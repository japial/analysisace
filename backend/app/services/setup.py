"""Guided set-up of a new household (D22): a checklist of first steps, and a quick start
that records the basics in one go.

Functions flush; the route commits. Quick start only calls the services every other screen
uses, so what it creates is ordinary data the person can change or delete afterwards.
"""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics import costs as formulas
from app.models import (
    Account,
    AltAsset,
    Expense,
    ExpenseCategory,
    FirePlan,
    Holding,
    HouseholdMember,
    IncomeEntry,
    IncomeRule,
    RecurringRule,
)
from app.models.enums import AccountType
from app.services import costs, income, portfolio
from app.services.auth import AuthError
from app.services.valuation import personal_config, today_dhaka

STEPS = ("you", "income", "costs", "savings", "plan")


def _config() -> dict[str, Any]:
    config = personal_config()["setup"]
    assert isinstance(config, dict)
    return config


def _exists(db: Session, statement: Any) -> bool:
    return bool(db.scalar(select(func.count()).select_from(statement.subquery())))


def status(db: Session, household_id: uuid.UUID, member: HouseholdMember) -> dict[str, Any]:
    """Which first steps the household has done, each read from its own records."""
    done = {
        "you": member.birth_year is not None,
        "income": _exists(
            db, select(IncomeEntry.id).where(IncomeEntry.household_id == household_id)
        )
        or _exists(db, select(IncomeRule.id).where(IncomeRule.household_id == household_id)),
        "costs": _exists(db, select(Expense.id).where(Expense.household_id == household_id))
        or _exists(db, select(RecurringRule.id).where(RecurringRule.household_id == household_id)),
        "savings": _exists(
            db,
            select(Holding.id)
            .join(Account, Account.id == Holding.account_id)
            .where(Account.household_id == household_id),
        )
        or _exists(db, select(AltAsset.id).where(AltAsset.household_id == household_id)),
        "plan": _exists(db, select(FirePlan.id).where(FirePlan.household_id == household_id)),
    }
    steps = [{"key": key, "done": done[key]} for key in STEPS]
    count = sum(1 for s in steps if s["done"])
    return {
        "steps": steps,
        "done": count,
        "total": len(steps),
        "complete": count == len(steps),
        "fixed_categories": list(_config()["fixed_cost_categories"]),
        "variable_categories": list(_config()["variable_cost_categories"]),
        "savings_kinds": list(_config()["savings"]),
    }


def quick_start(
    db: Session,
    household_id: uuid.UUID,
    member: HouseholdMember,
    *,
    birth_year: int | None,
    monthly_income: Decimal | None,
    costs_by_category: dict[str, Decimal],
    savings: dict[str, Decimal],
    locale: str = "en",
) -> dict[str, int]:
    """Record the basics in one transaction and say how many rows each part made.

    Income and fixed costs become monthly rules from the first of this month, so this month
    already has entries and the savings rate shows at once. Day-to-day costs are entered once,
    today, as this month's estimate. Savings become one account and one holding per kind.
    """
    config = _config()
    fixed = set(config["fixed_cost_categories"])
    variable = set(config["variable_cost_categories"])
    unknown = set(costs_by_category) - fixed - variable
    kinds: dict[str, dict[str, str]] = config["savings"]
    if unknown or set(savings) - set(kinds):
        raise AuthError("VALIDATION", 422)
    today = today_dhaka()
    if birth_year is not None and not today.year - 100 <= birth_year <= today.year - 15:
        raise AuthError("VALIDATION", 422)

    made = {"income_rules": 0, "cost_rules": 0, "cost_entries": 0, "holdings": 0}
    if birth_year is not None:
        member.birth_year = birth_year
    month_start = formulas.month_start(today)
    lang = "bn" if locale == "bn" else "en"
    note = str(config["note"][lang])

    if monthly_income:
        income.create_rule(
            db,
            household_id,
            kind=str(config["income_kind"]),
            amount=monthly_income,
            frequency="MONTHLY",
            start_date=month_start,
            note=note,
            member_id=member.id,
        )
        made["income_rules"] += 1

    category_ids = {
        c.key: c.id
        for c in db.scalars(select(ExpenseCategory).where(ExpenseCategory.household_id.is_(None)))
    }
    for key, amount in costs_by_category.items():
        if not amount:
            continue
        if key not in category_ids:
            raise AuthError("VALIDATION", 422)
        if key in fixed:
            costs.create_rule(
                db,
                household_id,
                category_id=category_ids[key],
                amount=amount,
                frequency="MONTHLY",
                start_date=month_start,
                note=note,
                member_id=member.id,
            )
            made["cost_rules"] += 1
        else:
            costs.create_expense(
                db,
                household_id,
                day=today,
                amount=amount,
                category_id=category_ids[key],
                note=note,
                member_id=member.id,
            )
            made["cost_entries"] += 1

    for key, amount in savings.items():
        if not amount:
            continue
        kind = kinds[key]
        account = portfolio.create_account(
            db,
            household_id,
            type=AccountType(kind["account"]),
            institution=note,
            name=kind[f"name_{lang}"],
        )
        portfolio.create_holding(
            db,
            household_id,
            account,
            {
                "instrument_type": kind["instrument"],
                "name": kind[f"name_{lang}"],
                "cost": amount,
                "manual_value": amount,
                "start_date": today,
            },
        )
        made["holdings"] += 1
    db.flush()
    return made
