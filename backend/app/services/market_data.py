"""Market data upkeep that needs no outside service (M1).

- Adjusted closes from stored corporate actions (PRD 7.2).
- Index and macro series reads for the public API.
- Admin entry of gold and silver prices (Q9 default: manual daily entry).
- Admin CSV loads of index and macro series, for backfills before live adapters exist.
- Quality checks that span days, stored as `data_issue` rows (PRD section 8).
"""

import csv
import datetime as dt
import hashlib
import io
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.adjustment import Action, back_adjust
from app.core.app_config import get_config
from app.core.security import utcnow
from app.core.trading_calendar import TradingCalendar
from app.models import (
    Company,
    CorporateAction,
    CorporateActionType,
    DataIssue,
    IndexDaily,
    MacroSeries,
    PriceDaily,
    Source,
    User,
)
from app.services import quality
from app.services.auth import AuthError, audit
from app.services.quality import Issue

MANUAL_SOURCE = "Manual admin entry"


def market_config() -> dict[str, Any]:
    return get_config("market").data


# --- adjusted closes ------------------------------------------------------------------


def recompute_adjusted_closes(db: Session, tickers: set[str] | None = None) -> int:
    """Write `adj_close` for every ticker that has a missing value, or for `tickers`.

    The whole series of a ticker is rewritten, because a new corporate action changes every
    earlier adjusted price. Returns how many rows changed.
    """
    if tickers is None:
        tickers = set(
            db.scalars(select(PriceDaily.ticker).where(PriceDaily.adj_close.is_(None)).distinct())
        )
    changed = 0
    for ticker in sorted(tickers):
        rows = list(
            db.scalars(
                select(PriceDaily).where(PriceDaily.ticker == ticker).order_by(PriceDaily.date)
            )
        )
        actions = [
            Action(a.ex_date, CorporateActionType(a.type), a.ratio, a.amount)
            for a in db.scalars(select(CorporateAction).where(CorporateAction.ticker == ticker))
        ]
        adjusted = back_adjust([(r.date, r.close) for r in rows], actions)
        for row, (_, value) in zip(rows, adjusted, strict=True):
            if row.adj_close != value:
                row.adj_close = value
                changed += 1
    db.flush()
    return changed


def add_corporate_action(
    db: Session,
    actor: User,
    *,
    ticker: str,
    ex_date: dt.date,
    type: CorporateActionType,
    ratio: Decimal | None,
    amount: Decimal | None,
    source_name: str,
    source_url: str | None,
) -> CorporateAction:
    """Admin entry of a corporate action; the ticker's adjusted closes are rewritten."""
    if db.scalar(select(Company.id).where(Company.ticker == ticker)) is None:
        raise AuthError("NOT_FOUND", 404)
    try:
        Action(ex_date, type, ratio, amount)
        if type is not CorporateActionType.CASH_DIVIDEND and (ratio is None or ratio <= 0):
            raise ValueError
        if (
            type in (CorporateActionType.RIGHTS, CorporateActionType.CASH_DIVIDEND)
            and amount is None
        ):
            raise ValueError
    except ValueError as exc:
        raise AuthError("VALIDATION", 422) from exc
    exists = db.scalar(
        select(CorporateAction.id).where(
            CorporateAction.ticker == ticker,
            CorporateAction.ex_date == ex_date,
            CorporateAction.type == type.value,
        )
    )
    if exists is not None:
        raise AuthError("DUPLICATE", 409)
    source = Source(name=source_name, url=source_url, fetched_at=utcnow())
    db.add(source)
    db.flush()
    row = CorporateAction(
        ticker=ticker,
        ex_date=ex_date,
        type=type.value,
        ratio=ratio,
        amount=amount,
        source_id=source.id,
    )
    db.add(row)
    db.flush()
    recompute_adjusted_closes(db, {ticker})
    audit(
        db,
        str(actor.id),
        "corporate_action.create",
        "corporate_action",
        str(row.id),
        after={"ticker": ticker, "ex_date": ex_date.isoformat(), "type": type.value},
    )
    return row


# --- series reads ---------------------------------------------------------------------


def index_series(
    db: Session, code: str, start: dt.date | None = None, end: dt.date | None = None
) -> list[IndexDaily]:
    statement = select(IndexDaily).where(IndexDaily.index_code == code)
    if start is not None:
        statement = statement.where(IndexDaily.date >= start)
    if end is not None:
        statement = statement.where(IndexDaily.date <= end)
    return list(db.scalars(statement.order_by(IndexDaily.date)))


