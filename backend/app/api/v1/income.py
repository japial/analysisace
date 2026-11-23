"""Income records and savings (F27)."""

import datetime as dt
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import select

from app.api.deps import Db, Editor, Viewer
from app.api.envelopes import computed
from app.api.v1.households import no_content
from app.models import IncomeEntry, IncomeRule
from app.schemas.common import Envelope, Page
from app.schemas.personal import (
    IncomeIn,
    IncomeOut,
    IncomeRuleIn,
    IncomeRuleOut,
    IncomeRuleUpdateIn,
    IncomeUpdateIn,
)
from app.services import income
from app.services.households import owned

router = APIRouter(prefix="/households/{household_id}", tags=["income"])


@router.get("/income")
def list_income(
    access: Viewer,
    db: Db,
    start: dt.date | None = None,
    end: dt.date | None = None,
    kind: str | None = None,
    member_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[IncomeOut]:
    rows, total = income.list_entries(
        db,
        access.household.id,
        start=start,
        end=end,
        kind=kind,
        member_id=member_id,
        limit=limit,
        offset=offset,
    )
    return Page[IncomeOut](
        items=[IncomeOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset
    )


@router.post("/income", status_code=status.HTTP_201_CREATED)
def create_income(body: IncomeIn, access: Editor, db: Db) -> IncomeOut:
    """FR27.1: amount, kind, date and an optional note."""
    row = income.create_entry(
        db,
        access.household.id,
        day=body.date,
        amount=body.amount,
        kind=body.kind,
        note=body.note,
        member_id=body.member_id or access.member.id,
    )
    db.commit()
    return IncomeOut.model_validate(row)


@router.patch("/income/{income_id}")
def update_income(income_id: uuid.UUID, body: IncomeUpdateIn, access: Editor, db: Db) -> IncomeOut:
    row = owned(db, IncomeEntry, income_id, access.household.id)
    changes = body.model_dump(exclude_unset=True)
    if "date" in changes:
        changes["day"] = changes.pop("date")
    income.update_entry(db, access.household.id, row, changes)
    db.commit()
    return IncomeOut.model_validate(row)


@router.delete("/income/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_income(income_id: uuid.UUID, access: Editor, db: Db) -> Response:
    db.delete(owned(db, IncomeEntry, income_id, access.household.id))
    db.commit()
    return no_content()


@router.get("/income-rules")
def list_income_rules(access: Viewer, db: Db) -> list[IncomeRuleOut]:
    rows = db.scalars(
        select(IncomeRule)
        .where(IncomeRule.household_id == access.household.id)
        .order_by(IncomeRule.created_at)
    )
    return [IncomeRuleOut.model_validate(r) for r in rows]


@router.post("/income-rules", status_code=status.HTTP_201_CREATED)
def create_income_rule(body: IncomeRuleIn, access: Editor, db: Db) -> IncomeRuleOut:
    """FR27.2: income that repeats. Entries already due are written at once."""
    rule = income.create_rule(
        db,
        access.household.id,
        **{**body.model_dump(), "member_id": body.member_id or access.member.id},
    )
    db.commit()
    return IncomeRuleOut.model_validate(rule)


@router.patch("/income-rules/{rule_id}")
def update_income_rule(
    rule_id: uuid.UUID, body: IncomeRuleUpdateIn, access: Editor, db: Db
) -> IncomeRuleOut:
    rule = owned(db, IncomeRule, rule_id, access.household.id)
    income.update_rule(db, rule, body.model_dump(exclude_unset=True))
    db.commit()
    return IncomeRuleOut.model_validate(rule)


@router.delete("/income-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_income_rule(rule_id: uuid.UUID, access: Editor, db: Db) -> Response:
    """Stops the rule. Entries it already wrote are kept."""
    db.delete(owned(db, IncomeRule, rule_id, access.household.id))
    db.commit()
    return no_content()


@router.get("/income/summary")
def income_summary(
    access: Viewer, db: Db, months: Annotated[int, Query(ge=1, le=120)] = 24
) -> Envelope[dict[str, Any]]:
    """FR27.3: income, costs and savings by month, the trailing 12 months, income by kind and
    the savings rate. `kinds` lists the income kinds the household may record."""
    result = income.summary(db, access.household.id, months=months)
    data = {
        "as_of_date": result.as_of,
        "kinds": income.kinds(),
        "months": result.months,
        "by_kind": result.by_kind,
        "income_12m": result.income_12m,
        "costs_12m": result.costs_12m,
        "savings_12m": result.savings_12m,
        "savings_rate_pct": result.savings_rate_pct,
        "months_counted": result.months_counted,
        "average_monthly_income": result.average_monthly_income,
        "average_monthly_savings": result.average_monthly_savings,
    }
    return computed(db, data, ())
