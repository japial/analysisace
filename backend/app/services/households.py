"""Households, members, roles and owner shares (F24).

Every personal finance row hangs off a household, so access is one check: is the user a
member, and is their role high enough. Roles are OWNER, EDITOR and VIEWER (FR24.2).
Functions flush; the route commits.
"""

import datetime as dt
import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import Base, Household, HouseholdMember, OwnerShare, User
from app.models.enums import HouseholdRole
from app.services import household_data
from app.services.auth import AuthError, ConsentPurpose, audit, get_user_by_email

HUNDRED = Decimal(100)
_RANK = {HouseholdRole.VIEWER: 0, HouseholdRole.EDITOR: 1, HouseholdRole.OWNER: 2}


@dataclass(frozen=True)
class Access:
    """A signed-in user's place in one household."""

    user: User
    household: Household
    member: HouseholdMember

    @property
    def role(self) -> HouseholdRole:
        return HouseholdRole(self.member.role)

    def has(self, role: HouseholdRole) -> bool:
        return _RANK[self.role] >= _RANK[role]


def get_access(db: Session, user: User, household_id: uuid.UUID) -> Access:
    """The user's membership, or 404. A household the user is not in looks like no household,
    so ids cannot be probed."""
    member = db.scalar(
        select(HouseholdMember).where(
            HouseholdMember.household_id == household_id, HouseholdMember.user_id == user.id
        )
    )
    household = db.get(Household, household_id) if member else None
    if member is None or household is None:
        raise AuthError("HOUSEHOLD_NOT_FOUND", 404)
    return Access(user=user, household=household, member=member)


def require_role(access: Access, role: HouseholdRole) -> None:
    if not access.has(role):
        raise AuthError("HOUSEHOLD_ROLE_REQUIRED", 403)


def has_consent(user: User, purpose: ConsentPurpose) -> bool:
    return bool(((user.consents or {}).get(purpose.value) or {}).get("granted", False))


def require_consent(user: User, purpose: ConsentPurpose) -> None:
    """FR23.2: religious preferences are stored only with separate, explicit consent."""
    if not has_consent(user, purpose):
        raise AuthError("CONSENT_REQUIRED", 403)


def owned[M: Base](db: Session, model: type[M], row_id: uuid.UUID, household_id: uuid.UUID) -> M:
    """A row of `model` that belongs to the household, or 404."""
    row = db.get(model, row_id)
    if row is None or getattr(row, "household_id", None) != household_id:
        raise AuthError("NOT_FOUND", 404)
    return row


# --- households -----------------------------------------------------------------------


def list_households(db: Session, user: User) -> list[tuple[Household, HouseholdMember]]:
    rows = db.execute(
        select(Household, HouseholdMember)
        .join(HouseholdMember, HouseholdMember.household_id == Household.id)
        .where(HouseholdMember.user_id == user.id)
        .order_by(Household.created_at)
    ).all()
    return [(household, member) for household, member in rows]


def create_household(db: Session, user: User, name: str) -> tuple[Household, HouseholdMember]:
    household = Household(name=name.strip(), created_by=user.id)
    db.add(household)
    db.flush()
    member = HouseholdMember(
        household_id=household.id,
        user_id=user.id,
        display_name=user.full_name,
        role=HouseholdRole.OWNER.value,
    )
    db.add(member)
    db.flush()
    audit(db, str(user.id), "HOUSEHOLD_CREATED", "household", str(household.id))
    return household, member


def delete_household(db: Session, access: Access) -> None:
    require_role(access, HouseholdRole.OWNER)
    household_data.delete_household(db, access.household.id)
    audit(db, str(access.user.id), "HOUSEHOLD_DELETED", "household", str(access.household.id))


# --- members --------------------------------------------------------------------------


def list_members(db: Session, household_id: uuid.UUID) -> list[HouseholdMember]:
    return list(
        db.scalars(
            select(HouseholdMember)
            .where(HouseholdMember.household_id == household_id)
            .order_by(HouseholdMember.created_at, HouseholdMember.display_name)
        )
    )


