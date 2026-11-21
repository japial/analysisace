"""Shariah screening use cases (F1, FR2.1).

`run_screening` screens every reviewed reporting period of every company with each method in
config/shariah.yaml and keeps every result (FR1.4). The company's shown status is the default
method's result for its newest period, unless an admin override is set (FR1.6). Each change
of shown status is stored in `shariah_status_change` and returned, so alerts can follow.

Market cap is the mean of daily close x shares outstanding over the method's trailing window
ending on the period end, so a result can be reproduced from stored prices.
"""

import datetime as dt
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.analytics.regime import add_months
from app.analytics.shariah import ScreenInput, average_market_cap, screen
from app.core.app_config import get_config
from app.core.security import utcnow
from app.models import (
    BusinessClassification,
    Company,
    CompanyShariahStatus,
    Financials,
    PriceDaily,
    ShariahResult,
    ShariahStatusChange,
    Source,
    User,
)
from app.models.enums import PeriodType, ShariahStatus
from app.services.auth import AuthError, audit
from app.services.valuation import closes_on

_Q6 = Decimal("0.000001")


@dataclass(frozen=True)
class StatusChange:
    ticker: str
    from_status: str | None
    to_status: str
    cause: str


def shariah_config() -> dict[str, Any]:
    return get_config("shariah").data


def effective_status(row: CompanyShariahStatus) -> str:
    return row.override_status or row.status


# --- running the screen ---------------------------------------------------------------


def _market_cap(
    db: Session, ticker: str, period_end: dt.date, months: int, shares: int | None
) -> Decimal | None:
    start = add_months(dt.date(period_end.year, period_end.month, 1), -months + 1)
    closes = list(
        db.scalars(
            select(PriceDaily.close).where(
                PriceDaily.ticker == ticker,
                PriceDaily.date >= start,
                PriceDaily.date <= period_end,
            )
        )
    )
    return average_market_cap(closes, shares)


def screen_period(
    db: Session,
    fin: Financials,
    classification: BusinessClassification | None,
    method_name: str,
    now: dt.datetime,
) -> ShariahResult:
    """Screen one period with one method. A stored result for this config version is kept
    when the outcome is unchanged and updated when its inputs changed."""
    cfg = shariah_config()
    version = get_config("shariah").version
    existing = db.scalar(
        select(ShariahResult).where(
            ShariahResult.ticker == fin.ticker,
            ShariahResult.period_end == fin.period_end,
            ShariahResult.method == method_name,
            ShariahResult.method_version == version,
        )
    )
    method = cfg["methods"][method_name]
    cap = _market_cap(
        db,
        fin.ticker,
        fin.period_end,
        int(method["market_cap_average_months"]),
        fin.shares_outstanding,
    )
    outcome = screen(
        ScreenInput(
            stage1_pass=None if classification is None else classification.stage1_pass,
            stage1_reason=None if classification is None else classification.reason,
            market_cap=cap,
            total_debt_interest_bearing=fin.total_debt_interest_bearing,
            cash_and_interest_securities=fin.cash_and_interest_securities,
            receivables=fin.receivables,
            total_revenue=fin.total_revenue,
            non_permissible_income=fin.non_permissible_income,
        ),
        method,
        Decimal(str(cfg["review_margin_pts"])),
    )
    ratios = outcome.ratios_json
    if cap is not None:
        ratios.append(
            {
                "rule": "market_cap_average",
                "value": str(cap),
                "months": int(method["market_cap_average_months"]),
            }
        )
    if existing is not None:
        same = (
            existing.status == outcome.status.value
            and existing.ratios == ratios
            and existing.reasons == outcome.reasons
            and existing.financials_id == fin.id
        )
        if not same:
            # The inputs changed (reclassification or corrected figures) under the same
            # config version. Status history stays in shariah_status_change.
            existing.status, existing.ratios = outcome.status.value, ratios
            existing.reasons, existing.financials_id = outcome.reasons, fin.id
            existing.screened_at = now
            db.flush()
        return existing
    row = ShariahResult(
        ticker=fin.ticker,
        period_end=fin.period_end,
        method=method_name,
        method_version=version,
        status=outcome.status.value,
        ratios=ratios,
        reasons=outcome.reasons,
        financials_id=fin.id,
        screened_at=now,
    )
    db.add(row)
    db.flush()
    return row


