"""Export and deletion of everything a household holds (FR23.4).

Most tables hang off `household` with ON DELETE CASCADE, so deleting the household row
removes them. `owner_share` and `valuation` point at several kinds of asset and so have no
foreign key; they are removed here explicitly.

When a table with personal data is added, add it to `_HOUSEHOLD_TABLES` or `_CHILD_TABLES`.
"""

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    AltAsset,
    Base,
    CashFlow,
    Document,
    Expense,
    ExpenseCategory,
    FirePlan,
    Goal,
    Holding,
    Household,
    HouseholdMember,
    Liability,
    NetWorthSnapshot,
    OwnerShare,
    RecurringRule,
    ScenarioResult,
    TargetAllocation,
    TaxSnapshot,
    Transaction,
    Valuation,
    ZakatSnapshot,
)

# Tables with a `household_id` column.
_HOUSEHOLD_TABLES: list[type[Base]] = [
    HouseholdMember,
    Account,
    AltAsset,
    Liability,
    ExpenseCategory,
    RecurringRule,
    Expense,
    Goal,
    TargetAllocation,
    FirePlan,
    NetWorthSnapshot,
]
# (table, parent column on the table, parent table): rows reached through a parent.
_CHILD_TABLES: list[tuple[type[Base], str, type[Base]]] = [
    (Holding, "account_id", Account),
    (Transaction, "holding_id", Holding),
    (CashFlow, "asset_id", AltAsset),
    (Document, "asset_id", AltAsset),
    (ZakatSnapshot, "member_id", HouseholdMember),
    (TaxSnapshot, "member_id", HouseholdMember),
    (ScenarioResult, "fire_plan_id", FirePlan),
]
# Never exported, even to the owner: ciphertext and storage keys are useless outside the app.
_HIDDEN_COLUMNS = {"encrypted_number", "encrypted_blob_ref"}


def _plain(value: Any) -> Any:
    if isinstance(value, Decimal | uuid.UUID):
        return str(value)
    if isinstance(value, dt.datetime | dt.date):
        return value.isoformat()
    return value


def _row(obj: Base) -> dict[str, Any]:
    return {
        column.name: _plain(getattr(obj, column.name))
        for column in obj.__table__.columns
        if column.name not in _HIDDEN_COLUMNS
    }


def _ids(db: Session, model: type[Base], household_id: uuid.UUID) -> list[uuid.UUID]:
    return list(db.scalars(select(model.id).where(model.household_id == household_id)))  # type: ignore[attr-defined]


def _asset_ids(db: Session, household_id: uuid.UUID) -> list[uuid.UUID]:
    """Ids of everything an owner share or valuation can point at."""
    account_ids = _ids(db, Account, household_id)
    holding_ids = list(db.scalars(select(Holding.id).where(Holding.account_id.in_(account_ids))))
    return holding_ids + _ids(db, AltAsset, household_id) + _ids(db, Liability, household_id)


def export_household(db: Session, household_id: uuid.UUID) -> dict[str, Any]:
    """Every row belonging to a household, keyed by table name."""
    household = db.get(Household, household_id)
    if household is None:
        return {}
    data: dict[str, Any] = {"household": _row(household)}
    rows_by_model: dict[type[Base], list[Base]] = {}
    for model in _HOUSEHOLD_TABLES:
        rows = list(db.scalars(select(model).where(model.household_id == household_id)))  # type: ignore[attr-defined]
        rows_by_model[model] = rows
        data[model.__tablename__] = [_row(r) for r in rows]
    for model, parent_column, parent in _CHILD_TABLES:
        parent_ids = [r.id for r in rows_by_model.get(parent, [])]  # type: ignore[attr-defined]
        rows = list(db.scalars(select(model).where(getattr(model, parent_column).in_(parent_ids))))
        rows_by_model[model] = rows
        data[model.__tablename__] = [_row(r) for r in rows]
    asset_ids = _asset_ids(db, household_id)
    for model in (OwnerShare, Valuation):
        rows = list(db.scalars(select(model).where(model.asset_id.in_(asset_ids))))
        data[model.__tablename__] = [_row(r) for r in rows]
    return data


def delete_household(db: Session, household_id: uuid.UUID) -> None:
    """Remove a household and everything in it."""
    asset_ids = _asset_ids(db, household_id)
    db.execute(delete(OwnerShare).where(OwnerShare.asset_id.in_(asset_ids)))
    db.execute(delete(Valuation).where(Valuation.asset_id.in_(asset_ids)))
    # Costs reference categories without a cascade, so they go first.
    db.execute(delete(Expense).where(Expense.household_id == household_id))
    db.execute(delete(RecurringRule).where(RecurringRule.household_id == household_id))
    db.execute(delete(Household).where(Household.id == household_id))
    db.flush()


def households_of(db: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        db.scalars(select(HouseholdMember.household_id).where(HouseholdMember.user_id == user_id))
    )


def has_other_login(db: Session, household_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """True when someone else can still sign in to this household."""
    others = db.scalar(
        select(func.count())
        .select_from(HouseholdMember)
        .where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.user_id.is_not(None),
            HouseholdMember.user_id != user_id,
        )
    )
    return bool(others)
