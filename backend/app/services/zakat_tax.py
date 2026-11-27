"""Tax and Zakat snapshots (F13).

A snapshot is worked out for one person on one date from everything the household has
recorded, and stored with every line so it can be read back exactly (FR13.1). Rules come
from config/zakat.yaml and are provisional until the Shariah advisor approves them (Q2).
analysisACE never files a tax return (FR13.6).
"""

import csv
import datetime as dt
import io
import re
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics import zakat as formulas
from app.analytics.returns import Trade, realised_gains
from app.core.app_config import get_config
from app.models import (
    CashFlow,
    Financials,
    HouseholdMember,
    IncomeEntry,
    TaxSnapshot,
    Transaction,
    User,
    ZakatSnapshot,
)
from app.services.auth import AuthError, ConsentPurpose
from app.services.costs import csv_safe
from app.services.households import require_consent
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


# --- Zakat ----------------------------------------------------------------------------


def _zakatable_assets_value(db: Session, position: Position, day: dt.date) -> Decimal | None:
    """The company's zakatable assets behind this holding, from reviewed financials (FR13.3)."""
    holding = position.holding
    if holding is None or not holding.ticker:
        return None
    report = db.scalar(
        select(Financials)
        .where(
            Financials.ticker == holding.ticker,
            Financials.period_end <= day,
            Financials.reviewed_at.is_not(None),
            Financials.zakatable_assets.is_not(None),
            Financials.shares_outstanding.is_not(None),
        )
        .order_by(Financials.period_end.desc())
        .limit(1)
    )
    if report is None or not report.shares_outstanding or report.zakatable_assets is None:
        return None
    per_share = report.zakatable_assets / report.shares_outstanding
    return (per_share * holding.quantity).quantize(Q2)


def zakat_inputs(
    db: Session, portfolio: Portfolio, member: HouseholdMember, config: dict[str, Any]
) -> tuple[list[formulas.ZakatAsset], list[formulas.ZakatDebt]]:
    """Turn the household's positions into the calculator's inputs for one member."""
    n = len(portfolio.members)
    defaults: dict[str, str] = config["alt_asset_defaults"]
    assets: list[formulas.ZakatAsset] = []
    for position in portfolio.positions:
        pct = position.ownership.member_pct(member.id, n)
        if pct <= 0:
            continue
        holding, alt = position.holding, position.alt
        value = position.value
        if holding is not None:
            rule = holding.instrument_type.lower()
            if rule == "sukuk" and config.get("sukuk_basis") == "FACE":
                value = holding.cost
        else:
            assert alt is not None
            rule = alt.zakat_rule or defaults.get(alt.type, "other")
        assets.append(
            formulas.ZakatAsset(
                label=position.name,
                rule=rule,
                value=value,
                owner_pct=pct.quantize(Decimal("0.0001")),
                principal=holding.cost if holding is not None else None,
                profit_received=holding.profit_received if holding is not None else Decimal(0),
                is_interest_bearing=bool(holding and holding.is_interest_bearing),
                is_recoverable=alt.is_recoverable if alt is not None else True,
                zakatable_assets_value=_zakatable_assets_value(db, position, portfolio.day),
                asset_kind=position.kind,
                asset_id=str(position.id),
            )
        )
    debts = [
        formulas.ZakatDebt(
            label=debt.liability.name,
            due_within_year=debt.liability.due_within_year,
            owner_pct=debt.ownership.member_pct(member.id, n).quantize(Decimal("0.0001")),
            asset_id=str(debt.liability.id),
        )
        for debt in portfolio.debts
        if debt.ownership.member_pct(member.id, n) > 0
    ]
    return assets, debts


def compute_zakat(
    db: Session,
    household_id: uuid.UUID,
    member: HouseholdMember,
    *,
    day: dt.date | None = None,
    nisab_basis: str | None = None,
    price_per_gram: Decimal | None = None,
    shares_method: str | None = None,
) -> tuple[formulas.ZakatResult, dt.date, set[uuid.UUID]]:
    """Work out one member's Zakat. Nothing is stored."""
    loaded = get_config("zakat")
    config = loaded.data
    day = day or today_dhaka()
    basis = nisab_basis or member.nisab_basis
    if basis not in ("GOLD", "SILVER"):
        raise AuthError("NISAB_BASIS_REQUIRED", 422)
    portfolio = load_portfolio(db, household_id, day)
    sources = set(portfolio.source_ids)
    if price_per_gram is None:
        price = latest_macro(db, config["nisab_price_series"][basis], day)
        if price is None:
            raise AuthError("NISAB_PRICE_REQUIRED", 422)
        price_per_gram = price.value.quantize(Q2)
        sources.add(price.source_id)
    assets, debts = zakat_inputs(db, portfolio, member, config)
    result = formulas.compute_zakat(
        assets,
        debts,
        config=config,
        nisab_basis=basis,
        price_per_gram=price_per_gram,
        shares_method=shares_method,
    )
    return result, day, sources


