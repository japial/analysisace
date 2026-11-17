"""Households, members and owner shares (F24). Access is by household role (FR24.2)."""

import uuid

from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app.api.deps import CurrentUser, Db, Editor, Owner, Viewer
from app.models import AltAsset, HouseholdMember, Liability, OwnerShare
from app.models.enums import AssetKind, HouseholdRole
from app.schemas.personal import (
    HouseholdIn,
    HouseholdOut,
    MemberIn,
    MemberOut,
    MemberUpdateIn,
    OwnerOut,
    OwnersIn,
)
from app.services import households, portfolio

router = APIRouter(prefix="/households", tags=["households"])


def no_content() -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def member_out(member: HouseholdMember, access: households.Access) -> MemberOut:
    return MemberOut(
        id=member.id,
        display_name=member.display_name,
        role=HouseholdRole(member.role),
        birth_year=member.birth_year,
        hawl_date=member.hawl_date,
        nisab_basis=member.nisab_basis,
        has_login=member.user_id is not None,
        is_you=member.id == access.member.id,
    )


@router.get("")
def list_households(user: CurrentUser, db: Db) -> list[HouseholdOut]:
    return [
        HouseholdOut(id=h.id, name=h.name, role=HouseholdRole(m.role), member_id=m.id)
        for h, m in households.list_households(db, user)
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_household(body: HouseholdIn, user: CurrentUser, db: Db) -> HouseholdOut:
    household, member = households.create_household(db, user, body.name)
    db.commit()
    return HouseholdOut(
        id=household.id, name=household.name, role=HouseholdRole(member.role), member_id=member.id
    )


@router.patch("/{household_id}")
def rename_household(body: HouseholdIn, access: Owner, db: Db) -> HouseholdOut:
    access.household.name = body.name.strip()
    db.commit()
    return HouseholdOut(
        id=access.household.id,
        name=access.household.name,
        role=access.role,
        member_id=access.member.id,
    )


@router.delete("/{household_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_household(access: Owner, db: Db) -> Response:
    """Removes the household and everything recorded in it. Cannot be undone."""
    households.delete_household(db, access)
    db.commit()
    return no_content()


@router.get("/{household_id}/members")
def list_members(access: Viewer, db: Db) -> list[MemberOut]:
    return [member_out(m, access) for m in households.list_members(db, access.household.id)]


@router.post("/{household_id}/members", status_code=status.HTTP_201_CREATED)
def add_member(body: MemberIn, access: Owner, db: Db) -> MemberOut:
    member = households.add_member(
        db,
        access,
        display_name=body.display_name,
        role=body.role,
        birth_year=body.birth_year,
        email=body.email,
    )
    db.commit()
    return member_out(member, access)


@router.patch("/{household_id}/members/{member_id}")
def update_member(member_id: uuid.UUID, body: MemberUpdateIn, access: Viewer, db: Db) -> MemberOut:
    """Owners may change anyone; other members may change their own details, not their role."""
    member = households.get_member(db, access.household.id, member_id)
    changes = body.model_dump(exclude_unset=True)
    if body.nisab_basis is not None:
        changes["nisab_basis"] = body.nisab_basis.value
    households.update_member(db, access, member, changes)
    db.commit()
    return member_out(member, access)


@router.delete("/{household_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(member_id: uuid.UUID, access: Viewer, db: Db) -> Response:
    member = households.get_member(db, access.household.id, member_id)
    households.remove_member(db, access, member)
    db.commit()
    return no_content()


def _check_asset(db: Db, household_id: uuid.UUID, kind: AssetKind, asset_id: uuid.UUID) -> None:
    if kind is AssetKind.HOLDING:
        portfolio.get_holding(db, household_id, asset_id)
    elif kind is AssetKind.ALT_ASSET:
        households.owned(db, AltAsset, asset_id, household_id)
    else:
        households.owned(db, Liability, asset_id, household_id)


@router.get("/{household_id}/owners/{asset_kind}/{asset_id}")
def get_owners(
    asset_kind: AssetKind, asset_id: uuid.UUID, access: Viewer, db: Db
) -> list[OwnerOut]:
    _check_asset(db, access.household.id, asset_kind, asset_id)
    rows = db.scalars(select(OwnerShare).where(OwnerShare.asset_id == asset_id))
    return [OwnerOut(pct=r.pct, member_id=r.member_id, external_name=r.external_name) for r in rows]


@router.put("/{household_id}/owners/{asset_kind}/{asset_id}")
def set_owners(
    asset_kind: AssetKind, asset_id: uuid.UUID, body: OwnersIn, access: Editor, db: Db
) -> list[OwnerOut]:
    """Who owns an asset or liability, by percentage (FR24.1, FR25.8). The part left
    unnamed is held jointly by the household."""
    _check_asset(db, access.household.id, asset_kind, asset_id)
    households.set_owner_shares(
        db,
        access.household.id,
        asset_kind.value,
        asset_id,
        [
            households.OwnerInput(pct=o.pct, member_id=o.member_id, external_name=o.external_name)
            for o in body.owners
        ],
    )
    db.commit()
    return get_owners(asset_kind, asset_id, access, db)
