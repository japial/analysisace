"""Outgoing email behind an interface, so a provider can be chosen without touching callers.

Two senders (D24):

- `LoggingEmailSender` writes the message to the log. It is the default, and what
  development uses: a password reset link can be followed from the API log.
- `SmtpEmailSender` sends through any SMTP service. Amazon SES, Postmark, SendGrid, Mailgun,
  Resend and Brevo all offer SMTP, so choosing a provider is a matter of environment
  variables (`EMAIL_BACKEND=smtp`, `SMTP_HOST`, ...), not code.

Callers use `send_safely`: a failed send is logged and reported as False, and never breaks
the request or job that triggered it.
"""

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr
from typing import Protocol

from app.core.config import Settings, get_settings

logger = logging.getLogger("analysisace.email")


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    body: str


class EmailSendError(Exception):
    """The provider refused or could not be reached. The message holds no credentials."""


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
        message.set_content(email.body, charset="utf-8")
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
        except (smtplib.SMTPException, OSError) as exc:
            # The class name and SMTP code are enough to diagnose; never the password.
            code = getattr(exc, "smtp_code", None)
            raise EmailSendError(f"{type(exc).__name__}{f' {code}' if code else ''}") from None


def sender_from_settings(settings: Settings) -> EmailSender:
    if settings.email_backend == "smtp":
        if not settings.smtp_host:
            raise RuntimeError("EMAIL_BACKEND=smtp needs SMTP_HOST")
        return SmtpEmailSender(
            host=settings.smtp_host,
            port=settings.smtp_port,
            security=settings.smtp_security,
            sender=settings.email_from,
            username=settings.smtp_username,
            password=settings.smtp_password.get_secret_value() if settings.smtp_password else None,
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


def send_safely(sender: EmailSender, email: Email) -> bool:
    """Send, and report whether it went. A failure is logged without the address."""
    try:
        sender.send(email)
    except EmailSendError as exc:
        logger.error("Email not sent (%s): %s", exc, email.subject)
        return False
    return True


_RESET_TEXT = {
    "en": (
        "Reset your analysisACE password",
        "Someone asked to reset the password for this analysisACE account.\n\n"
        "Open this link within {minutes} minutes to choose a new password:\n{link}\n\n"
        "If this was not you, ignore this email. Your password stays the same.",
    ),
    "bn": (
        "আপনার analysisACE পাসওয়ার্ড পরিবর্তন করুন",
        "এই analysisACE অ্যাকাউন্টের পাসওয়ার্ড পরিবর্তনের অনুরোধ করা হয়েছে।\n\n"
        "নতুন পাসওয়ার্ড দিতে {minutes} মিনিটের মধ্যে এই লিংকটি খুলুন:\n{link}\n\n"
        "আপনি অনুরোধ না করে থাকলে এই ইমেইল উপেক্ষা করুন। আপনার পাসওয়ার্ড আগের মতোই থাকবে।",
    ),
}


def password_reset_email(to: str, locale: str, link: str, minutes: int) -> Email:
    subject, body = _RESET_TEXT.get(locale, _RESET_TEXT["en"])
    return Email(to=to, subject=subject, body=body.format(link=link, minutes=minutes))


_VERIFY_TEXT = {
    "en": (
        "Confirm your email for analysisACE",
        "Welcome to analysisACE.\n\n"
        "Open this link within {hours} hours to confirm this is your email address:\n{link}\n\n"
        "Until you do, reminders and monthly reports are not emailed to you. "
        "If you did not sign up, ignore this email.",
    ),
    "bn": (
        "analysisACE-এর জন্য আপনার ইমেইল নিশ্চিত করুন",
        "analysisACE-এ স্বাগতম।\n\n"
        "এটি আপনার ইমেইল ঠিকানা তা নিশ্চিত করতে {hours} ঘণ্টার মধ্যে এই লিংকটি খুলুন:\n{link}\n\n"
        "নিশ্চিত না করা পর্যন্ত তাগিদ ও মাসিক প্রতিবেদন ইমেইলে পাঠানো হবে না। "
        "আপনি নিবন্ধন না করে থাকলে এই ইমেইল উপেক্ষা করুন।",
    ),
}


def verification_email(to: str, locale: str, link: str, hours: int) -> Email:
    subject, body = _VERIFY_TEXT.get(locale, _VERIFY_TEXT["en"])
    return Email(to=to, subject=subject, body=body.format(link=link, hours=hours))


def job_failed_email(to: str, job: str, error: str, environment: str) -> Email:
    """For operators (FR M1: alert on failed jobs). English only: it goes to the team."""
    return Email(
        to=to,
        subject=f"[analysisACE {environment}] Job failed: {job}",
        body=(
            f"The scheduled job '{job}' failed.\n\n"
            f"Error: {error[:500]}\n\n"
            "Details are in the job runs table on /admin/audit and in the worker log."
        ),
    )