def create_zakat_snapshot(
    db: Session, user: User, household_id: uuid.UUID, member: HouseholdMember, **options: Any
) -> tuple[ZakatSnapshot, set[uuid.UUID]]:
    """Compute and store a Zakat snapshot. Needs the religious-preferences consent (FR23.2)."""
    require_consent(user, ConsentPurpose.RELIGIOUS_PREFERENCES)
    result, day, sources = compute_zakat(db, household_id, member, **options)
    snapshot = ZakatSnapshot(
        member_id=member.id,
        date=day,
        nisab_basis=result.nisab_basis,
        price_per_gram=result.price_per_gram,
        nisab_value=result.nisab_value,
        shares_method=result.shares_method,
        items=[line.as_dict() for line in (*result.lines, *result.deductions)],
        total_zakatable=result.total_zakatable,
        total_deductions=result.total_deductions,
        net_zakatable=result.net_zakatable,
        zakat_due=result.zakat_due,
        config_version=get_config("zakat").version,
    )
    db.add(snapshot)
    db.flush()
    return snapshot, sources


def _member_ids(db: Session, household_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        db.scalars(select(HouseholdMember.id).where(HouseholdMember.household_id == household_id))
    )


def list_zakat_snapshots(db: Session, household_id: uuid.UUID) -> list[ZakatSnapshot]:
    return list(
        db.scalars(
            select(ZakatSnapshot)
            .where(ZakatSnapshot.member_id.in_(_member_ids(db, household_id)))
            .order_by(ZakatSnapshot.date.desc(), ZakatSnapshot.created_at.desc())
        )
    )


def get_zakat_snapshot(
    db: Session, household_id: uuid.UUID, snapshot_id: uuid.UUID
) -> ZakatSnapshot:
    row = db.get(ZakatSnapshot, snapshot_id)
    if row is None or row.member_id not in _member_ids(db, household_id):
        raise AuthError("NOT_FOUND", 404)
    return row


# --- Tax (FR13.6) ---------------------------------------------------------------------

_TAX_YEAR = re.compile(r"^(\d{4})-(\d{2})$")


def tax_year_bounds(tax_year: str) -> tuple[dt.date, dt.date]:
    """ "2026-27" -> 1 July 2026 to 30 June 2027 (the income year)."""
    match = _TAX_YEAR.match(tax_year)
    if not match or (int(match[1]) + 1) % 100 != int(match[2]):
        raise AuthError("TAX_YEAR_INVALID", 422)
    start_month = int(personal_config()["tax"]["year_start_month"])  # type: ignore[index]
    start = dt.date(int(match[1]), start_month, 1)
    return start, dt.date(start.year + 1, start_month, 1) - dt.timedelta(days=1)


def current_tax_year(today: dt.date) -> str:
    start_month = int(personal_config()["tax"]["year_start_month"])  # type: ignore[index]
    first = today.year if today.month >= start_month else today.year - 1
    return f"{first}-{(first + 1) % 100:02d}"


def _money(value: Decimal) -> str:
    return str(value.quantize(Q2))


def recorded_income(
    db: Session, household_id: uuid.UUID, member: HouseholdMember, start: dt.date, end: dt.date
) -> dict[str, Any]:
    """This member's income records in the period, split into the statement lines they fill
    and the kinds that are not counted (FR27.5). Records for the whole household, with no
    member, are not counted because they belong to no one person."""
    lines: dict[str, str] = dict(personal_config()["income"]["tax_lines"])  # type: ignore[index]
    rows = db.execute(
        select(IncomeEntry.kind, IncomeEntry.member_id, func.sum(IncomeEntry.amount))
        .where(
            IncomeEntry.household_id == household_id,
            IncomeEntry.date >= start,
            IncomeEntry.date <= end,
        )
        .group_by(IncomeEntry.kind, IncomeEntry.member_id)
    ).all()
    counted = {"salary": Decimal(0), "other": Decimal(0)}
    not_counted: dict[str, Decimal] = {}
    unassigned = Decimal(0)
    for kind, member_id, amount in rows:
        amount = Decimal(amount or 0)
        if member_id is None:
            unassigned += amount
        elif member_id != member.id:
            continue
        elif kind in lines:
            counted[lines[kind]] += amount
        else:
            not_counted[kind] = not_counted.get(kind, Decimal(0)) + amount
    return {
        "salary": counted["salary"].quantize(Q2),
        "other": counted["other"].quantize(Q2),
        "not_counted": [
            {"kind": kind, "amount": _money(amount)} for kind, amount in sorted(not_counted.items())
        ],
        "unassigned": _money(unassigned),
    }


