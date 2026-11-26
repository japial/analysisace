"""Firm accounts (F9, D30): the firm page for members and admins, and the platform admin
screens. Every route answers 404 while FIRM_FEATURES_ENABLED is off (TODO(owner): Q4)."""

import base64
import binascii
import datetime as dt
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select

from app.api.deps import AppSettings, CurrentUser, Db, require_permission
from app.core.config import Settings, get_settings
from app.core.permissions import Permission
from app.models import MacroNote, User
from app.schemas.firm import (
    AdminFirmIn,
    AdminFirmOut,
    AdminFirmUpdateIn,
    ApiKeyCreated,
    ApiKeyIn,
    ApiKeyOut,
    FirmDetail,
    FirmSummary,
    FirmUpdateIn,
    LogoIn,
    MemberOut,
    SeatIn,
    SeatRoleIn,
    UsageRow,
)
from app.services import firm_report, firms
from app.services.auth import AuthError
from app.services.storage import DocumentStorage, get_document_storage
from app.services.valuation import today_dhaka

Storage = Annotated[DocumentStorage, Depends(get_document_storage)]


def _enabled(settings: Annotated[Settings, Depends(get_settings)]) -> None:
    firms.require_enabled(settings)


router = APIRouter(tags=["firms"], dependencies=[Depends(_enabled)])
FirmsManager = Annotated[User, Depends(require_permission(Permission.FIRMS_MANAGE))]


def _detail(db: Db, found: firms.Membership) -> FirmDetail:
    firm = found.firm
    weeks = list(
        db.scalars(
            select(MacroNote.week_start)
            .where(MacroNote.status == "PUBLISHED")
            .distinct()
            .order_by(MacroNote.week_start.desc())
            .limit(12)
        )
    )
    return FirmDetail(
        id=firm.id,
        name=firm.name,
        role=found.seat.role,
        seat_limit=firm.seat_limit,
        report_disclaimer=firm.report_disclaimer,
        has_logo=firm.logo_ref is not None,
        members=[
            MemberOut(
                user_id=user.id,
                full_name=user.full_name,
                email=user.email,
                role=seat.role,
                since=seat.created_at,
            )
            for seat, user in firms.seats(db, firm.id)
        ],
        api_keys=[ApiKeyOut.model_validate(k) for k in firms.list_keys(db, firm.id)]
        if found.is_admin
        else [],
        usage=[UsageRow(**u) for u in firms.usage(db, firm.id)] if found.is_admin else [],
        report_weeks=weeks,
    )


# --- the firm page ----------------------------------------------------------------------


@router.get("/firms/mine")
def my_firms(user: CurrentUser, db: Db) -> list[FirmSummary]:
    """The firms this person has a seat in (FR9.3)."""
    return [
        FirmSummary(id=m.firm.id, name=m.firm.name, role=m.seat.role)
        for m in firms.memberships(db, user)
    ]


@router.get("/firms/{firm_id}")
def get_firm(firm_id: uuid.UUID, user: CurrentUser, db: Db) -> FirmDetail:
    return _detail(db, firms.membership(db, user, firm_id))


@router.patch("/firms/{firm_id}")
def update_firm(firm_id: uuid.UUID, body: FirmUpdateIn, user: CurrentUser, db: Db) -> FirmDetail:
    """A firm admin sets the disclaimer printed on the firm's reports (FR9.1)."""
    found = firms.membership(db, user, firm_id, admin=True)
    firms.update_firm(db, user, found.firm, body.model_dump(exclude_unset=True))
    db.commit()
    return _detail(db, found)


@router.put("/firms/{firm_id}/logo", status_code=status.HTTP_204_NO_CONTENT)
def set_logo(
    firm_id: uuid.UUID,
    body: LogoIn,
    user: CurrentUser,
    db: Db,
    settings: AppSettings,
    storage: Storage,
) -> Response:
    found = firms.membership(db, user, firm_id, admin=True)
    try:
        data = base64.b64decode(body.content_base64, validate=True)
    except (binascii.Error, ValueError):
        raise AuthError("LOGO_INVALID", 422) from None
    firms.set_logo(db, user, found.firm, storage, data, settings.firm_logo_max_bytes)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/firms/{firm_id}/logo", status_code=status.HTTP_204_NO_CONTENT)
def remove_logo(firm_id: uuid.UUID, user: CurrentUser, db: Db, storage: Storage) -> Response:
    found = firms.membership(db, user, firm_id, admin=True)
    firms.remove_logo(db, user, found.firm, storage)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/firms/{firm_id}/logo")
def get_logo(firm_id: uuid.UUID, user: CurrentUser, db: Db, storage: Storage) -> Response:
    found = firms.membership(db, user, firm_id)
    data = firms.logo(found.firm, storage)
    if data is None:
        raise AuthError("NOT_FOUND", 404)
    # Always re-encoded PNG (see firms.set_logo), so it is safe to show inline.
    return Response(
        data,
        media_type="image/png",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
    )


@router.post("/firms/{firm_id}/members", status_code=status.HTTP_201_CREATED)
def add_member(firm_id: uuid.UUID, body: SeatIn, user: CurrentUser, db: Db) -> FirmDetail:
    """FR9.3: give an existing analysisACE account a seat, within the firm's seat limit."""
    found = firms.membership(db, user, firm_id, admin=True)
    firms.add_seat(db, user, found.firm, body.email, body.role)
    db.commit()
    return _detail(db, found)


