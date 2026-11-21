"""Sukuk and Islamic bank investments (F26).

Holdings themselves are ordinary portfolio holdings (services/portfolio.py). This module
adds the views on top: profit so far, the maturity calendar, the rate comparison and the
bank safety panel. All of it is information, never a recommendation (FR26.4).
"""

import datetime as dt
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.allocation import expected_profit, real_rate_pct
from app.core.security import utcnow
from app.models import AltAsset, BankFlag, IslamicProduct, SukukIssue, User
from app.models.enums import BankStatus
from app.services.auth import AuthError, audit
from app.services.valuation import (
    Portfolio,
    Position,
    latest_macro,
    load_portfolio,
    personal_config,
    today_dhaka,
)

Q2 = Decimal("0.01")
HUNDRED = Decimal(100)
ISLAMIC_TYPES = ("SUKUK", "ISLAMIC_DEPOSIT")


@dataclass
class IslamicHolding:
    position: Position
    # The final rate once the bank has declared it, otherwise the expected rate (FR26.2).
    rate_pct: Decimal | None
    rate_is_final: bool
    # Profit at that rate from the start date to today (or maturity, if earlier).
    profit_at_rate: Decimal | None
    profit_received: Decimal
    tax_deducted: Decimal
    days_to_maturity: int | None


def islamic_holdings(
    db: Session, household_id: uuid.UUID
) -> tuple[list[IslamicHolding], Portfolio]:
    portfolio = load_portfolio(db, household_id)
    today = portfolio.day
    out: list[IslamicHolding] = []
    for position in portfolio.positions:
        holding = position.holding
        if holding is None or holding.instrument_type not in ISLAMIC_TYPES:
            continue
        rate = holding.final_rate if holding.final_rate is not None else holding.expected_rate
        profit: Decimal | None = None
        if rate is not None and holding.start_date:
            until = min(today, holding.maturity_date) if holding.maturity_date else today
            profit = expected_profit(holding.cost, rate, holding.start_date, until)
        out.append(
            IslamicHolding(
                position=position,
                rate_pct=rate,
                rate_is_final=holding.final_rate is not None,
                profit_at_rate=profit,
                profit_received=holding.profit_received,
                tax_deducted=holding.tax_deducted,
                days_to_maturity=(holding.maturity_date - today).days
                if holding.maturity_date
                else None,
            )
        )
    return out, portfolio


# --- calendar (FR26.3) ----------------------------------------------------------------


def calendar(db: Session, household_id: uuid.UUID, *, days: int = 365) -> list[dict[str, Any]]:
    """Maturities of the household's holdings and upcoming government sukuk auctions."""
    today = today_dhaka()
    until = today + dt.timedelta(days=days)
    portfolio = load_portfolio(db, household_id)
    events: list[dict[str, Any]] = []
    for position in portfolio.positions:
        holding = position.holding
        if (
            holding is not None
            and holding.maturity_date
            and today <= holding.maturity_date <= until
        ):
            events.append(
                {
                    "date": holding.maturity_date,
                    "kind": "MATURITY",
                    "name": holding.name,
                    "instrument_type": holding.instrument_type,
                    "institution": position.institution,
                    "amount": position.value,
                    "holding_id": holding.id,
                    "days_away": (holding.maturity_date - today).days,
                }
            )
    for alt in db.scalars(
        select(AltAsset).where(
            AltAsset.household_id == household_id,
            AltAsset.is_active.is_(True),
            AltAsset.expected_exit_date >= today,
            AltAsset.expected_exit_date <= until,
        )
    ):
        assert alt.expected_exit_date is not None
        events.append(
            {
                "date": alt.expected_exit_date,
                "kind": "EXPECTED_EXIT",
                "name": alt.name,
                "instrument_type": alt.type,
                "institution": alt.counterparty,
                "amount": None,
                "alt_asset_id": alt.id,
                "days_away": (alt.expected_exit_date - today).days,
            }
        )
    for issue in upcoming_auctions(db, today, until):
        assert issue.auction_date is not None
        events.append(
            {
                "date": issue.auction_date,
                "kind": "SUKUK_AUCTION",
                "name": issue.name,
                "instrument_type": "SUKUK",
                "institution": issue.issuer,
                "amount": issue.min_investment,
                "rate_pct": issue.rate_pct,
                "individual_quota_pct": issue.individual_quota_pct,
                "days_away": (issue.auction_date - today).days,
            }
        )
    return sorted(events, key=lambda e: (e["date"], e["name"]))


