"""Guided set-up of a new household (D22)."""

from typing import Any

from fastapi import APIRouter, status

from app.api.deps import Db, Editor, Viewer
from app.schemas.personal import QuickStartIn
from app.services import setup

router = APIRouter(prefix="/households/{household_id}", tags=["setup"])


@router.get("/setup/status")
def setup_status(access: Viewer, db: Db) -> dict[str, Any]:
    """The first steps (your birth year, income, costs, savings, a FIRE plan) and which are
    done, read from the household's records. Also the categories and savings kinds the
    quick start form asks about."""
    return setup.status(db, access.household.id, access.member)


@router.post("/setup/quick-start", status_code=status.HTTP_201_CREATED)
def quick_start(body: QuickStartIn, access: Editor, db: Db) -> dict[str, Any]:
    """Record the basics in one go: birth year, monthly income as a rule, fixed costs as
    rules, day-to-day costs as this month's estimate, and savings held today."""
    made = setup.quick_start(
        db,
        access.household.id,
        access.member,
        birth_year=body.birth_year,
        monthly_income=body.monthly_income,
        costs_by_category=body.costs,
        savings=body.savings,
        locale=body.locale,
    )
    db.commit()
    return {"made": made, **setup.status(db, access.household.id, access.member)}