@router.patch("/firms/{firm_id}/members/{user_id}")
def change_member(
    firm_id: uuid.UUID, user_id: uuid.UUID, body: SeatRoleIn, user: CurrentUser, db: Db
) -> FirmDetail:
    found = firms.membership(db, user, firm_id, admin=True)
    firms.change_role(db, user, found.firm, user_id, body.role)
    db.commit()
    return _detail(db, firms.membership(db, user, firm_id))


@router.delete("/firms/{firm_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(firm_id: uuid.UUID, user_id: uuid.UUID, user: CurrentUser, db: Db) -> Response:
    found = firms.membership(db, user, firm_id, admin=True)
    firms.remove_seat(db, user, found.firm, user_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/firms/{firm_id}/api-keys", status_code=status.HTTP_201_CREATED)
def create_key(
    firm_id: uuid.UUID, body: ApiKeyIn, user: CurrentUser, db: Db, settings: AppSettings
) -> ApiKeyCreated:
    """FR9.2: a read-only key for the firm API. The key is shown in this answer only."""
    found = firms.membership(db, user, firm_id, admin=True)
    row, secret = firms.create_key(
        db, user, found.firm, body.name, settings.firm_api_rate_per_minute
    )
    db.commit()
    return ApiKeyCreated(**ApiKeyOut.model_validate(row).model_dump(), key=secret)


@router.delete("/firms/{firm_id}/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_key(firm_id: uuid.UUID, key_id: uuid.UUID, user: CurrentUser, db: Db) -> Response:
    found = firms.membership(db, user, firm_id, admin=True)
    firms.revoke_key(db, user, found.firm, key_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _csv(text: str, name: str) -> Response:
    return Response(
        text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/firms/{firm_id}/exports/{dataset}.csv")
def export_csv(
    firm_id: uuid.UUID, dataset: Literal["shariah", "scores"], user: CurrentUser, db: Db
) -> Response:
    """FR9.2: the Shariah screen or the rate-sensitivity scores as CSV, for any member."""
    firms.membership(db, user, firm_id)
    text = firms.shariah_csv(db) if dataset == "shariah" else firms.scores_csv(db)
    return _csv(text, f"analysisace-{dataset}-{today_dhaka().isoformat()}.csv")


@router.get("/firms/{firm_id}/reports/weekly.pdf")
def weekly_report(
    firm_id: uuid.UUID,
    user: CurrentUser,
    db: Db,
    storage: Storage,
    locale: Literal["en", "bn"] = "en",
    week: Annotated[dt.date | None, Query()] = None,
) -> Response:
    """FR9.1: the published weekly note as a PDF with the firm's logo, name and disclaimer."""
    found = firms.membership(db, user, firm_id)
    statement = select(MacroNote).where(MacroNote.status == "PUBLISHED", MacroNote.locale == locale)
    if week is not None:
        statement = statement.where(MacroNote.week_start == week)
    note = db.scalar(statement.order_by(MacroNote.week_start.desc()).limit(1))
    if note is None:
        raise AuthError("NOTE_NOT_PUBLISHED", 404)
    pdf = firm_report.weekly_report_pdf(found.firm, firms.logo(found.firm, storage), note, locale)
    name = f"weekly-{note.week_start.isoformat()}-{locale}.pdf"
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


# --- platform administration --------------------------------------------------------------


def _admin_out(firm: object, used: int) -> AdminFirmOut:
    return AdminFirmOut(
        id=firm.id,  # type: ignore[attr-defined]
        name=firm.name,  # type: ignore[attr-defined]
        seat_limit=firm.seat_limit,  # type: ignore[attr-defined]
        seats_used=used,
        is_active=firm.is_active,  # type: ignore[attr-defined]
        created_at=firm.created_at,  # type: ignore[attr-defined]
    )


@router.get("/admin/firms")
def admin_list(_: FirmsManager, db: Db) -> list[AdminFirmOut]:
    return [_admin_out(f, used) for f, used in firms.list_firms(db)]


@router.post("/admin/firms", status_code=status.HTTP_201_CREATED)
def admin_create(body: AdminFirmIn, actor: FirmsManager, db: Db) -> AdminFirmOut:
    """FR9.3: a new firm, with an existing account as its first admin."""
    firm = firms.create_firm(
        db,
        actor,
        name=body.name,
        seat_limit=body.seat_limit,
        admin_email=body.admin_email,
        disclaimer=body.report_disclaimer,
    )
    db.commit()
    return _admin_out(firm, 1)


@router.patch("/admin/firms/{firm_id}")
def admin_update(
    firm_id: uuid.UUID, body: AdminFirmUpdateIn, actor: FirmsManager, db: Db
) -> AdminFirmOut:
    firm = firms.get_firm(db, firm_id)
    firms.update_firm(db, actor, firm, body.model_dump(exclude_unset=True, exclude_none=True))
    db.commit()
    used = next((n for f, n in firms.list_firms(db) if f.id == firm.id), 0)
    return _admin_out(firm, used)