def upcoming_auctions(db: Session, start: dt.date, end: dt.date) -> list[SukukIssue]:
    return list(
        db.scalars(
            select(SukukIssue)
            .where(
                SukukIssue.is_government.is_(True),
                SukukIssue.auction_date >= start,
                SukukIssue.auction_date <= end,
            )
            .order_by(SukukIssue.auction_date)
        )
    )


# --- catalogue and comparison (FR26.4) ------------------------------------------------


def list_products(db: Session) -> list[IslamicProduct]:
    return list(
        db.scalars(
            select(IslamicProduct)
            .where(IslamicProduct.is_active.is_(True))
            .order_by(IslamicProduct.bank, IslamicProduct.name, IslamicProduct.tenor_months)
        )
    )


def list_sukuk(db: Session) -> list[SukukIssue]:
    return list(db.scalars(select(SukukIssue).order_by(SukukIssue.name)))


@dataclass
class Comparison:
    tbill_pct: Decimal | None = None
    tbill_date: dt.date | None = None
    inflation_pct: Decimal | None = None
    inflation_date: dt.date | None = None
    rows: list[dict[str, Any]] = field(default_factory=list)
    source_ids: set[uuid.UUID] = field(default_factory=set)


def compare(db: Session) -> Comparison:
    """Expected rates of sukuk and Islamic bank products beside the 91-day T-bill yield and
    CPI inflation, with the return above inflation. Rates are what issuers state; Mudaraba
    rates are provisional until declared."""
    config = personal_config()
    tbill = latest_macro(db, str(config["performance"]["risk_free_series"]))  # type: ignore[index]
    cpi = latest_macro(db, str(config["fire"]["inflation_series"]))  # type: ignore[index]
    result = Comparison(
        tbill_pct=tbill.value if tbill else None,
        tbill_date=tbill.date if tbill else None,
        inflation_pct=cpi.value if cpi else None,
        inflation_date=cpi.date if cpi else None,
    )
    result.source_ids = {m.source_id for m in (tbill, cpi) if m is not None}

    def row(kind: str, name: str, issuer: str, rate: Decimal | None, **extra: Any) -> None:
        result.rows.append(
            {
                "kind": kind,
                "name": name,
                "issuer": issuer,
                "rate_pct": rate,
                "real_rate_pct": real_rate_pct(rate, cpi.value)
                if rate is not None and cpi
                else None,
                "spread_over_tbill_pts": (rate - tbill.value).quantize(Q2)
                if rate is not None and tbill
                else None,
                **extra,
            }
        )

    for issue in list_sukuk(db):
        row(
            "SUKUK",
            issue.name,
            issue.issuer,
            issue.rate_pct,
            tenor_months=None,
            min_amount=issue.min_investment,
            rate_is_provisional=False,
            as_of=None,
        )
        if issue.source_id:
            result.source_ids.add(issue.source_id)
    for product in list_products(db):
        row(
            product.product_type,
            product.name,
            product.bank,
            product.expected_rate_pct,
            tenor_months=product.tenor_months,
            min_amount=product.min_amount,
            rate_is_provisional=product.rate_is_provisional,
            as_of=product.as_of,
        )
        if product.source_id:
            result.source_ids.add(product.source_id)
    result.rows.sort(key=lambda r: (r["rate_pct"] is None, -(r["rate_pct"] or Decimal(0))))
    return result


