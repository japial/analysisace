"""Daily cost records (F12): categories, entries, recurring rules, totals, CSV.

Functions flush; the route commits.
"""

import csv
import datetime as dt
import io
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.analytics import costs as formulas
from app.models import Expense, ExpenseCategory, HouseholdMember, MacroSeries, RecurringRule
from app.services.auth import AuthError
from app.services.households import owned
from app.services.valuation import personal_config, today_dhaka

Q2 = Decimal("0.01")
MAX_AMOUNT = Decimal("999999999999.99")


# --- categories (FR12.1) --------------------------------------------------------------


def list_categories(db: Session, household_id: uuid.UUID) -> list[ExpenseCategory]:
    """The default categories followed by the household's own."""
    return list(
        db.scalars(
            select(ExpenseCategory)
            .where(
                or_(
                    ExpenseCategory.household_id.is_(None),
                    ExpenseCategory.household_id == household_id,
                )
            )
            .order_by(ExpenseCategory.sort_order, ExpenseCategory.name_en)
        )
    )


def _category(db: Session, household_id: uuid.UUID, category_id: uuid.UUID) -> ExpenseCategory:
    row = db.get(ExpenseCategory, category_id)
    if row is None or row.household_id not in (None, household_id):
        raise AuthError("CATEGORY_NOT_FOUND", 404)
    return row


def create_category(db: Session, household_id: uuid.UUID, name: str) -> ExpenseCategory:
    """A household's own category. The name is used as typed in both languages."""
    name = name.strip()
    key = re.sub(r"[^\w]+", "_", name.lower(), flags=re.UNICODE).strip("_")[:40] or "custom"
    for existing in list_categories(db, household_id):
        if existing.key == key or name.lower() in (
            existing.name_en.lower(),
            existing.name_bn.lower(),
        ):
            raise AuthError("CATEGORY_EXISTS", 409)
    row = ExpenseCategory(
        household_id=household_id, key=key, name_en=name, name_bn=name, sort_order=200
    )
    db.add(row)
    db.flush()
    return row


def delete_category(db: Session, household_id: uuid.UUID, category_id: uuid.UUID) -> None:
    row = db.get(ExpenseCategory, category_id)
    if row is None or row.household_id != household_id:
        raise AuthError("CATEGORY_NOT_FOUND", 404)
    used = db.scalar(select(func.count()).select_from(Expense).where(Expense.category_id == row.id))
    ruled = db.scalar(
        select(func.count()).select_from(RecurringRule).where(RecurringRule.category_id == row.id)
    )
    if used or ruled:
        raise AuthError("CATEGORY_IN_USE", 409)
    db.delete(row)
    db.flush()


# --- entries --------------------------------------------------------------------------


def _check_member(db: Session, household_id: uuid.UUID, member_id: uuid.UUID | None) -> None:
    if member_id is not None:
        owned(db, HouseholdMember, member_id, household_id)


def create_expense(
    db: Session,
    household_id: uuid.UUID,
    *,
    day: dt.date,
    amount: Decimal,
    category_id: uuid.UUID,
    note: str | None = None,
    member_id: uuid.UUID | None = None,
) -> Expense:
    _category(db, household_id, category_id)
    _check_member(db, household_id, member_id)
    row = Expense(
        household_id=household_id,
        member_id=member_id,
        date=day,
        amount=amount,
        category_id=category_id,
        note=(note or "").strip() or None,
    )
    db.add(row)
    db.flush()
    return row


def update_expense(
    db: Session, household_id: uuid.UUID, expense: Expense, changes: dict[str, Any]
) -> Expense:
    if changes.get("category_id") is not None:
        _category(db, household_id, changes["category_id"])
    if "member_id" in changes:
        _check_member(db, household_id, changes["member_id"])
    for name, value in changes.items():
        if name == "day":
            expense.date = value
        elif name == "note":
            expense.note = (value or "").strip() or None
        elif value is not None or name == "member_id":
            setattr(expense, name, value)
    db.flush()
    return expense


