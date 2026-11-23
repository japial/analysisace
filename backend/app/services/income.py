"""Income records (F27): entries, recurring income, monthly totals and savings.

Functions flush; the route commits. Income and costs together give what a household
saves (FR27.3): savings = income - costs, rate = savings / income.
"""

import datetime as dt
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics import costs as formulas
from app.models import Expense, HouseholdMember, IncomeEntry, IncomeRule
from app.services.auth import AuthError
from app.services.households import owned
from app.services.valuation import personal_config, today_dhaka

Q2 = Decimal("0.01")
HUNDRED = Decimal(100)


def kinds() -> list[str]:
    return [str(k) for k in personal_config()["income"]["kinds"]]  # type: ignore[index]


def _check(
    db: Session, household_id: uuid.UUID, kind: str | None, member_id: uuid.UUID | None
) -> None:
    if kind is not None and kind not in kinds():
        raise AuthError("VALIDATION", 422)
    if member_id is not None:
        owned(db, HouseholdMember, member_id, household_id)


def create_entry(
    db: Session,
    household_id: uuid.UUID,
    *,
    day: dt.date,
    amount: Decimal,
    kind: str,
    note: str | None = None,
    member_id: uuid.UUID | None = None,
) -> IncomeEntry:
    _check(db, household_id, kind, member_id)
    row = IncomeEntry(
        household_id=household_id,
        member_id=member_id,
        date=day,
        amount=amount,
        kind=kind,
        note=(note or "").strip() or None,
    )
    db.add(row)
    db.flush()
    return row


def update_entry(
    db: Session, household_id: uuid.UUID, row: IncomeEntry, changes: dict[str, Any]
) -> IncomeEntry:
    _check(db, household_id, changes.get("kind"), changes.get("member_id"))
    for name, value in changes.items():
        if name == "day":
            row.date = value
        elif name == "note":
            row.note = (value or "").strip() or None
        elif value is not None or name == "member_id":
            setattr(row, name, value)
    db.flush()
    return row


