"""Accounts: registration, sign-in, sessions, password reset, consents, export, deletion.

Covers the Auth endpoints in PRD section 10 and the privacy rules in FR23. Functions flush
but do not commit; the API route commits.
"""

import uuid
from datetime import timedelta
from enum import StrEnum
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.permissions import Role
from app.core.security import (
    as_utc,
    hash_password,
    hash_token,
    new_token,
    password_needs_rehash,
    utcnow,
    verify_password,
)
from app.models import (
    AlertRule,
    AuditLog,
    EmailVerificationToken,
    FirmSeat,
    Notification,
    PasswordResetToken,
    PushSubscription,
    Subscription,
    User,
    UserSession,
    Watchlist,
)
from app.services import household_data
from app.services.email import (
    EmailSender,
    password_reset_email,
    send_safely,
    verification_email,
)


class AuthError(Exception):
    """A refusal the client can act on. `code` is stable and translated by the client."""

    def __init__(self, code: str, status_code: int = 400) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class ConsentPurpose(StrEnum):
    TERMS = "TERMS"  # required to hold an account; withdrawn by deleting the account
    MARKETING = "MARKETING"
    RELIGIOUS_PREFERENCES = "RELIGIOUS_PREFERENCES"  # Zakat and Shariah preferences (FR23.2)
    COMMUNITY_BENCHMARKING = "COMMUNITY_BENCHMARKING"  # FR21.1


OPTIONAL_CONSENTS = frozenset(ConsentPurpose) - {ConsentPurpose.TERMS}


def normalise_email(email: str) -> str:
    return email.strip().lower()


def audit(
    db: Session,
    actor: str,
    action: str,
    entity: str,
    entity_id: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            actor=actor,
            action=action,
            entity=entity,
            entity_id=entity_id,
            before=before,
            after=after,
            at=utcnow(),
        )
    )


def _consent(granted: bool) -> dict[str, Any]:
    return {"granted": granted, "at": utcnow().isoformat()}


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalise_email(email)))


def register_user(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str,
    locale: str,
    accept_terms: bool,
    role: Role = Role.USER,
) -> User:
    if not accept_terms:
        # FR23.1: consent must be explicit.
        raise AuthError("TERMS_REQUIRED")
    if get_user_by_email(db, email) is not None:
        raise AuthError("EMAIL_TAKEN", 409)
    user = User(
        email=normalise_email(email),
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        locale=locale,
        role=role.value,
        consents={ConsentPurpose.TERMS.value: _consent(True)},
        # Registering through the API signs the person in at once.
        last_login_at=utcnow(),
    )
    db.add(user)
    db.flush()
    audit(db, str(user.id), "USER_REGISTERED", "app_user", str(user.id))
    return user


def authenticate(db: Session, email: str, password: str, settings: Settings) -> User:
    """Check a password. Raises AuthError; never says whether the email exists."""
    user = get_user_by_email(db, email)
    now = utcnow()
    if user is not None and user.locked_until and as_utc(user.locked_until) > now:
        raise AuthError("ACCOUNT_LOCKED", 429)

    if not verify_password(password, user.password_hash if user else None):
        if user is not None:
            user.failed_login_count += 1
            if user.failed_login_count >= settings.login_max_failures:
                user.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
                user.failed_login_count = 0
                audit(db, str(user.id), "LOGIN_LOCKED", "app_user", str(user.id))
            db.flush()
        raise AuthError("INVALID_CREDENTIALS", 401)

    assert user is not None  # verify_password is False for an unknown email
    if not user.is_active:
        raise AuthError("ACCOUNT_DISABLED", 403)
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    db.flush()
    return user


def create_session(
    db: Session,
    user: User,
    settings: Settings,
    *,
    client: str = "web",
    user_agent: str | None = None,
) -> tuple[UserSession, str]:
    """Returns the session and the token. The token is shown once and never stored."""
    token = new_token()
    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(token),
        client=client,
        user_agent=(user_agent or "")[:300] or None,
        expires_at=utcnow() + timedelta(days=settings.session_ttl_days),
    )
    db.add(session)
    db.flush()
    return session, token


def resolve_session(db: Session, token: str) -> tuple[UserSession, User] | None:
    """The live session and active user for a token, or None."""
    session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    if session is None or session.revoked_at is not None:
        return None
    if as_utc(session.expires_at) <= utcnow():
        return None
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        return None
    return session, user


def revoke_session(db: Session, session: UserSession) -> None:
    session.revoked_at = utcnow()
    db.flush()


def revoke_all_sessions(db: Session, user_id: uuid.UUID, *, keep: uuid.UUID | None = None) -> None:
    statement = (
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    if keep is not None:
        statement = statement.where(UserSession.id != keep)
    db.execute(statement)
    db.flush()


def request_password_reset(
    db: Session, email: str, sender: EmailSender, settings: Settings
) -> None:
    """Email a reset link if the account exists. Silent otherwise, so emails cannot be probed."""
    user = get_user_by_email(db, email)
    if user is None or not user.is_active:
        return
    token = new_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=utcnow() + timedelta(minutes=settings.password_reset_ttl_minutes),
        )
    )
    db.flush()
    link = f"{settings.web_base_url}/{user.locale}/reset-password?token={token}"
    # The answer is the same whether or not the email went, so accounts cannot be probed.
    send_safely(
        sender,
        password_reset_email(user.email, user.locale, link, settings.password_reset_ttl_minutes),
    )


