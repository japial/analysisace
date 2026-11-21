"""Daily cost records (F12)."""

import datetime as dt
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import select

from app.api.deps import Db, Editor, Viewer
from app.api.envelopes import computed
from app.api.v1.households import no_content
from app.models import Expense, ExpenseCategory, RecurringRule
from app.schemas.common import Envelope, Page
from app.schemas.personal import (
    CategoryIn,
    CategoryOut,
    CsvIn,
    ExpenseIn,
    ExpenseOut,
    ExpenseUpdateIn,
    ImportOut,
    RecurringIn,
    RecurringOut,
    RecurringUpdateIn,
)
from app.services import costs
from app.services.households import owned

router = APIRouter(prefix="/households/{household_id}", tags=["costs"])


def _category_out(row: ExpenseCategory) -> CategoryOut:
    return CategoryOut(
        id=row.id,
        key=row.key,
        name_en=row.name_en,
        name_bn=row.name_bn,
        is_default=row.household_id is None,
    )


@router.get("/categories")
def list_categories(access: Viewer, db: Db) -> list[CategoryOut]:
    return [_category_out(c) for c in costs.list_categories(db, access.household.id)]


@router.post("/categories", status_code=status.HTTP_201_CREATED)
def create_category(body: CategoryIn, access: Editor, db: Db) -> CategoryOut:
    row = costs.create_category(db, access.household.id, body.name)
    db.commit()
    return _category_out(row)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: uuid.UUID, access: Editor, db: Db) -> Response:
    costs.delete_category(db, access.household.id, category_id)
    db.commit()
    return no_content()


@router.get("/expenses")
def list_expenses(
    access: Viewer,
    db: Db,
    start: dt.date | None = None,
    end: dt.date | None = None,
    category_id: uuid.UUID | None = None,
    member_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ExpenseOut]:
    rows, total = costs.list_expenses(
        db,
        access.household.id,
        start=start,
        end=end,
        category_id=category_id,
        member_id=member_id,
        limit=limit,
        offset=offset,
    )
    return Page[ExpenseOut](
        items=[ExpenseOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset
    )


@router.post("/expenses", status_code=status.HTTP_201_CREATED)
def create_expense(body: ExpenseIn, access: Editor, db: Db) -> ExpenseOut:
    """FR12.1: amount, category, date and an optional note."""
    row = costs.create_expense(
        db,
        access.household.id,
        day=body.date,
        amount=body.amount,
        category_id=body.category_id,
        note=body.note,
        member_id=body.member_id or access.member.id,
    )
    db.commit()
    return ExpenseOut.model_validate(row)


@router.patch("/expenses/{expense_id}")
def update_expense(
    expense_id: uuid.UUID, body: ExpenseUpdateIn, access: Editor, db: Db
) -> ExpenseOut:
    row = owned(db, Expense, expense_id, access.household.id)
    changes = body.model_dump(exclude_unset=True)
    if "date" in changes:
        changes["day"] = changes.pop("date")
    costs.update_expense(db, access.household.id, row, changes)
    db.commit()
    return ExpenseOut.model_validate(row)


@router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: uuid.UUID, access: Editor, db: Db) -> Response:
    db.delete(owned(db, Expense, expense_id, access.household.id))
    db.commit()
    return no_content()


@router.get("/recurring")
def list_recurring(access: Viewer, db: Db) -> list[RecurringOut]:
    rows = db.scalars(
        select(RecurringRule)
        .where(RecurringRule.household_id == access.household.id)
        .order_by(RecurringRule.created_at)
    )
    return [RecurringOut.model_validate(r) for r in rows]


@router.post("/recurring", status_code=status.HTTP_201_CREATED)
def create_recurring(body: RecurringIn, access: Editor, db: Db) -> RecurringOut:
    """FR12.2: a cost that repeats. Entries already due are written at once."""
    rule = costs.create_rule(db, access.household.id, **body.model_dump())
    db.commit()
    return RecurringOut.model_validate(rule)


@router.patch("/recurring/{rule_id}")
def update_recurring(
    rule_id: uuid.UUID, body: RecurringUpdateIn, access: Editor, db: Db
) -> RecurringOut:
    rule = owned(db, RecurringRule, rule_id, access.household.id)
    costs.update_rule(db, rule, body.model_dump(exclude_unset=True))
    db.commit()
    return RecurringOut.model_validate(rule)


@router.delete("/recurring/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recurring(rule_id: uuid.UUID, access: Editor, db: Db) -> Response:
    """Stops the rule. Entries it already wrote are kept."""
    db.delete(owned(db, RecurringRule, rule_id, access.household.id))
    db.commit()
    return no_content()


@router.get("/costs/summary")
def cost_summary(
    access: Viewer, db: Db, months: Annotated[int, Query(ge=1, le=120)] = 24
) -> Envelope[dict[str, Any]]:
    """Monthly and yearly totals, category totals, the trailing 12 months, and each
    month restated in the latest month's prices using BBS CPI (FR12.3, FR12.4)."""
    result = costs.summary(db, access.household.id, months=months)
    data = {
        "as_of_date": result.as_of,
        "months": result.months,
        "years": result.years,
        "by_category": result.by_category,
        "trailing_12_months": result.trailing_12_months,
        "price_base_month": result.price_base_month,
    }
    return computed(db, data, result.source_ids)


@router.get("/costs/export.csv")
def export_costs(access: Viewer, db: Db) -> Response:
    """FR12.5: every cost entry as CSV."""
    return Response(
        costs.export_csv(db, access.household.id),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="analysisace-costs.csv"'},
    )


@router.post("/imports/expenses")
def import_costs(body: CsvIn, access: Editor, db: Db) -> ImportOut:
    """FR12.5: add costs from CSV (columns: date, amount, category, note)."""
    result = costs.import_csv(db, access.household.id, body.csv)
    db.commit()
    return ImportOut(imported=result.imported, errors=result.errors)
