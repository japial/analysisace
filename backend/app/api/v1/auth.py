"""Sign-up, sign-in, sign-out and password reset (PRD section 10, Auth).

The API deals only in opaque Bearer tokens. The web app keeps the token in an httpOnly
cookie on its own server; the mobile app keeps it in secure storage (DECISIONS D10).
"""

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response, status

from app.api.deps import AppSettings, CurrentIdentity, CurrentUser, Db
from app.core.config import Settings
from app.schemas.auth import (
    AuthOut,
    EmailChangeConfirmIn,
    EmailChangeIn,
    EmailChangeOut,
    LoginIn,
    PasswordResetConfirmIn,
    PasswordResetRequestIn,
    RegisterIn,
    UserOut,
    VerifyEmailConfirmIn,
)
from app.services import auth as auth_service
from app.services import ratelimit
from app.services.email import EmailSender, get_email_sender

router = APIRouter(prefix="/auth", tags=["auth"])

UserAgent = Annotated[str | None, Header()]
ForwardedFor = Annotated[str | None, Header(alias="X-Forwarded-For")]

HOUR = dt.timedelta(hours=1)


def _visitor(request: Request, forwarded_for: str | None, settings: Settings) -> str:
    return ratelimit.client_ip(
        request.client.host if request.client else None, forwarded_for, settings
    )


def _limit(db: Db, bucket: str, key: str, limit: int, window: dt.timedelta) -> None:
    """D28: count this attempt, saved at once so that a request that then fails still counts,
    and refuse with 429 past the limit."""
    allowed = ratelimit.allow(db, bucket, key, limit, window)
    db.commit()
    if not allowed:
        raise auth_service.AuthError("RATE_LIMITED", 429)


def _limit_visitor(
    db: Db, settings: Settings, bucket: str, visitor: str, limit: int, window: dt.timedelta
) -> None:
    """A per-visitor limit. In development the machine's own address is left out: every
    local browser and test reaches the API from it (D28). Production exempts no one."""
    if settings.environment == "development" and ratelimit.is_loopback(visitor):
        return
    _limit(db, bucket, visitor, limit, window)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterIn,
    db: Db,
    settings: AppSettings,
    sender: Annotated[EmailSender, Depends(get_email_sender)],
    request: Request,
    user_agent: UserAgent = None,
    forwarded_for: ForwardedFor = None,
) -> AuthOut:
    visitor = _visitor(request, forwarded_for, settings)
    _limit_visitor(db, settings, "signup", visitor, settings.rate_limit_signup_per_hour, HOUR)
    user = auth_service.register_user(
        db,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        locale=body.locale,
        accept_terms=body.accept_terms,
    )
    session, token = auth_service.create_session(db, user, settings, user_agent=user_agent)
    # D25: a link to confirm the address. Sign-up does not wait for it.
    auth_service.start_email_verification(db, user, sender, settings)
    db.commit()
    return AuthOut(user=UserOut.model_validate(user), token=token, expires_at=session.expires_at)


@router.post("/login")
def login(
    body: LoginIn,
    db: Db,
    settings: AppSettings,
    request: Request,
    user_agent: UserAgent = None,
    forwarded_for: ForwardedFor = None,
) -> AuthOut:
    visitor = _visitor(request, forwarded_for, settings)
    _limit_visitor(
        db,
        settings,
        "login",
        visitor,
        settings.rate_limit_login_per_15_minutes,
        dt.timedelta(minutes=15),
    )
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
    request: Request,
    forwarded_for: ForwardedFor = None,
) -> Response:
    """Always answers 202, whether or not the email has an account. Past the per-address
    limit (D28) it still answers 202 but sends nothing, so an inbox cannot be flooded and
    the answer still says nothing about the account."""
    visitor = _visitor(request, forwarded_for, settings)
    _limit_visitor(db, settings, "reset", visitor, settings.rate_limit_reset_per_hour, HOUR)
    if ratelimit.allow(
        db, "reset-email", body.email, settings.rate_limit_reset_per_email_per_hour, HOUR
    ):
        auth_service.request_password_reset(db, body.email, sender, settings)
    db.commit()
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post("/verify-email/request", status_code=status.HTTP_202_ACCEPTED)
def request_email_verification(
    identity: CurrentIdentity,
    db: Db,
    settings: AppSettings,
    sender: Annotated[EmailSender, Depends(get_email_sender)],
) -> Response:
    """D25: send a new confirmation link to the signed-in person. Nothing happens when the
    address is already confirmed and has not bounced (D35). Limited per person (D28)."""
    _limit(db, "verify", str(identity.user.id), settings.rate_limit_verify_per_user_per_hour, HOUR)
    auth_service.start_email_verification(db, identity.user, sender, settings)
    db.commit()
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post("/verify-email/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_email_verification(body: VerifyEmailConfirmIn, db: Db) -> Response:
    """D25: the link from the email. Works without being signed in."""
    auth_service.confirm_email_verification(db, body.token)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(body: PasswordResetConfirmIn, db: Db) -> Response:
    auth_service.confirm_password_reset(db, body.token, body.new_password)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- changing the sign-in email (D39) ---------------------------------------------------


@router.get("/email-change")
def read_email_change(user: CurrentUser, db: Db) -> EmailChangeOut | None:
    """The change waiting for its link to be opened, or null."""
    pending = auth_service.pending_email_change(db, user)
    if pending is None:
        return None
    return EmailChangeOut(new_email=pending.new_email, expires_at=pending.expires_at)


@router.post("/email-change", status_code=status.HTTP_202_ACCEPTED)
def request_email_change(
    body: EmailChangeIn,
    identity: CurrentIdentity,
    db: Db,
    settings: AppSettings,
    sender: Annotated[EmailSender, Depends(get_email_sender)],
) -> EmailChangeOut:
    """D39: email a link to the new address. Limited per person, like confirmation links."""
    _limit(
        db,
        "email-change",
        str(identity.user.id),
        settings.rate_limit_verify_per_user_per_hour,
        HOUR,
    )
    record = auth_service.request_email_change(
        db, identity.user, body.new_email, body.password, sender, settings
    )
    db.commit()
    return EmailChangeOut(new_email=record.new_email, expires_at=record.expires_at)


@router.delete("/email-change", status_code=status.HTTP_204_NO_CONTENT)
def cancel_email_change(user: CurrentUser, db: Db) -> Response:
    auth_service.cancel_email_change(db, user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/email-change/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_email_change(
    body: EmailChangeConfirmIn,
    db: Db,
    settings: AppSettings,
    sender: Annotated[EmailSender, Depends(get_email_sender)],
) -> Response:
    """D39: the link from the new address. Works without being signed in."""
    auth_service.confirm_email_change(db, body.token, sender, settings)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
