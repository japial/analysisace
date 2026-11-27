"""Web Push to the browsers a person has turned notifications on in (FR7.1, FR20.1, D26).

The notice is always in the app; push is an extra copy for people whose alert rule asks for
PUSH or BOTH. Push needs a VAPID key pair in the settings (`scripts/generate_vapid_keys.py`);
without one, push is off and nothing is sent. A failed push never breaks the caller, and a
subscription the browser has given up (HTTP 404 or 410) is removed.
"""

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from pywebpush import WebPushException, webpush
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import PushSubscription, User

logger = logging.getLogger("analysisace.push")

# Endpoints are issued by browser vendors; anything else is refused so the server never
# posts to an address a client made up.
ALLOWED_HOST_SUFFIXES = (
    ".googleapis.com",  # Chrome, Edge (FCM)
    ".mozilla.com",  # Firefox
    ".push.apple.com",  # Safari
    ".notify.windows.com",  # Edge on Windows (WNS)
)


@dataclass(frozen=True)
class PushMessage:
    title: str
    body: str
    url: str


class PushSender(Protocol):
    def send(self, subscription: PushSubscription, message: PushMessage) -> int | None:
        """Send one message. Returns the HTTP status of a refusal, or None when sent."""
        ...


class WebPushSender:
    def __init__(self, private_key: str, subject: str) -> None:
        self.private_key, self.subject = private_key, subject

    def send(self, subscription: PushSubscription, message: PushMessage) -> int | None:
        try:
            webpush(
                subscription_info={"endpoint": subscription.endpoint, "keys": subscription.keys},
                data=json.dumps(
                    {"title": message.title, "body": message.body, "url": message.url},
                    ensure_ascii=False,
                ),
                vapid_private_key=self.private_key,
                vapid_claims={"sub": self.subject},
                ttl=24 * 60 * 60,
                timeout=10,
            )
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            return int(status) if status else 0
        except OSError:
            return 0
        return None


def enabled(settings: Settings) -> bool:
    return bool(settings.webpush_public_key and settings.webpush_private_key)


def get_push_sender() -> PushSender | None:
    """The sender, or None when push is not configured. Tests override it."""
    settings = get_settings()
    if not enabled(settings) or settings.webpush_private_key is None:
        return None
    return WebPushSender(settings.webpush_private_key.get_secret_value(), settings.webpush_subject)


def endpoint_allowed(endpoint: str) -> bool:
    from urllib.parse import urlparse

    parts = urlparse(endpoint)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and any(
        host.endswith(suffix) or host == suffix.lstrip(".") for suffix in ALLOWED_HOST_SUFFIXES
    )


def subscribe(
    db: Session, user: User, endpoint: str, keys: dict[str, str], user_agent: str | None
) -> PushSubscription:
    """Save this browser for the user. The same endpoint moves to whoever signs in on it."""
    row = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
    if row is None:
        row = PushSubscription(endpoint=endpoint, user_id=user.id, keys=keys)
        db.add(row)
    row.user_id, row.keys = user.id, keys
    row.user_agent = (user_agent or "")[:300] or None
    db.flush()
    return row


def unsubscribe(db: Session, user: User, endpoint: str) -> bool:
    row = db.scalar(
        select(PushSubscription).where(
            PushSubscription.endpoint == endpoint, PushSubscription.user_id == user.id
        )
    )
    if row is None:
        return False
    db.delete(row)
    db.flush()
    return True


def count_for(db: Session, user_id: uuid.UUID) -> int:
    return len(
        list(db.scalars(select(PushSubscription.id).where(PushSubscription.user_id == user_id)))
    )


def push_to_user(
    db: Session, sender: PushSender | None, user_id: uuid.UUID, message: PushMessage
) -> int:
    """Push to every browser of the user; returns how many accepted it. Browsers that have
    dropped the subscription (404, 410) are forgotten."""
    if sender is None:
        return 0
    delivered = 0
    for row in list(
        db.scalars(select(PushSubscription).where(PushSubscription.user_id == user_id))
    ):
        refused = sender.send(row, message)
        if refused is None:
            delivered += 1
        elif refused in (404, 410):
            db.delete(row)
        else:
            logger.warning("Push not delivered (status %s)", refused)
    db.flush()
    return delivered


def notice_message(title: str, body: str, link: str, base_url: str, locale: str) -> PushMessage:
    """Push text is short: the first line of the email body, cut at 180 characters."""
    first = body.strip().splitlines()[0] if body.strip() else ""
    text = first if len(first) <= 180 else first[:177] + "..."
    path = link if link.startswith("/") else f"/{link}"
    return PushMessage(title=title, body=text, url=f"{base_url}/{locale}{path}")


def describe(settings: Settings) -> dict[str, Any]:
    return {"enabled": enabled(settings), "public_key": settings.webpush_public_key}