def macro_series(
    db: Session, code: str, start: dt.date | None = None, end: dt.date | None = None
) -> list[MacroSeries]:
    statement = select(MacroSeries).where(MacroSeries.series_code == code)
    if start is not None:
        statement = statement.where(MacroSeries.date >= start)
    if end is not None:
        statement = statement.where(MacroSeries.date <= end)
    return list(db.scalars(statement.order_by(MacroSeries.date)))


def series_codes(db: Session) -> dict[str, list[str]]:
    """Every index and macro code that has data."""
    return {
        "indices": sorted(db.scalars(select(IndexDaily.index_code).distinct())),
        "macro": sorted(db.scalars(select(MacroSeries.series_code).distinct())),
    }


# --- manual gold and silver prices (Q9) -----------------------------------------------


def add_metal_price(
    db: Session, actor: User, *, code: str, day: dt.date, value: Decimal, note: str | None
) -> MacroSeries:
    """Store one admin-entered price per gram. Replaces that day's value if it exists.

    A value that moves more than `metal_prices.max_change_pct` from the previous day's is
    refused as a likely typing error.
    """
    cfg = market_config()["metal_prices"]
    if code not in cfg["series"] or value <= 0:
        raise AuthError("VALIDATION", 422)
    previous = db.scalar(
        select(MacroSeries)
        .where(MacroSeries.series_code == code, MacroSeries.date < day)
        .order_by(MacroSeries.date.desc())
        .limit(1)
    )
    if previous is not None and previous.value > 0:
        move = abs(value / previous.value - 1) * 100
        if move > Decimal(str(cfg["max_change_pct"])):
            raise AuthError("PRICE_CHANGE_TOO_LARGE", 422)
    source = Source(name=MANUAL_SOURCE, url=None, fetched_at=utcnow(), checksum=None)
    db.add(source)
    db.flush()
    row = db.scalar(
        select(MacroSeries).where(MacroSeries.series_code == code, MacroSeries.date == day)
    )
    before = None if row is None else {"value": str(row.value)}
    if row is None:
        row = MacroSeries(series_code=code, date=day, value=value, source_id=source.id)
        db.add(row)
    else:
        row.value, row.source_id = value, source.id
    db.flush()
    audit(
        db,
        str(actor.id),
        "macro_series.manual_entry",
        "macro_series",
        f"{code}:{day.isoformat()}",
        before=before,
        after={"value": str(value), "note": note},
    )
    return row


# --- CSV loads ------------------------------------------------------------------------


@dataclass
class CsvLoadResult:
    inserted: int = 0
    updated: int = 0
    errors: list[str] = field(default_factory=list)