def _set_status(
    db: Session,
    ticker: str,
    status: str,
    method: str,
    result: ShariahResult | None,
    npi_ratio: Decimal | None,
    now: dt.datetime,
) -> StatusChange | None:
    version = get_config("shariah").version
    row = db.scalar(select(CompanyShariahStatus).where(CompanyShariahStatus.ticker == ticker))
    if row is None:
        row = CompanyShariahStatus(
            ticker=ticker,
            status=status,
            method=method,
            method_version=version,
            result_id=result.id if result else None,
            screened_at=now,
            non_permissible_income_ratio=npi_ratio,
        )
        db.add(row)
        db.flush()
        db.add(
            ShariahStatusChange(
                ticker=ticker,
                from_status=None,
                to_status=status,
                cause="SCREEN",
                result_id=result.id if result else None,
                changed_at=now,
            )
        )
        db.flush()
        return StatusChange(ticker, None, status, "SCREEN")

    before = effective_status(row)
    changed_screen = row.status != status
    row.status, row.method, row.method_version = status, method, version
    row.result_id = result.id if result else None
    row.screened_at, row.non_permissible_income_ratio = now, npi_ratio
    db.flush()
    after = effective_status(row)
    if not changed_screen or after == before:
        return None
    db.add(
        ShariahStatusChange(
            ticker=ticker,
            from_status=before,
            to_status=after,
            cause="SCREEN",
            result_id=row.result_id,
            changed_at=now,
        )
    )
    db.flush()
    return StatusChange(ticker, before, after, "SCREEN")


def screen_company(db: Session, ticker: str, now: dt.datetime) -> StatusChange | None:
    cfg = shariah_config()
    default = str(cfg["default_method"])
    classification = db.scalar(
        select(BusinessClassification).where(BusinessClassification.ticker == ticker)
    )
    periods = list(
        db.scalars(
            select(Financials)
            .where(Financials.ticker == ticker, Financials.reviewed_at.is_not(None))
            .order_by(Financials.period_end)
        )
    )
    latest: ShariahResult | None = None
    for fin in periods:
        for method_name in cfg["methods"]:
            result = screen_period(db, fin, classification, method_name, now)
            if method_name == default and fin is periods[-1]:
                latest = result

    if latest is not None:
        fin = periods[-1]
        npi = (
            (fin.non_permissible_income / fin.total_revenue).quantize(_Q6)
            if fin.non_permissible_income is not None and fin.total_revenue
            else None
        )
        return _set_status(db, ticker, latest.status, default, latest, npi, now)
    # No reviewed figures: Stage 1 alone can still decide a failure.
    if classification is not None and not classification.stage1_pass:
        return _set_status(db, ticker, ShariahStatus.NON_COMPLIANT.value, default, None, None, now)
    return _set_status(db, ticker, ShariahStatus.UNDER_REVIEW.value, default, None, None, now)


def run_screening(db: Session, now: dt.datetime | None = None) -> list[StatusChange]:
    """Screen every active company. Returns the changes of shown status."""
    now = now or utcnow()
    changes: list[StatusChange] = []
    for ticker in db.scalars(
        select(Company.ticker).where(Company.is_active.is_(True)).order_by(Company.ticker)
    ):
        change = screen_company(db, ticker, now)
        if change is not None:
            changes.append(change)
    return changes


# --- admin actions (FR1.6) ------------------------------------------------------------


def _status_row(db: Session, ticker: str) -> CompanyShariahStatus:
    row = db.scalar(select(CompanyShariahStatus).where(CompanyShariahStatus.ticker == ticker))
    if row is None:
        raise AuthError("NOT_SCREENED", 409)
    return row


def set_override(
    db: Session, actor: User, ticker: str, status: ShariahStatus | None, reason: str
) -> tuple[CompanyShariahStatus, StatusChange | None]:
    """Set or clear a manual override. A reason is always required and the change audited."""
    if not reason.strip():
        raise AuthError("VALIDATION", 422)
    row = _status_row(db, ticker)
    before = effective_status(row)
    snapshot = {"override_status": row.override_status, "override_reason": row.override_reason}
    row.override_status = None if status is None else status.value
    row.override_reason = None if status is None else reason.strip()
    row.override_by = None if status is None else actor.id
    db.flush()
    after = effective_status(row)
    audit(
        db,
        str(actor.id),
        "shariah.override",
        "company_shariah_status",
        ticker,
        before=snapshot,
        after={"override_status": row.override_status, "reason": reason.strip()},
    )
    change = None
    if after != before:
        now = utcnow()
        db.add(
            ShariahStatusChange(
                ticker=ticker,
                from_status=before,
                to_status=after,
                cause="OVERRIDE",
                result_id=row.result_id,
                changed_at=now,
            )
        )
        db.flush()
        change = StatusChange(ticker, before, after, "OVERRIDE")
    return row, change


def set_board_note(db: Session, actor: User, ticker: str, note: str | None) -> CompanyShariahStatus:
    row = _status_row(db, ticker)
    before = {"board_note": row.board_note}
    row.board_note = note.strip() if note and note.strip() else None
    db.flush()
    audit(
        db,
        str(actor.id),
        "shariah.board_note",
        "company_shariah_status",
        ticker,
        before=before,
        after={"board_note": row.board_note},
    )
    return row


