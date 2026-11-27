"""Bounced email (D35): stop emailing an address that does not work.

A bounce is learnt two ways. Gmail accepts almost every message and reports failures later
as "Delivery Status Notification" emails to the sending account, so a job reads that
mailbox over IMAP (`ImapMailbox`, the same app password as SMTP) and parses each report
(RFC 3464). A server that refuses a recipient while sending counts too.

Only failures that mean the address itself does not work (`config/email.yaml`) pause the
person's alert and report emails. Their notices stay in the app, the web app asks them to
confirm the address again, and confirming it lifts the pause. Account emails (password
reset, email confirmation) are still sent when asked for: that is how the person recovers.
"""

import email
import imaplib
import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from email.message import Message
from email.utils import getaddresses
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.app_config import get_config
from app.core.config import Settings
from app.core.security import utcnow
from app.models import User
from app.services.auth import audit
from app.services.email import (
    Email,
    EmailSender,
    EmailSendError,
    smtp_password,
)

logger = logging.getLogger(__name__)

_STATUS = re.compile(r"\b([245])\.(\d{1,3})\.(\d{1,3})\b")


@dataclass(frozen=True)
class Bounce:
    recipient: str
    status: str  # an enhanced status code such as "5.1.1"


def _rules() -> dict[str, Any]:
    return dict(get_config("email").data["bounces"])


def pauses(status: str) -> bool:
    """Whether a failure means the address itself does not work (config/email.yaml)."""
    return any(status.startswith(prefix) for prefix in _rules()["pause_on_status"])


def _status(text: str) -> str | None:
    match = _STATUS.search(text)
    return ".".join(match.groups()) if match else None


def _address(field: str) -> str:
    # "rfc822; someone@example.com" -> "someone@example.com"
    return field.split(";", 1)[-1].strip().strip("<>").lower()


def parse_bounce(raw: bytes) -> list[Bounce]:
    """The permanent failures in one bounce report. Delays and successes are left out, and
    a message that is not a bounce report gives an empty list."""
    message = email.message_from_bytes(raw)
    found: dict[str, str] = {}
    for part in message.walk():
        if part.get_content_type() != "message/delivery-status":
            continue
        blocks = part.get_payload()
        for block in blocks if isinstance(blocks, list) else []:
            if not isinstance(block, Message):
                continue
            recipient = block.get("Final-Recipient") or block.get("Original-Recipient")
            action = str(block.get("Action", "")).strip().lower()
            status = _status(str(block.get("Status", "")))
            if recipient and action == "failed" and status and status.startswith("5"):
                found[_address(str(recipient))] = status
    if not found and _rules()["trust_failed_recipients_header"]:
        failed = message.get_all("X-Failed-Recipients") or []
        text = _plain_text(message)
        for _, address in getaddresses([str(value) for value in failed]):
            if address:
                found[address.lower()] = _status(text) or "5.1.0"
    return [Bounce(recipient, status) for recipient, status in found.items()]


def _plain_text(message: Message) -> str:
    for part in message.walk():
        if part.get_content_type() == "text/plain":
            payload = part.get_payload(decode=True)
            if isinstance(payload, bytes):
                return payload.decode(part.get_content_charset() or "utf-8", "replace")
    return ""


# --- recording ------------------------------------------------------------------------


def can_email(user: User) -> bool:
    """Alert and report emails go only to a confirmed address that has not bounced."""
    return user.email_verified_at is not None and user.email_bounced_at is None


def record(db: Session, user: User, status: str) -> bool:
    """Pause alert and report emails to this person when the failure means the address does
    not work. Returns whether it did."""
    if not pauses(status) or user.email_bounced_at is not None:
        return False
    user.email_bounced_at = utcnow()
    user.email_bounce_status = status
    audit(db, "system", "EMAIL_BOUNCED", "app_user", str(user.id), after={"status": status})
    db.flush()
    return True


def send_to(db: Session, sender: EmailSender, user: User, message: Email) -> bool:
    """Send an alert or report email, and record a bounce if the server refuses the address
    outright. Returns whether it went; a failure is logged without the address."""
    try:
        sender.send(message)
    except EmailSendError as exc:
        logger.error("Email not sent (%s): %s", exc, message.subject)
        if exc.refused_status:
            record(db, user, exc.refused_status)
        return False
    return True


# --- the bounce mailbox ---------------------------------------------------------------


class Mailbox(Protocol):
    def unseen_reports(self, limit: int) -> list[tuple[bytes, bytes]]:
        """Up to `limit` unread bounce reports as (id, raw message)."""
        ...

    def mark_seen(self, message_id: bytes) -> None: ...


class ImapMailbox:
    """The sending account's inbox over IMAP with TLS. Only messages from the mail system
    (mailer-daemon, postmaster) are read; nothing else is opened or changed."""

    SEARCH = '(UNSEEN OR FROM "mailer-daemon" FROM "postmaster")'

    def __init__(self, client: imaplib.IMAP4) -> None:
        self.client = client

    def unseen_reports(self, limit: int) -> list[tuple[bytes, bytes]]:
        status, data = self.client.uid("SEARCH", None, self.SEARCH)  # type: ignore[arg-type]
        if status != "OK" or not data or not data[0]:
            return []
        reports: list[tuple[bytes, bytes]] = []
        for uid in data[0].split()[:limit]:
            # BODY.PEEK leaves the message unread until it has been handled.
            status, parts = self.client.uid("FETCH", uid.decode(), "(BODY.PEEK[])")
            raw = next((p[1] for p in parts or [] if isinstance(p, tuple) and len(p) > 1), None)
            if status == "OK" and isinstance(raw, bytes):
                reports.append((uid, raw))
        return reports

    def mark_seen(self, message_id: bytes) -> None:
        self.client.uid("STORE", message_id.decode(), "+FLAGS", "(\\Seen)")


def imap_configured(settings: Settings) -> bool:
    return bool(
        settings.email_backend == "smtp"
        and settings.bounce_imap_host
        and (settings.bounce_imap_username or settings.smtp_username)
        and (settings.bounce_imap_password or settings.smtp_password)
    )


@contextmanager
def open_mailbox(settings: Settings) -> Iterator[ImapMailbox]:
    """Sign in to the bounce mailbox. The username and app password default to the SMTP
    ones, which is right for Gmail: bounces come back to the sending account."""
    username = settings.bounce_imap_username or settings.smtp_username or ""
    if settings.bounce_imap_password:
        password = settings.bounce_imap_password.get_secret_value()
    else:
        password = smtp_password(settings) or ""
    client = imaplib.IMAP4_SSL(
        settings.bounce_imap_host or "", settings.bounce_imap_port, timeout=30
    )
    try:
        client.login(username, password)
        client.select(settings.bounce_imap_folder)
        yield ImapMailbox(client)
    finally:
        with suppress(imaplib.IMAP4.error, OSError):
            client.logout()


def process_mailbox(db: Session, mailbox: Mailbox) -> dict[str, int]:
    """Read unread bounce reports, pause email to addresses that do not work, and mark each
    report read. Addresses that belong to no account are skipped."""
    rules = _rules()
    counts = {"reports": 0, "bounces": 0, "paused": 0}
    for message_id, raw in mailbox.unseen_reports(int(rules["max_messages_per_run"])):
        counts["reports"] += 1
        for bounce in parse_bounce(raw):
            counts["bounces"] += 1
            user = db.scalar(select(User).where(func.lower(User.email) == bounce.recipient))
            if user is not None and record(db, user, bounce.status):
                counts["paused"] += 1
        mailbox.mark_seen(message_id)
    db.flush()
    return counts
