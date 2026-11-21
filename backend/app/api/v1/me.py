"""The signed-in user's own account: profile, password, consents, export, deletion (FR23)."""

from typing import Any

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentIdentity, CurrentUser, Db
from app.schemas.auth import (
    AccountDeleteIn,
    ConsentsUpdateIn,
    PasswordChangeIn,
    ProfileUpdateIn,
    UserOut,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/me", tags=["me"])


@router.get("")
def read_me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("")
def update_me(body: ProfileUpdateIn, user: CurrentUser, db: Db) -> UserOut:
    if body.full_name is not None:
        user.full_name = body.full_name.strip()
    if body.locale is not None:
        user.locale = body.locale
    db.commit()
    return UserOut.model_validate(user)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: PasswordChangeIn, identity: CurrentIdentity, db: Db) -> Response:
    """Changes the password and signs out every other device."""
    auth_service.change_password(
        db, identity.user, body.current_password, body.new_password, keep=identity.session.id
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/consents")
def update_consents(body: ConsentsUpdateIn, user: CurrentUser, db: Db) -> UserOut:
    auth_service.update_consents(db, user, body.consents)
    db.commit()
    return UserOut.model_validate(user)


@router.get("/export")
def export_me(user: CurrentUser, db: Db) -> dict[str, Any]:
    """Self-service copy of everything stored about the user (FR23.4)."""
    return auth_service.export_user_data(db, user)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(body: AccountDeleteIn, user: CurrentUser, db: Db) -> Response:
    """Deletes the account at once, which meets the 7-day limit in FR23.4."""
    auth_service.delete_account(db, user, body.password)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