def list_expenses(
    db: Session,
    household_id: uuid.UUID,
    *,
    start: dt.date | None = None,
    end: dt.date | None = None,
    category_id: uuid.UUID | None = None,
    member_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Expense], int]:
    filters = [Expense.household_id == household_id]
    if start:
        filters.append(Expense.date >= start)
    if end:
        filters.append(Expense.date <= end)
    if category_id:
        filters.append(Expense.category_id == category_id)
    if member_id:
        filters.append(Expense.member_id == member_id)
    total = db.scalar(select(func.count()).select_from(Expense).where(*filters)) or 0
    rows = db.scalars(
        select(Expense)
        .where(*filters)
        .order_by(Expense.date.desc(), Expense.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total


# --- recurring rules (FR12.2) ---------------------------------------------------------


def create_rule(
    db: Session,
    household_id: uuid.UUID,
    *,
    category_id: uuid.UUID,
    amount: Decimal,
    frequency: str,
    start_date: dt.date,
    end_date: dt.date | None = None,
    note: str | None = None,
    member_id: uuid.UUID | None = None,
) -> RecurringRule:
    _category(db, household_id, category_id)
    _check_member(db, household_id, member_id)
    if frequency not in formulas.RECURRING_FREQUENCIES or (end_date and end_date < start_date):
        raise AuthError("VALIDATION", 422)
    rule = RecurringRule(
        household_id=household_id,
        member_id=member_id,
        category_id=category_id,
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


def update_rule(db: Session, rule: RecurringRule, changes: dict[str, Any]) -> RecurringRule:
    """Change a rule. Entries already generated stay as they are; later ones follow the rule."""
    if changes.get("category_id") is not None:
        _category(db, rule.household_id, changes["category_id"])
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

    Safe to run any number of times: an entry exists at most once per rule and date
    (FR12 acceptance criteria). Returns how many entries were added.
    """
    statement = select(RecurringRule).where(RecurringRule.is_active.is_(True))
    if household_id is not None:
        statement = statement.where(RecurringRule.household_id == household_id)
    added = 0
    for rule in db.scalars(statement):
        due = formulas.occurrences(rule.start_date, rule.frequency, until, rule.end_date)
        if not due:
            continue
        existing = set(db.scalars(select(Expense.date).where(Expense.recurring_id == rule.id)))
        for day in due:
            if day in existing:
                continue
            db.add(
                Expense(
                    household_id=rule.household_id,
                    member_id=rule.member_id,
                    date=day,
                    amount=rule.amount,
                    category_id=rule.category_id,
                    note=rule.note,
                    recurring_id=rule.id,
                )
            )
            added += 1
    db.flush()
    return added


# --- totals (FR12.3, FR12.4) ----------------------------------------------------------


@dataclass
class CostSummary:
    as_of: dt.date
    # [{month, total, real_total, by_category: {category_id: amount}}], oldest first.
    months: list[dict[str, Any]] = field(default_factory=list)
    years: list[dict[str, Any]] = field(default_factory=list)
    by_category: list[dict[str, Any]] = field(default_factory=list)
    trailing_12_months: Decimal = Decimal(0)
    # Month whose prices `real_total` is stated in; None when no CPI data is loaded.
    price_base_month: dt.date | None = None
    source_ids: set[uuid.UUID] = field(default_factory=set)


def cost_of_living(db: Session, household_id: uuid.UUID, as_of: dt.date) -> tuple[Decimal, int]:
    """(A year of spending, months with records), from the 12 months to `as_of`.

    Feeds the FIRE calculator (FR12.4). When fewer than 12 months have records, the average
    recorded month is scaled to a year, so a new household is not shown a FIRE number built
    on one month of costs.
    """
    first = formulas.add_months(as_of, -12) + dt.timedelta(days=1)
    rows = db.execute(
        select(Expense.date, Expense.amount).where(
            Expense.household_id == household_id, Expense.date >= first, Expense.date <= as_of
        )
    ).all()
    total = sum((amount for _, amount in rows), Decimal(0))
    months = min(len({formulas.month_start(day) for day, _ in rows}), 12)
    return formulas.annualised(total, months), months


def trailing_cost_of_living(db: Session, household_id: uuid.UUID, as_of: dt.date) -> Decimal:
    """A year of spending for the FIRE calculator (FR12.4); see `cost_of_living`."""
    return cost_of_living(db, household_id, as_of)[0]


def summary(
    db: Session, household_id: uuid.UUID, *, months: int = 24, as_of: dt.date | None = None
) -> CostSummary:
    as_of = as_of or today_dhaka()
    first = formulas.month_start(formulas.add_months(as_of, -(months - 1)))
    rows = db.execute(
        select(Expense.date, Expense.amount, Expense.category_id).where(
            Expense.household_id == household_id, Expense.date >= first, Expense.date <= as_of
        )
    ).all()
    result = CostSummary(as_of=as_of)
    totals = formulas.monthly_totals((day, amount) for day, amount, _ in rows)
    by_month_category: dict[dt.date, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    category_totals: dict[uuid.UUID, Decimal] = defaultdict(Decimal)
    year_totals: dict[int, Decimal] = defaultdict(Decimal)
    trailing_first = formulas.add_months(as_of, -12)
    for day, amount, category_id in rows:
        by_month_category[formulas.month_start(day)][str(category_id)] += amount
        year_totals[day.year] += amount
        if day > trailing_first:
            category_totals[category_id] += amount

    cpi_code = str(personal_config()["costs"]["cpi_series"])  # type: ignore[index]
    cpi = list(
        db.scalars(
            select(MacroSeries)
            .where(MacroSeries.series_code == cpi_code, MacroSeries.date <= as_of)
            .order_by(MacroSeries.date)
        )
    )
    real: dict[dt.date, Decimal] = {}
    if cpi and totals:
        index = formulas.price_index({formulas.month_start(r.date): r.value for r in cpi})
        result.price_base_month = max(index)
        real = formulas.in_prices_of(totals, index, result.price_base_month)
        result.source_ids = {r.source_id for r in cpi}

    result.months = [
        {
            "month": month,
            "total": total.quantize(Q2),
            "real_total": real.get(month),
            "by_category": {k: v.quantize(Q2) for k, v in by_month_category[month].items()},
        }
        for month, total in totals.items()
    ]
    result.years = [
        {"year": year, "total": total.quantize(Q2)} for year, total in sorted(year_totals.items())
    ]
    result.by_category = [
        {"category_id": category_id, "total": total.quantize(Q2)}
        for category_id, total in sorted(category_totals.items(), key=lambda item: -item[1])
    ]
    result.trailing_12_months = formulas.trailing_total(
        ((day, amount) for day, amount, _ in rows), as_of
    ).quantize(Q2)
    return result


# --- CSV (FR12.5) ---------------------------------------------------------------------

CSV_COLUMNS = ["date", "amount", "category", "note", "member"]


def export_csv(db: Session, household_id: uuid.UUID) -> str:
    categories = {c.id: c.key for c in list_categories(db, household_id)}
    members = dict(
        db.execute(
            select(HouseholdMember.id, HouseholdMember.display_name).where(
                HouseholdMember.household_id == household_id
            )
        ).all()
    )
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for row in db.scalars(
        select(Expense)
        .where(Expense.household_id == household_id)
        .order_by(Expense.date, Expense.created_at)
    ):
        writer.writerow(
            [
                row.date.isoformat(),
                str(row.amount),
                categories.get(row.category_id, ""),
                csv_safe(row.note or ""),
                csv_safe(members.get(row.member_id, "") if row.member_id else ""),
            ]
        )
    return out.getvalue()


def csv_safe(text: str) -> str:
    """Stops a spreadsheet from running a cell that starts like a formula."""
    return f"'{text}" if text[:1] in ("=", "+", "-", "@") else text


@dataclass
class ImportResult:
    imported: int = 0
    # [{row, code}] with the row number as a spreadsheet shows it (header is row 1).
    errors: list[dict[str, Any]] = field(default_factory=list)


def parse_amount(text: str) -> Decimal | None:
    """A positive taka amount from text such as "1,250.50". None when it is not one."""
    try:
        amount = Decimal(text.replace(",", "").replace("৳", "").strip())
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or amount <= 0 or amount > MAX_AMOUNT:
        return None
    return amount.quantize(Q2)


def parse_day(text: str) -> dt.date | None:
    text = text.strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(text, pattern).date()  # noqa: DTZ007 - a calendar day
        except ValueError:
            continue
    return None


def import_csv(db: Session, household_id: uuid.UUID, text: str) -> ImportResult:
    """Add costs from CSV with the columns date, amount, category and (optional) note.

    A category is matched by its key or its name in either language. A row that cannot be
    read is reported and skipped; the good rows are still imported.
    """
    result = ImportResult()
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    headers = {(h or "").strip().lower() for h in reader.fieldnames or []}
    if not {"date", "amount", "category"} <= headers:
        raise AuthError("CSV_HEADER_INVALID", 422)
    lookup: dict[str, uuid.UUID] = {}
    for category in list_categories(db, household_id):
        for label in (category.key, category.name_en, category.name_bn):
            lookup[label.strip().lower()] = category.id
    max_rows = int(personal_config()["costs"]["import_max_rows"])  # type: ignore[index]
    for number, raw in enumerate(reader, start=2):
        if number - 1 > max_rows:
            result.errors.append({"row": number, "code": "TOO_MANY_ROWS"})
            break
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        if not any(row.values()):
            continue
        day = parse_day(row.get("date", ""))
        amount = parse_amount(row.get("amount", ""))
        category_id = lookup.get(row.get("category", "").lower())
        if day is None:
            result.errors.append({"row": number, "code": "BAD_DATE"})
        elif amount is None:
            result.errors.append({"row": number, "code": "BAD_AMOUNT"})
        elif category_id is None:
            result.errors.append({"row": number, "code": "UNKNOWN_CATEGORY"})
        else:
            db.add(
                Expense(
                    household_id=household_id,
                    date=day,
                    amount=amount,
                    category_id=category_id,
                    note=row.get("note", "")[:300] or None,
                )
            )
            result.imported += 1
    db.flush()
    return result