def list_entries(
    db: Session,
    household_id: uuid.UUID,
    *,
    start: dt.date | None = None,
    end: dt.date | None = None,
    kind: str | None = None,
    member_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[IncomeEntry], int]:
    filters = [IncomeEntry.household_id == household_id]
    if start:
        filters.append(IncomeEntry.date >= start)
    if end:
        filters.append(IncomeEntry.date <= end)
    if kind:
        filters.append(IncomeEntry.kind == kind)
    if member_id:
        filters.append(IncomeEntry.member_id == member_id)
    total = db.scalar(select(func.count()).select_from(IncomeEntry).where(*filters)) or 0
    rows = db.scalars(
        select(IncomeEntry)
        .where(*filters)
        .order_by(IncomeEntry.date.desc(), IncomeEntry.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total


# --- recurring income (FR27.2) --------------------------------------------------------


def create_rule(
    db: Session,
    household_id: uuid.UUID,
    *,
    kind: str,
    amount: Decimal,
    frequency: str,
    start_date: dt.date,
    end_date: dt.date | None = None,
    note: str | None = None,
    member_id: uuid.UUID | None = None,
) -> IncomeRule:
    _check(db, household_id, kind, member_id)
    if frequency not in formulas.RECURRING_FREQUENCIES or (end_date and end_date < start_date):
        raise AuthError("VALIDATION", 422)
    rule = IncomeRule(
        household_id=household_id,
        member_id=member_id,
        kind=kind,
        amount=amount,
        note=(note or "").strip() or None,
        frequency=frequency,
        start_date=start_date,
        end_date=end_date,
    )
    db.add(rule)
    db.flush()
    generate_recurring(db, today_dhaka(), household_id=household_id)
    return rule


def update_rule(db: Session, rule: IncomeRule, changes: dict[str, Any]) -> IncomeRule:
    """Change a rule. Entries already generated stay as they are; later ones follow the rule."""
    _check(db, rule.household_id, changes.get("kind"), None)
    for name, value in changes.items():
        if name in ("end_date", "note") or value is not None:
            setattr(rule, name, value)
    if rule.end_date and rule.end_date < rule.start_date:
        raise AuthError("VALIDATION", 422)
    db.flush()
    generate_recurring(db, today_dhaka(), household_id=rule.household_id)
    return rule


def generate_recurring(
    db: Session, until: dt.date, *, household_id: uuid.UUID | None = None
) -> int:
    """Write the entries that active rules have fallen due for, up to `until`.

    Safe to run any number of times: an entry exists at most once per rule and date.
    Returns how many entries were added.
    """
    statement = select(IncomeRule).where(IncomeRule.is_active.is_(True))
    if household_id is not None:
        statement = statement.where(IncomeRule.household_id == household_id)
    added = 0
    for rule in db.scalars(statement):
        due = formulas.occurrences(rule.start_date, rule.frequency, until, rule.end_date)
        if not due:
            continue
        existing = set(
            db.scalars(select(IncomeEntry.date).where(IncomeEntry.recurring_id == rule.id))
        )
        for day in due:
            if day in existing:
                continue
            db.add(
                IncomeEntry(
                    household_id=rule.household_id,
                    member_id=rule.member_id,
                    date=day,
                    amount=rule.amount,
                    kind=rule.kind,
                    note=rule.note,
                    recurring_id=rule.id,
                )
            )
            added += 1
    db.flush()
    return added


# --- totals and savings (FR27.3) ------------------------------------------------------


@dataclass
class IncomeSummary:
    as_of: dt.date
    # [{month, income, costs, savings}], oldest first, over the months asked for.
    months: list[dict[str, Any]] = field(default_factory=list)
    by_kind: list[dict[str, Any]] = field(default_factory=list)
    # Trailing 12 months.
    income_12m: Decimal = Decimal(0)
    costs_12m: Decimal = Decimal(0)
    savings_12m: Decimal = Decimal(0)
    savings_rate_pct: Decimal | None = None
    # Averages per month over the months with any income or cost record in those 12 months.
    months_counted: int = 0
    average_monthly_income: Decimal | None = None
    average_monthly_savings: Decimal | None = None


def summary(
    db: Session, household_id: uuid.UUID, *, months: int = 24, as_of: dt.date | None = None
) -> IncomeSummary:
    as_of = as_of or today_dhaka()
    first = formulas.month_start(formulas.add_months(as_of, -(max(months, 12) - 1)))
    income_rows = db.execute(
        select(IncomeEntry.date, IncomeEntry.amount, IncomeEntry.kind).where(
            IncomeEntry.household_id == household_id,
            IncomeEntry.date >= first,
            IncomeEntry.date <= as_of,
        )
    ).all()
    cost_rows = db.execute(
        select(Expense.date, Expense.amount).where(
            Expense.household_id == household_id, Expense.date >= first, Expense.date <= as_of
        )
    ).all()
    income_by_month = formulas.monthly_totals((d, a) for d, a, _ in income_rows)
    cost_by_month = formulas.monthly_totals((d, a) for d, a in cost_rows)

    result = IncomeSummary(as_of=as_of)
    for month in sorted(set(income_by_month) | set(cost_by_month)):
        income = income_by_month.get(month, Decimal(0)).quantize(Q2)
        spent = cost_by_month.get(month, Decimal(0)).quantize(Q2)
        result.months.append(
            {"month": month, "income": income, "costs": spent, "savings": income - spent}
        )

    # The trailing window is the 12 months ending with the month of `as_of`.
    window_first = formulas.month_start(formulas.add_months(as_of, -11))
    window = [m for m in result.months if m["month"] >= window_first]
    result.months_counted = len(window)
    result.income_12m = sum((m["income"] for m in window), Decimal(0)).quantize(Q2)
    result.costs_12m = sum((m["costs"] for m in window), Decimal(0)).quantize(Q2)
    result.savings_12m = result.income_12m - result.costs_12m
    if result.income_12m > 0:
        result.savings_rate_pct = (result.savings_12m / result.income_12m * HUNDRED).quantize(Q2)
    if window:
        result.average_monthly_income = (result.income_12m / len(window)).quantize(Q2)
        result.average_monthly_savings = (result.savings_12m / len(window)).quantize(Q2)

    by_kind: dict[str, Decimal] = defaultdict(Decimal)
    for day, amount, kind in income_rows:
        if day >= window_first:
            by_kind[kind] += amount
    result.by_kind = [
        {"kind": kind, "total": total.quantize(Q2)}
        for kind, total in sorted(by_kind.items(), key=lambda item: -item[1])
    ]
    return result