def set_classification(
    db: Session,
    actor: User,
    ticker: str,
    *,
    stage1_pass: bool,
    activity: str | None,
    reason: str,
) -> BusinessClassification:
    """Stage 1 (PRD 7.1). A failing company names an excluded activity from config."""
    if db.scalar(select(Company.id).where(Company.ticker == ticker)) is None:
        raise AuthError("NOT_FOUND", 404)
    excluded = shariah_config()["stage1_excluded_activities"]
    if not reason.strip() or (not stage1_pass and activity not in excluded):
        raise AuthError("VALIDATION", 422)
    row = db.scalar(select(BusinessClassification).where(BusinessClassification.ticker == ticker))
    before = None if row is None else {"stage1_pass": row.stage1_pass, "activity": row.activity}
    if row is None:
        row = BusinessClassification(
            ticker=ticker, stage1_pass=stage1_pass, reason=reason, method_version=""
        )
        db.add(row)
    row.stage1_pass = stage1_pass
    row.activity = None if stage1_pass else activity
    row.reason = reason.strip()
    row.method_version = get_config("shariah").version
    row.set_by = actor.id
    db.flush()
    audit(
        db,
        str(actor.id),
        "shariah.classification",
        "business_classification",
        ticker,
        before=before,
        after={"stage1_pass": stage1_pass, "activity": row.activity},
    )
    return row


# --- financials and the review screen -------------------------------------------------

FIGURES = (
    "total_debt_interest_bearing",
    "cash_and_interest_securities",
    "receivables",
    "total_revenue",
    "non_permissible_income",
    "zakatable_assets",
)


def list_financials(
    db: Session, *, ticker: str | None, reviewed: bool | None, limit: int, offset: int
) -> tuple[list[Financials], int]:
    filters: list[ColumnElement[bool]] = []
    if ticker:
        filters.append(Financials.ticker == ticker)
    if reviewed is True:
        filters.append(Financials.reviewed_at.is_not(None))
    elif reviewed is False:
        filters.append(Financials.reviewed_at.is_(None))
    total = db.scalar(select(func.count()).select_from(Financials).where(*filters)) or 0
    rows = list(
        db.scalars(
            select(Financials)
            .where(*filters)
            .order_by(Financials.period_end.desc(), Financials.ticker)
            .limit(limit)
            .offset(offset)
        )
    )
    return rows, total


def save_financials(
    db: Session,
    actor: User,
    *,
    ticker: str,
    period_end: dt.date,
    period_type: PeriodType,
    figures: dict[str, Decimal | None],
    shares_outstanding: int | None,
    source_name: str,
    source_url: str | None,
    source_page: int | None,
) -> Financials:
    """Create or replace one period's figures. Saved figures wait for review (PRD section 8)."""
    if db.scalar(select(Company.id).where(Company.ticker == ticker)) is None:
        raise AuthError("NOT_FOUND", 404)
    if any(v is not None and v < 0 for v in figures.values()) or (
        shares_outstanding is not None and shares_outstanding <= 0
    ):
        raise AuthError("VALIDATION", 422)
    source = Source(name=source_name, url=source_url, fetched_at=utcnow())
    db.add(source)
    db.flush()
    row = db.scalar(
        select(Financials).where(
            Financials.ticker == ticker,
            Financials.period_end == period_end,
            Financials.period_type == period_type.value,
        )
    )
    if row is None:
        row = Financials(
            ticker=ticker, period_end=period_end, period_type=period_type.value, source_id=source.id
        )
        db.add(row)
    for name in FIGURES:
        setattr(row, name, figures.get(name))
    row.shares_outstanding = shares_outstanding
    row.source_id, row.source_page = source.id, source_page
    row.reviewed_by, row.reviewed_at = None, None
    db.flush()
    audit(
        db,
        str(actor.id),
        "financials.save",
        "financials",
        str(row.id),
        after={"ticker": ticker, "period_end": period_end.isoformat()},
    )
    return row


def review_financials(db: Session, actor: User, financials_id: uuid.UUID) -> Financials:
    """Mark figures as checked against the report. Only reviewed figures are screened."""
    row = db.get(Financials, financials_id)
    if row is None:
        raise AuthError("NOT_FOUND", 404)
    if row.reviewed_at is None:
        row.reviewed_by, row.reviewed_at = actor.id, utcnow()
        db.flush()
        audit(db, str(actor.id), "financials.review", "financials", str(row.id))
    return row


# --- reads ----------------------------------------------------------------------------


def latest_market_caps(db: Session, tickers: list[str]) -> dict[str, tuple[Decimal, uuid.UUID]]:
    """Newest close x newest reviewed shares outstanding, with the price's source."""
    if not tickers:
        return {}
    newest = db.scalar(select(func.max(PriceDaily.date)))
    if newest is None:
        return {}
    prices = closes_on(db, set(tickers), newest)
    shares: dict[str, int] = {}
    for fin in db.scalars(
        select(Financials)
        .where(Financials.ticker.in_(tickers), Financials.reviewed_at.is_not(None))
        .order_by(Financials.period_end)
    ):
        if fin.shares_outstanding:
            shares[fin.ticker] = fin.shares_outstanding
    return {
        t: ((p.close * shares[t]).quantize(Decimal("0.01")), p.source_id)
        for t, p in prices.items()
        if t in shares
    }