def build_tax_items(
    db: Session,
    household_id: uuid.UUID,
    member: HouseholdMember,
    tax_year: str,
    *,
    salary_income: Decimal | None = None,
    other_income: Decimal | None = None,
) -> tuple[dict[str, Any], dt.date, set[uuid.UUID]]:
    """The figures a person needs for a return: wealth statement, income, tax deducted at
    source and rebate-eligible investments, each as this member's share.

    Salary and other income come from the income records (FR27.5) unless the person types
    them in; `income_basis` on the result says which."""
    start, end = tax_year_bounds(tax_year)
    as_of = min(end, today_dhaka())
    records = recorded_income(db, household_id, member, start, as_of)
    basis = {
        "salary": "ENTERED" if salary_income is not None else "RECORDS",
        "other": "ENTERED" if other_income is not None else "RECORDS",
        "not_counted": records["not_counted"],
        "unassigned": records["unassigned"],
    }
    salary_income = records["salary"] if salary_income is None else salary_income
    other_income = records["other"] if other_income is None else other_income
    portfolio = load_portfolio(db, household_id, as_of, active_only=False)
    n = len(portfolio.members)
    eligible = set(personal_config()["tax"]["rebate_eligible"])  # type: ignore[index]

    assets: list[dict[str, Any]] = []
    income = dict.fromkeys(("dividends", "profit", "rent", "capital_gains"), Decimal(0))
    tds_year, tds_recorded = Decimal(0), Decimal(0)
    tds_lines: list[dict[str, Any]] = []
    rebate: list[dict[str, Any]] = []

    for position in portfolio.positions:
        pct = position.ownership.member_pct(member.id, n)
        if pct <= 0:
            continue
        share = pct / HUNDRED
        holding, alt = position.holding, position.alt
        active = holding.is_active if holding is not None else bool(alt and alt.is_active)
        if active:
            assets.append(
                {
                    "label": position.name,
                    "category": position.asset_class,
                    "type": position.type,
                    "owner_pct": str(pct.quantize(Q2)),
                    "cost": _money(position.cost * share),
                    "value": _money(position.value * share),
                }
            )
        if holding is not None:
            tds_recorded += holding.tax_deducted * share
            transactions = list(
                db.scalars(select(Transaction).where(Transaction.holding_id == holding.id))
            )
            in_year = [t for t in transactions if start <= t.date <= as_of]
            invested = Decimal(0)
            holding_tds = Decimal(0)
            for row in in_year:
                if row.type == "DIVIDEND":
                    income["dividends"] += row.amount * share
                elif row.type == "PROFIT":
                    income["profit"] += row.amount * share
                elif row.type == "TAX":
                    holding_tds += row.amount * share
                elif row.type in ("BUY", "DEPOSIT"):
                    invested += row.amount * share
            trades = [
                Trade(t.date, t.type, t.amount, t.units or Decimal(0))
                for t in transactions
                if t.type in ("BUY", "SELL", "BONUS", "FEE")
            ]
            for day, gain in realised_gains(trades):
                if start <= day <= as_of:
                    income["capital_gains"] += gain * share
            if holding_tds:
                tds_year += holding_tds
                tds_lines.append({"label": holding.name, "amount": _money(holding_tds)})
            if invested and holding.instrument_type in eligible:
                rebate.append(
                    {
                        "label": holding.name,
                        "type": holding.instrument_type,
                        "amount": _money(invested),
                    }
                )
        elif alt is not None:
            for flow in db.scalars(
                select(CashFlow).where(
                    CashFlow.asset_id == alt.id, CashFlow.date >= start, CashFlow.date <= as_of
                )
            ):
                if flow.type == "RENT":
                    income["rent"] += flow.amount * share
                elif flow.type == "PROFIT_SHARE":
                    income["profit"] += flow.amount * share

    liabilities = []
    for debt in portfolio.debts:
        pct = debt.ownership.member_pct(member.id, n)
        if pct > 0 and debt.liability.is_active:
            liabilities.append(
                {
                    "label": debt.liability.name,
                    "type": debt.liability.type,
                    "owner_pct": str(pct.quantize(Q2)),
                    "outstanding": _money(debt.liability.outstanding * pct / HUNDRED),
                }
            )

    total_assets_cost = sum((Decimal(a["cost"]) for a in assets), Decimal(0))
    total_assets_value = sum((Decimal(a["value"]) for a in assets), Decimal(0))
    total_liabilities = sum((Decimal(x["outstanding"]) for x in liabilities), Decimal(0))
    income_lines = {
        "salary": _money(salary_income),
        **{key: _money(value) for key, value in income.items()},
        "other": _money(other_income),
    }
    items: dict[str, Any] = {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "assets": assets,
        "liabilities": liabilities,
        "totals": {
            "assets_cost": _money(total_assets_cost),
            "assets_value": _money(total_assets_value),
            "liabilities": _money(total_liabilities),
            "net_wealth_cost": _money(total_assets_cost - total_liabilities),
            "income": _money(sum((Decimal(v) for v in income_lines.values()), Decimal(0))),
        },
        "income": income_lines,
        "income_basis": basis,
        "tax_deducted": {
            "in_year": _money(tds_year),
            "recorded_on_holdings": _money(tds_recorded),
            "lines": tds_lines,
        },
        "rebate_eligible": rebate,
        "rebate_eligible_total": _money(sum((Decimal(r["amount"]) for r in rebate), Decimal(0))),
    }
    return items, as_of, portfolio.source_ids


