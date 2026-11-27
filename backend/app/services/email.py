"""Outgoing email behind an interface, so a provider can be chosen without touching callers.

Two senders (D24):

- `LoggingEmailSender` writes the message to the log. It is the default, and what
  development uses: a password reset link can be followed from the API log.
- `SmtpEmailSender` sends through any SMTP service. Production uses Gmail SMTP (D27):
  `EMAIL_BACKEND=smtp`, `SMTP_USERNAME` (the Gmail address) and `SMTP_PASSWORD` (an app
  password). Another provider is only a change of the `SMTP_*` variables.

Callers use `send_safely`: a failed send is logged and reported as False, and never breaks
the request or job that triggered it.
"""

import logging
import re
import smtplib
import ssl
from collections.abc import Mapping
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid, parseaddr
from typing import Protocol

from app.core.config import Settings, get_settings

logger = logging.getLogger("analysisace.email")


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    # The plain-text part; always present.
    body: str
    # The HTML part (D31). With it the message is multipart/alternative.
    html: str | None = None
    # Extra headers, such as List-Unsubscribe.
    headers: Mapping[str, str] = field(default_factory=dict)


class EmailSendError(Exception):
    """The provider refused or could not be reached. The message holds no credentials.

    `refused_status` is set when the server refused the recipient itself with a permanent
    error, as an enhanced status code such as "5.1.1" (D35)."""

    def __init__(self, message: str, refused_status: str | None = None) -> None:
        super().__init__(message)
        self.refused_status = refused_status


class EmailSender(Protocol):
    def send(self, email: Email) -> None: ...


class LoggingEmailSender:
    """Development stand-in: prints the message instead of sending it."""

    def send(self, email: Email) -> None:
        logger.warning(
            "EMAIL NOT SENT (no provider configured)\nTo: %s\nSubject: %s\n\n%s",
            email.to,
            email.subject,
            email.body,
        )


class SmtpEmailSender:
    """Plain-text mail over SMTP with STARTTLS (port 587) or implicit TLS (port 465)."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        security: str,
        sender: str,
        username: str | None = None,
        password: str | None = None,
        reply_to: str | None = None,
        timeout: float = 15,
    ) -> None:
        if security not in ("starttls", "ssl", "none"):
            raise ValueError(f"Unknown SMTP security: {security}")
        self.host, self.port, self.security = host, port, security
        self.sender, self.reply_to = sender, reply_to
        self.username, self.password = username, password
        self.timeout = timeout

    def message(self, email: Email) -> EmailMessage:
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = email.to
        message["Subject"] = email.subject
        message["Date"] = formatdate(localtime=False)
        domain = parseaddr(self.sender)[1].rpartition("@")[2] or None
        message["Message-ID"] = make_msgid(domain=domain)
        if self.reply_to:
            message["Reply-To"] = self.reply_to
        for name, value in email.headers.items():
            message[name] = value
        message.set_content(email.body, charset="utf-8")
        if email.html:
            # Mail apps show the last part they can display: HTML, else the text above.
            message.add_alternative(email.html, subtype="html", charset="utf-8")
        return message

    def send(self, email: Email) -> None:
        message = self.message(email)
        context = ssl.create_default_context()
        try:
            if self.security == "ssl":
                server: smtplib.SMTP = smtplib.SMTP_SSL(
                    self.host, self.port, timeout=self.timeout, context=context
                )
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
            with server:
                if self.security == "starttls":
                    server.starttls(context=context)
                if self.username:
                    server.login(self.username, self.password or "")
                server.send_message(message)
        except smtplib.SMTPRecipientsRefused as exc:
            codes = [(code, reply) for code, reply in exc.recipients.values()]
            permanent = [(c, r) for c, r in codes if 500 <= c < 600]
            status = None
            if permanent:
                refused, reply = permanent[0]
                text = reply.decode("utf-8", "replace") if isinstance(reply, bytes) else str(reply)
                found = re.search(r"\b5\.\d{1,3}\.\d{1,3}\b", text)
                status = found.group(0) if found else f"5.0.{refused % 100}"
            code_text = f" {codes[0][0]}" if codes else ""
            raise EmailSendError(f"SMTPRecipientsRefused{code_text}", status) from None
        except (smtplib.SMTPException, OSError) as exc:
            # The class name and SMTP code are enough to diagnose; never the password.
            code = getattr(exc, "smtp_code", None)
            raise EmailSendError(f"{type(exc).__name__}{f' {code}' if code else ''}") from None


GMAIL_HOSTS = ("smtp.gmail.com", "smtp.googlemail.com")


def is_gmail(settings: Settings) -> bool:
    return (settings.smtp_host or "").strip().lower() in GMAIL_HOSTS


def from_address(settings: Settings) -> str:
    """EMAIL_FROM if set; otherwise the SMTP account with the display name (D27)."""
    if settings.email_from:
        return settings.email_from
    if settings.smtp_username:
        return formataddr((settings.email_from_name, settings.smtp_username))
    return formataddr((settings.email_from_name, "no-reply@analysisace.com"))


def smtp_password(settings: Settings) -> str | None:
    """Google shows an app password as four groups of letters ("abcd efgh ijkl mnop");
    the spaces are not part of it."""
    if settings.smtp_password is None:
        return None
    value = settings.smtp_password.get_secret_value()
    return "".join(value.split()) if is_gmail(settings) else value


def sender_from_settings(settings: Settings) -> EmailSender:
    if settings.email_backend == "smtp":
        if not settings.smtp_host:
            raise RuntimeError("EMAIL_BACKEND=smtp needs SMTP_HOST")
        return SmtpEmailSender(
            host=settings.smtp_host,
            port=settings.smtp_port,
            security=settings.smtp_security,
            sender=from_address(settings),
            username=settings.smtp_username,
            password=smtp_password(settings),
            reply_to=settings.email_reply_to,
            timeout=settings.smtp_timeout_seconds,
        )
    return LoggingEmailSender()


def get_email_sender() -> EmailSender:
    """FastAPI dependency and the worker's sender. Tests override it to capture messages."""
    return sender_from_settings(get_settings())


def check_email_settings(settings: Settings) -> None:
    """Called at start-up: outside development, mail that only reaches the log is a fault."""
    if settings.environment != "development" and settings.email_backend == "log":
        logger.error(
            "EMAIL_BACKEND is 'log' in %s: password resets, alerts and reports are not "
            "delivered. Set EMAIL_BACKEND=smtp and the SMTP_* variables.",
            settings.environment,
        )
    if settings.email_backend == "smtp":
        missing = [
            name
            for name, value in (
                ("SMTP_HOST", settings.smtp_host),
                ("SMTP_USERNAME", settings.smtp_username),
                ("SMTP_PASSWORD", settings.smtp_password),
            )
            if not value
        ]
        if missing:
            logger.error("EMAIL_BACKEND=smtp but %s not set: email will fail.", ", ".join(missing))
        if is_gmail(settings) and settings.email_from and settings.smtp_username:
            account = settings.smtp_username.strip().lower()
            if account not in settings.email_from.lower():
                logger.warning(
                    "EMAIL_FROM is not the Gmail account; Gmail sends it from the account "
                    "unless the address is a verified 'Send mail as' alias."
                )


def send_safely(sender: EmailSender, email: Email) -> bool:
    """Send, and report whether it went. A failure is logged without the address."""
    try:
        sender.send(email)
    except EmailSendError as exc:
        logger.error("Email not sent (%s): %s", exc, email.subject)
        return False
    return True