def get_member(db: Session, household_id: uuid.UUID, member_id: uuid.UUID) -> HouseholdMember:
    return owned(db, HouseholdMember, member_id, household_id)


def _owner_count(db: Session, household_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(HouseholdMember)
            .where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.role == HouseholdRole.OWNER.value,
                HouseholdMember.user_id.is_not(None),
            )
        )
        or 0
    )


def add_member(
    db: Session,
    access: Access,
    *,
    display_name: str,
    role: HouseholdRole,
    birth_year: int | None = None,
    email: str | None = None,
) -> HouseholdMember:
    """Add a family member. With `email`, that existing account gains access (US9)."""
    require_role(access, HouseholdRole.OWNER)
    user_id: uuid.UUID | None = None
    if email:
        linked = get_user_by_email(db, email)
        if linked is None or not linked.is_active:
            raise AuthError("USER_NOT_FOUND", 404)
        taken = db.scalar(
            select(HouseholdMember.id).where(
                HouseholdMember.household_id == access.household.id,
                HouseholdMember.user_id == linked.id,
            )
        )
        if taken is not None:
            raise AuthError("ALREADY_MEMBER", 409)
        user_id = linked.id
    member = HouseholdMember(
        household_id=access.household.id,
        user_id=user_id,
        display_name=display_name.strip(),
        role=role.value,
        birth_year=birth_year,
    )
    db.add(member)
    db.flush()
    audit(
        db,
        str(access.user.id),
        "HOUSEHOLD_MEMBER_ADDED",
        "household_member",
        str(member.id),
        after={"role": role.value, "has_login": user_id is not None},
    )
    return member


def update_member(
    db: Session, access: Access, member: HouseholdMember, changes: dict[str, Any]
) -> HouseholdMember:
    """Change a member. Role changes need OWNER; a person may edit their own details.

    `hawl_date` and `nisab_basis` are religious preferences and need consent (FR23.2).
    """
    is_self = member.id == access.member.id
    if not (access.has(HouseholdRole.OWNER) or (is_self and "role" not in changes)):
        raise AuthError("HOUSEHOLD_ROLE_REQUIRED", 403)
    if ("hawl_date" in changes and changes["hawl_date"] is not None) or (
        "nisab_basis" in changes and changes["nisab_basis"] is not None
    ):
        require_consent(access.user, ConsentPurpose.RELIGIOUS_PREFERENCES)
    if "role" in changes and changes["role"] is not None:
        new_role = HouseholdRole(changes["role"])
        losing_owner = member.role == HouseholdRole.OWNER.value and new_role != HouseholdRole.OWNER
        if (
            losing_owner
            and member.user_id is not None
            and _owner_count(db, member.household_id) <= 1
        ):
            raise AuthError("LAST_OWNER", 409)
        if member.role != new_role.value:
            audit(
                db,
                str(access.user.id),
                "HOUSEHOLD_ROLE_CHANGED",
                "household_member",
                str(member.id),
                before={"role": member.role},
                after={"role": new_role.value},
            )
        member.role = new_role.value
    for field in ("display_name", "birth_year", "hawl_date", "nisab_basis"):
        if field in changes:
            value = changes[field]
            setattr(member, field, value.strip() if isinstance(value, str) else value)
    db.flush()
    return member


def remove_member(db: Session, access: Access, member: HouseholdMember) -> None:
    """Remove a member. A person may leave; the last owner with a login may not."""
    if not (access.has(HouseholdRole.OWNER) or member.id == access.member.id):
        raise AuthError("HOUSEHOLD_ROLE_REQUIRED", 403)
    is_last_owner = (
        member.role == HouseholdRole.OWNER.value
        and member.user_id is not None
        and _owner_count(db, member.household_id) <= 1
    )
    if is_last_owner:
        raise AuthError("LAST_OWNER", 409)
    db.execute(delete(OwnerShare).where(OwnerShare.member_id == member.id))
    db.delete(member)
    db.flush()
    audit(db, str(access.user.id), "HOUSEHOLD_MEMBER_REMOVED", "household_member", str(member.id))