# --- bank safety panel (FR26.5) -------------------------------------------------------


def bank_safety(db: Session, household_id: uuid.UUID) -> list[dict[str, Any]]:
    """How much of the household's bank money sits with each bank, and any notice on it."""
    deposit_types = set(personal_config()["portfolio"]["bank_deposit_types"])  # type: ignore[index]
    portfolio = load_portfolio(db, household_id)
    by_bank: dict[str, Decimal] = {}
    for position in portfolio.positions:
        if position.type in deposit_types and position.institution:
            by_bank[position.institution] = (
                by_bank.get(position.institution, Decimal(0)) + position.household_value
            )
    total = sum(by_bank.values(), Decimal(0))
    flags = {flag.bank.lower(): flag for flag in db.scalars(select(BankFlag))}
    rows = []
    for bank, amount in sorted(by_bank.items(), key=lambda item: -item[1]):
        flag = flags.get(bank.lower())
        rows.append(
            {
                "bank": bank,
                "amount": amount.quantize(Q2),
                "share_pct": (amount / total * 100).quantize(Q2) if total > 0 else Decimal(0),
                "status": flag.status if flag else BankStatus.NORMAL.value,
                "note_en": flag.note_en if flag else None,
                "note_bn": flag.note_bn if flag else None,
                "source_links": flag.source_links if flag else [],
                "flag_updated_at": flag.updated_at if flag else None,
            }
        )
    return rows


def list_bank_flags(db: Session) -> list[BankFlag]:
    return list(db.scalars(select(BankFlag).order_by(BankFlag.bank)))


def set_bank_flag(
    db: Session,
    actor: User,
    *,
    bank: str,
    status: BankStatus,
    note_en: str,
    note_bn: str,
    source_links: list[dict[str, str]],
) -> BankFlag:
    """Admin: add or change the notice on a bank. Audited, and must stay neutral and sourced."""
    name = bank.strip()
    flag = db.scalar(select(BankFlag).where(BankFlag.bank == name))
    before = {"status": flag.status} if flag else None
    if flag is None:
        flag = BankFlag(bank=name)
        db.add(flag)
    flag.status = status.value
    flag.note_en, flag.note_bn = note_en.strip(), note_bn.strip()
    flag.source_links = source_links
    flag.set_by = actor.id
    flag.updated_at = utcnow()
    db.flush()
    audit(
        db,
        str(actor.id),
        "BANK_FLAG_SET",
        "bank_flag",
        str(flag.id),
        before=before,
        after={"status": status.value},
    )
    return flag


def delete_bank_flag(db: Session, actor: User, flag_id: uuid.UUID) -> None:
    flag = db.get(BankFlag, flag_id)
    if flag is None:
        raise AuthError("NOT_FOUND", 404)
    db.delete(flag)
    db.flush()
    audit(db, str(actor.id), "BANK_FLAG_REMOVED", "bank_flag", str(flag_id))


def safe_return_pct(db: Session, household_id: uuid.UUID) -> tuple[Decimal | None, str]:
    """A starting return for the FIRE form (FR17.5): the value-weighted rate of the
    household's own sukuk and deposits, else the latest T-bill yield. The person can
    change it; it is not a forecast."""
    rows, _ = islamic_holdings(db, household_id)
    weighted = [(r.position.household_value, r.rate_pct) for r in rows if r.rate_pct is not None]
    total = sum((value for value, _ in weighted), Decimal(0))
    if total > 0:
        rate = sum((value * rate for value, rate in weighted), Decimal(0)) / total
        return rate.quantize(Q2), "OWN_SUKUK_AND_DEPOSITS"
    code = str(personal_config()["fire"]["fallback_return_series"])  # type: ignore[index]
    tbill = latest_macro(db, code)
    return (tbill.value.quantize(Q2), "TBILL_91D") if tbill else (None, "NONE")