def import_series_csv(
    db: Session,
    actor: User,
    *,
    kind: str,
    content: bytes,
    source_name: str,
    source_url: str | None,
) -> CsvLoadResult:
    """Load `code,date,value` rows into `index_daily` (kind "index") or `macro_series`.

    Codes must be listed under `csv_series` in config/market.yaml. A file with any bad row
    is refused whole, so a half-loaded series never reaches the analytics.
    """
    cfg = market_config()["csv_series"]
    allowed = set(cfg["index_codes"] if kind == "index" else cfg["macro_codes"])
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AuthError("CSV_INVALID", 422) from exc
    reader = csv.DictReader(io.StringIO(text))
    fields = {(f or "").strip().lower() for f in reader.fieldnames or []}
    if not {"code", "date", "value"} <= fields:
        raise AuthError("CSV_INVALID", 422)

    result = CsvLoadResult()
    parsed: dict[tuple[str, dt.date], Decimal] = {}
    for line, raw in enumerate(reader, start=2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        code = row["code"].upper()
        try:
            day = dt.date.fromisoformat(row["date"])
            value = Decimal(row["value"].replace(",", ""))
        except (ValueError, InvalidOperation):
            result.errors.append(f"line {line}: bad date or value")
            continue
        if code not in allowed:
            result.errors.append(f"line {line}: code {code} is not allowed")
        elif value <= 0 and kind == "index":
            result.errors.append(f"line {line}: index level must be positive")
        elif (code, day) in parsed:
            result.errors.append(f"line {line}: duplicate {code} {day}")
        else:
            parsed[(code, day)] = value
    if result.errors or not parsed:
        if not parsed and not result.errors:
            result.errors.append("no rows")
        return result

    source = Source(
        name=source_name,
        url=source_url,
        fetched_at=utcnow(),
        checksum=hashlib.sha256(content).hexdigest(),
    )
    db.add(source)
    db.flush()
    model: Any = IndexDaily if kind == "index" else MacroSeries
    code_col = model.index_code if kind == "index" else model.series_code
    value_attr = "close" if kind == "index" else "value"
    existing = {
        (getattr(r, "index_code" if kind == "index" else "series_code"), r.date): r
        for r in db.scalars(select(model).where(code_col.in_({c for c, _ in parsed})))
    }
    for (code, day), value in parsed.items():
        current = existing.get((code, day))
        if current is None:
            fields_ = {"index_code" if kind == "index" else "series_code": code}
            db.add(model(**fields_, date=day, **{value_attr: value}, source_id=source.id))
            result.inserted += 1
        else:
            setattr(current, value_attr, value)
            current.source_id = source.id
            result.updated += 1
    db.flush()
    audit(
        db,
        str(actor.id),
        f"{'index_daily' if kind == 'index' else 'macro_series'}.csv_import",
        "source",
        str(source.id),
        after={"inserted": result.inserted, "updated": result.updated},
    )
    return result


# --- daily quality checks (PRD section 8) ---------------------------------------------


def _store_issues(db: Session, issues: list[Issue]) -> int:
    """Add issues not already open with the same check, dataset, entity and date."""
    added = 0
    for issue in issues:
        exists = db.scalar(
            select(DataIssue.id).where(
                DataIssue.check_name == issue.check_name,
                DataIssue.dataset == issue.dataset,
                DataIssue.entity.is_(None)
                if issue.entity is None
                else DataIssue.entity == issue.entity,
                DataIssue.date.is_(None) if issue.day is None else DataIssue.date == issue.day,
                DataIssue.status == "OPEN",
            )
        )
        if exists is None:
            db.add(
                DataIssue(
                    check_name=issue.check_name,
                    dataset=issue.dataset,
                    entity=issue.entity,
                    date=issue.day,
                    detail=issue.detail,
                )
            )
            added += 1
    db.flush()
    return added


def run_quality_checks(
    db: Session, calendar: TradingCalendar, today: dt.date, lookback_sessions: int = 20
) -> dict[str, int]:
    """Check the last `lookback_sessions` trading days of prices and indices.

    Finds missing trading days, moves above the configured limit with no corporate action,
    and stale datasets. Returns the number of new issues per check.
    """
    cfg = get_config("schedules").data["quality"]
    max_move = Decimal(str(cfg["max_unexplained_move_pct"]))
    stale_after = int(cfg["stale_after_trading_days"])
    issues: list[Issue] = []

    sessions = calendar.trading_days(today - dt.timedelta(days=lookback_sessions * 2), today)
    sessions = sessions[-lookback_sessions:]
    newest_price = db.scalar(select(func.max(PriceDaily.date)))
    if sessions and newest_price is not None:
        window_end = min(sessions[-1], newest_price)
        present = set(
            db.scalars(select(PriceDaily.date).where(PriceDaily.date >= sessions[0]).distinct())
        )
        issues += quality.check_missing_trading_days(
            calendar, sessions[0], window_end, present, "price_daily"
        )
        start = calendar.previous_trading_day(sessions[0])
        closes: dict[str, list[tuple[dt.date, Decimal]]] = defaultdict(list)
        for ticker, day, close in db.execute(
            select(PriceDaily.ticker, PriceDaily.date, PriceDaily.close).where(
                PriceDaily.date >= start
            )
        ):
            closes[ticker].append((day, close))
        ex_dates: dict[str, set[dt.date]] = defaultdict(set)
        for ticker, day in db.execute(
            select(CorporateAction.ticker, CorporateAction.ex_date).where(
                CorporateAction.ex_date >= start,
                CorporateAction.type != CorporateActionType.CASH_DIVIDEND.value,
            )
        ):
            ex_dates[ticker].add(day)
        for ticker, series in sorted(closes.items()):
            issues += quality.check_unexplained_moves(ticker, series, ex_dates[ticker], max_move)

    issues += quality.check_stale(calendar, newest_price, today, stale_after, "price_daily")
    issues += quality.check_stale(
        calendar, db.scalar(select(func.max(IndexDaily.date))), today, stale_after, "index_daily"
    )

    return {"found": len(issues), "added": _store_issues(db, issues)}