def member_age(member: HouseholdMember, today: dt.date) -> int | None:
    return today.year - member.birth_year if member.birth_year else None


# --- owner shares (FR24.1, FR25.8) ----------------------------------------------------


@dataclass(frozen=True)
class OwnerInput:
    pct: Decimal
    member_id: uuid.UUID | None = None
    external_name: str | None = None


def set_owner_shares(
    db: Session,
    household_id: uuid.UUID,
    asset_kind: str,
    asset_id: uuid.UUID,
    owners: Sequence[OwnerInput],
) -> None:
    """Replace who owns an asset or liability. Shares may total at most 100%; any part
    left unnamed belongs to the household jointly."""
    member_ids = {m.id for m in list_members(db, household_id)}
    total = Decimal(0)
    seen: set[uuid.UUID | str] = set()
    for owner in owners:
        key: uuid.UUID | str | None = owner.member_id or (owner.external_name or "").strip().lower()
        named_twice = bool(owner.member_id) == bool((owner.external_name or "").strip())
        if (
            not key
            or named_twice
            or key in seen
            or owner.pct <= 0
            or (owner.member_id is not None and owner.member_id not in member_ids)
        ):
            raise AuthError("OWNER_SHARES_INVALID", 422)
        seen.add(key)
        total += owner.pct
    if total > HUNDRED:
        raise AuthError("OWNER_SHARES_INVALID", 422)
    db.execute(
        delete(OwnerShare).where(
            OwnerShare.asset_kind == asset_kind, OwnerShare.asset_id == asset_id
        )
    )
    for owner in owners:
        db.add(
            OwnerShare(
                asset_kind=asset_kind,
                asset_id=asset_id,
                member_id=owner.member_id,
                external_name=(owner.external_name or "").strip() or None,
                pct=owner.pct,
            )
        )
    db.flush()


def delete_owner_shares(db: Session, asset_ids: Iterable[uuid.UUID]) -> None:
    db.execute(delete(OwnerShare).where(OwnerShare.asset_id.in_(list(asset_ids))))


@dataclass(frozen=True)
class Ownership:
    """Who owns one asset. Percentages are of the whole asset."""

    members: dict[uuid.UUID, Decimal]
    external: dict[str, Decimal]

    @property
    def household_pct(self) -> Decimal:
        """The part that belongs to the household: everything not held by outsiders."""
        return HUNDRED - sum(self.external.values(), Decimal(0))

    def member_pct(self, member_id: uuid.UUID, n_members: int) -> Decimal:
        """One member's share: their named part plus an equal split of the joint part."""
        named = sum(self.members.values(), Decimal(0))
        joint = max(self.household_pct - named, Decimal(0))
        split = joint / n_members if n_members else Decimal(0)
        return self.members.get(member_id, Decimal(0)) + split


JOINT = Ownership(members={}, external={})


def ownership_map(db: Session, asset_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, Ownership]:
    """Ownership for each asset id. An asset with no rows is wholly joint."""
    members: dict[uuid.UUID, dict[uuid.UUID, Decimal]] = defaultdict(dict)
    external: dict[uuid.UUID, dict[str, Decimal]] = defaultdict(dict)
    if asset_ids:
        for row in db.scalars(select(OwnerShare).where(OwnerShare.asset_id.in_(list(asset_ids)))):
            if row.member_id is not None:
                members[row.asset_id][row.member_id] = row.pct
            else:
                external[row.asset_id][row.external_name or ""] = row.pct
    return {
        asset_id: Ownership(members=members.get(asset_id, {}), external=external.get(asset_id, {}))
        for asset_id in asset_ids
    }
