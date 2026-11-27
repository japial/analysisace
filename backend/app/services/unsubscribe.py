"""One-click unsubscribe from alert and report emails (RFC 8058, FR7.3, D34).

Every alert, digest and monthly report email carries a personal link. The link holds a token
sealed with the data encryption key (`app.core.crypto`), naming the person and what to stop:
one alert type, or "DIGEST" for every alert that arrives once a day. Nobody can make a token
for someone else, and no sign-in is needed, so mail apps can unsubscribe in one press.

Unsubscribing stops email only. The notices stay in the app, and browser notifications carry
on where they were chosen: EMAIL becomes APP (in the app only) and BOTH becomes PUSH.
"""

import json
import uuid
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import EncryptionUnavailable, decrypt_text, encrypt_text
from app.models import AlertRule, Notification, User
from app.models.enums import AlertType
from app.services.auth import AuthError, audit
from app.services.email_render import Links

DIGEST = "DIGEST"
SCOPES = frozenset({DIGEST, *(t.value for t in AlertType)})
_WITHOUT_EMAIL = {"EMAIL": "APP", "BOTH": "PUSH"}


def make_token(user_id: uuid.UUID, scope: str) -> str:
    if scope not in SCOPES:
        raise ValueError(f"unknown unsubscribe scope {scope!r}")
    return encrypt_text(json.dumps({"u": str(user_id), "s": scope}, separators=(",", ":")))


def links(base: str, lang: str, user_id: uuid.UUID, scope: str) -> Links | None:
    """The two addresses for an email, or None when no key is set to seal a token (the email
    then points to the alert settings page instead)."""
    try:
        token = quote(make_token(user_id, scope), safe="")
    except EncryptionUnavailable:
        return None
    root = base.rstrip("/")
    return Links(
        page=f"{root}/{lang}/unsubscribe?t={token}",
        one_click=f"{root}/{lang}/unsubscribe/one-click?t={token}",
    )


def _read(db: Session, token: str) -> tuple[User, str]:
    try:
        payload = json.loads(decrypt_text(token.strip()))
        user_id, scope = uuid.UUID(payload["u"]), str(payload["s"])
    except (EncryptionUnavailable, ValueError, KeyError, TypeError, UnicodeError) as exc:
        raise AuthError("UNSUBSCRIBE_LINK_INVALID", 400) from exc
    user = db.get(User, user_id)
    if user is None or scope not in SCOPES:
        raise AuthError("UNSUBSCRIBE_LINK_INVALID", 400)
    return user, scope


def _rules(db: Session, user: User, scope: str) -> list[AlertRule]:
    query = select(AlertRule).where(AlertRule.user_id == user.id)
    if scope == DIGEST:
        query = query.where(AlertRule.frequency == "DAILY_DIGEST")
    else:
        query = query.where(AlertRule.type == scope)
    return list(db.scalars(query))


def describe(db: Session, token: str) -> dict[str, object]:
    """What the link would stop, for the confirmation page: the scope, and whether any of it
    is still emailed."""
    user, scope = _read(db, token)
    emailing = any(rule.channel in _WITHOUT_EMAIL for rule in _rules(db, user, scope))
    return {"scope": scope, "emailing": emailing}


def unsubscribe(db: Session, token: str) -> dict[str, object]:
    """Stop the emails the token names. Safe to repeat: a second press changes nothing."""
    user, scope = _read(db, token)
    changed = 0
    for rule in _rules(db, user, scope):
        new = _WITHOUT_EMAIL.get(rule.channel)
        if new is None:
            continue
        audit(
            db,
            str(user.id),
            "EMAIL_UNSUBSCRIBED",
            "alert_rule",
            str(rule.id),
            before={"channel": rule.channel},
            after={"channel": new},
        )
        rule.channel = new
        changed += 1
    # Notices already waiting for the next digest are not emailed either.
    waiting = select(Notification).where(
        Notification.user_id == user.id,
        Notification.digest_channel.in_(tuple(_WITHOUT_EMAIL)),
        Notification.digested_at.is_(None),
    )
    if scope != DIGEST:
        waiting = waiting.where(Notification.type == scope)
    for row in db.scalars(waiting):
        row.digest_channel = _WITHOUT_EMAIL[row.digest_channel or ""]
    db.flush()
    return {"scope": scope, "changed": changed}
