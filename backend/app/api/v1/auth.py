"""Sign-up, sign-in, sign-out and password reset (PRD section 10, Auth).

The API deals only in opaque Bearer tokens. The web app keeps the token in an httpOnly
cookie on its own server; the mobile app keeps it in secure storage (DECISIONS D10).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status

from app.api.deps import AppSettings, CurrentIdentity, Db
from app.schemas.auth import (
    AuthOut,
    LoginIn,
    PasswordResetConfirmIn,
    PasswordResetRequestIn,
    RegisterIn,
    UserOut,
)
from app.services import auth as auth_service
from app.services.email import EmailSender, get_email_sender

router = APIRouter(prefix="/auth", tags=["auth"])

UserAgent = Annotated[str | None, Header()]


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterIn, db: Db, settings: AppSettings, user_agent: UserAgent = None
) -> AuthOut:
    user = auth_service.register_user(
        db,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        locale=body.locale,
        accept_terms=body.accept_terms,
    )
    session, token = auth_service.create_session(db, user, settings, user_agent=user_agent)
    db.commit()
    return AuthOut(user=UserOut.model_validate(user), token=token, expires_at=session.expires_at)


@router.post("/login")
def login(body: LoginIn, db: Db, settings: AppSettings, user_agent: UserAgent = None) -> AuthOut:
    try:
        user = auth_service.authenticate(db, body.email, body.password, settings)
    except auth_service.AuthError:
        # Keep the failed-attempt counter and any lock that was just applied.
        db.commit()
        raise
    session, token = auth_service.create_session(
        db, user, settings, client=body.client, user_agent=user_agent
    )
    db.commit()
    return AuthOut(user=UserOut.model_validate(user), token=token, expires_at=session.expires_at)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(identity: CurrentIdentity, db: Db) -> Response:
    auth_service.revoke_session(db, identity.session)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(
    body: PasswordResetRequestIn,
    db: Db,
    settings: AppSettings,
    sender: Annotated[EmailSender, Depends(get_email_sender)],
) -> Response:
    """Always answers 202, whether or not the email has an account."""
    auth_service.request_password_reset(db, body.email, sender, settings)
    db.commit()
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(body: PasswordResetConfirmIn, db: Db) -> Response:
    auth_service.confirm_password_reset(db, body.token, body.new_password)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