def start_email_verification(
    db: Session, user: User, sender: EmailSender, settings: Settings
) -> bool:
    """Email a link that confirms the address (D25). Earlier unused links stop working, so
    only the newest one counts. Returns False when there is nothing to confirm."""
    if user.email_verified_at is not None or not user.is_active:
        return False
    now = utcnow()
    for old in db.scalars(
        select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user.id, EmailVerificationToken.used_at.is_(None)
        )
    ):
        old.used_at = now
    token = new_token()
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=now + timedelta(hours=settings.email_verification_ttl_hours),
        )
    )
    db.flush()
    link = f"{settings.web_base_url}/{user.locale}/verify-email?token={token}"
    send_safely(
        sender,
        verification_email(user.email, user.locale, link, settings.email_verification_ttl_hours),
    )
    return True


def confirm_email_verification(db: Session, token: str) -> User:
    record = db.scalar(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == hash_token(token))
    )
    if record is None or record.used_at is not None or as_utc(record.expires_at) <= utcnow():
        raise AuthError("VERIFY_TOKEN_INVALID")
    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        raise AuthError("VERIFY_TOKEN_INVALID")
    record.used_at = utcnow()
    if user.email_verified_at is None:
        user.email_verified_at = utcnow()
        audit(db, str(user.id), "EMAIL_VERIFIED", "app_user", str(user.id))
    return user


def confirm_password_reset(db: Session, token: str, new_password: str) -> User:
    record = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(token))
    )
    if record is None or record.used_at is not None or as_utc(record.expires_at) <= utcnow():
        raise AuthError("INVALID_TOKEN")
    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        raise AuthError("INVALID_TOKEN")
    record.used_at = utcnow()
    user.password_hash = hash_password(new_password)
    user.failed_login_count = 0
    user.locked_until = None
    # Whoever knew the old password is signed out everywhere.
    revoke_all_sessions(db, user.id)
    audit(db, str(user.id), "PASSWORD_RESET", "app_user", str(user.id))
    return user


def change_password(
    db: Session, user: User, current_password: str, new_password: str, *, keep: uuid.UUID
) -> None:
    if not verify_password(current_password, user.password_hash):
        raise AuthError("WRONG_PASSWORD")
    user.password_hash = hash_password(new_password)
    revoke_all_sessions(db, user.id, keep=keep)
    audit(db, str(user.id), "PASSWORD_CHANGED", "app_user", str(user.id))


def update_consents(db: Session, user: User, changes: dict[ConsentPurpose, bool]) -> None:
    """Grant or withdraw optional consents (FR23.1). Each change is audited."""
    consents = dict(user.consents or {})
    for purpose, granted in changes.items():
        if purpose not in OPTIONAL_CONSENTS:
            raise AuthError("CONSENT_NOT_CHANGEABLE")
        previous = bool((consents.get(purpose.value) or {}).get("granted", False))
        if previous == granted:
            continue
        consents[purpose.value] = _consent(granted)
        audit(
            db,
            str(user.id),
            "CONSENT_CHANGED",
            "app_user",
            str(user.id),
            before={purpose.value: previous},
            after={purpose.value: granted},
        )
    user.consents = consents
    db.flush()


def export_user_data(db: Session, user: User) -> dict[str, Any]:
    """Everything stored about the user (FR23.4). Extend as personal finance tables arrive."""
    sessions = db.scalars(select(UserSession).where(UserSession.user_id == user.id)).all()
    return {
        "exported_at": utcnow().isoformat(),
        "account": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "locale": user.locale,
            "role": user.role,
            "created_at": as_utc(user.created_at).isoformat(),
            "last_login_at": as_utc(user.last_login_at).isoformat() if user.last_login_at else None,
        },
        "consents": user.consents,
        "households": [
            household_data.export_household(db, household_id)
            for household_id in household_data.households_of(db, user.id)
        ],
        "watchlist": list(db.scalars(select(Watchlist.ticker).where(Watchlist.user_id == user.id))),
        "alert_rules": [
            {"type": r.type, "channel": r.channel, "frequency": r.frequency, "params": r.params}
            for r in db.scalars(select(AlertRule).where(AlertRule.user_id == user.id))
        ],
        "sessions": [
            {
                "client": s.client,
                "user_agent": s.user_agent,
                "created_at": as_utc(s.created_at).isoformat(),
                "expires_at": as_utc(s.expires_at).isoformat(),
                "revoked": s.revoked_at is not None,
            }
            for s in sessions
        ],
    }


def delete_account(db: Session, user: User, password: str) -> None:
    """Remove the account and everything tied to it (FR23.4)."""
    if not verify_password(password, user.password_hash):
        raise AuthError("WRONG_PASSWORD")
    if user.role == Role.ADMIN.value and count_active_admins(db) <= 1:
        raise AuthError("LAST_ADMIN", 409)
    user_id = user.id
    for household_id in household_data.households_of(db, user_id):
        # A household shared with another login stays; this person just leaves it.
        if not household_data.has_other_login(db, household_id, user_id):
            household_data.delete_household(db, household_id)
    for model in (Watchlist, AlertRule, Notification, PushSubscription, FirmSeat, Subscription):
        db.execute(delete(model).where(model.user_id == user_id))
    db.execute(delete(UserSession).where(UserSession.user_id == user_id))
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user_id))
    db.execute(delete(EmailVerificationToken).where(EmailVerificationToken.user_id == user_id))
    db.delete(user)
    # The audit entry keeps the id only, never the email or name.
    audit(db, str(user_id), "USER_DELETED", "app_user", str(user_id))
    db.flush()


def count_active_admins(db: Session) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == Role.ADMIN.value, User.is_active.is_(True))
        )
        or 0
    )