def create_tax_snapshot(
    db: Session,
    household_id: uuid.UUID,
    member: HouseholdMember,
    tax_year: str,
    **inputs: Decimal | None,
) -> tuple[TaxSnapshot, set[uuid.UUID]]:
    items, as_of, sources = build_tax_items(db, household_id, member, tax_year, **inputs)
    snapshot = TaxSnapshot(member_id=member.id, tax_year=tax_year, as_of=as_of, items=items)
    db.add(snapshot)
    db.flush()
    return snapshot, sources


def list_tax_snapshots(db: Session, household_id: uuid.UUID) -> list[TaxSnapshot]:
    return list(
        db.scalars(
            select(TaxSnapshot)
            .where(TaxSnapshot.member_id.in_(_member_ids(db, household_id)))
            .order_by(TaxSnapshot.tax_year.desc(), TaxSnapshot.created_at.desc())
        )
    )


def get_tax_snapshot(db: Session, household_id: uuid.UUID, snapshot_id: uuid.UUID) -> TaxSnapshot:
    row = db.get(TaxSnapshot, snapshot_id)
    if row is None or row.member_id not in _member_ids(db, household_id):
        raise AuthError("NOT_FOUND", 404)
    return row


def tax_snapshot_csv(snapshot: TaxSnapshot) -> str:
    """The snapshot as CSV: one row per line of the wealth statement and income summary."""
    items = snapshot.items
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["section", "label", "type", "owner_pct", "cost", "value_or_amount"])
    for asset in items["assets"]:
        writer.writerow(
            [
                "asset",
                csv_safe(asset["label"]),
                asset["type"],
                asset["owner_pct"],
                asset["cost"],
                asset["value"],
            ]
        )
    for debt in items["liabilities"]:
        writer.writerow(
            [
                "liability",
                csv_safe(debt["label"]),
                debt["type"],
                debt["owner_pct"],
                "",
                debt["outstanding"],
            ]
        )
    for key, amount in items["income"].items():
        writer.writerow(["income", key, "", "", "", amount])
    for line in items["tax_deducted"]["lines"]:
        writer.writerow(
            ["tax_deducted_at_source", csv_safe(line["label"]), "", "", "", line["amount"]]
        )
    for line in items["rebate_eligible"]:
        writer.writerow(
            ["rebate_eligible", csv_safe(line["label"]), line["type"], "", "", line["amount"]]
        )
    for key, amount in items["totals"].items():
        writer.writerow(["total", key, "", "", "", amount])
    writer.writerow(["note", "Historical analysis for education only. Not investment advice."])
    writer.writerow(["note", "analysisACE does not file tax returns."])
    return out.getvalue()
