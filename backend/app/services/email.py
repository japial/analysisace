"""Outgoing email behind an interface, so a provider can be added without touching callers.

No transactional email provider is chosen yet (PRD section 11). Until one is, messages are
written to the log, which is enough to follow a password reset link in development.
"""

import logging
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger("analysisace.email")


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    body: str


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


def get_email_sender() -> EmailSender:
    """FastAPI dependency. Tests override it to capture messages."""
    return LoggingEmailSender()


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
