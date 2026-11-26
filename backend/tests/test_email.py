"""Outgoing email (D24): the SMTP sender, choosing a sender from settings, and failures
that must not break requests or jobs."""

import smtplib
from email.message import EmailMessage
from typing import Any, ClassVar

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.jobs import worker
from app.services import email as mail
from app.services.email import Email, EmailSendError, LoggingEmailSender, SmtpEmailSender

MESSAGE = Email(to="karim@example.com", subject="যাকাতের তারিখ", body="Zakat date: ১ রমজান")


class FakeSMTP:
    """Stands in for smtplib.SMTP and SMTP_SSL and records what the sender did."""

    calls: ClassVar[list[tuple[str, Any]]] = []
    fail_with: ClassVar[Exception | None] = None

    def __init__(self, host: str, port: int, timeout: float = 0, context: Any = None) -> None:
        FakeSMTP.calls.append(("connect", (host, port, context is not None)))

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, *exc: object) -> None:
        FakeSMTP.calls.append(("quit", None))

    def starttls(self, context: Any = None) -> None:
        FakeSMTP.calls.append(("starttls", None))

    def login(self, user: str, password: str) -> None:
        FakeSMTP.calls.append(("login", user))

    def send_message(self, message: EmailMessage) -> None:
        if FakeSMTP.fail_with:
            raise FakeSMTP.fail_with
        FakeSMTP.calls.append(("send", message))


@pytest.fixture(autouse=True)
def fake_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeSMTP.calls, FakeSMTP.fail_with = [], None
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)


def _sender(**overrides: Any) -> SmtpEmailSender:
    options: dict[str, Any] = {
        "host": "smtp.example.com",
        "port": 587,
        "security": "starttls",
        "sender": "analysisACE <no-reply@analysisace.com>",
        "username": "apikey",
        "password": "secret-value",
        "reply_to": "help@analysisace.com",
    }
    options.update(overrides)
    return SmtpEmailSender(**options)


def test_smtp_sends_utf8_plain_text_over_starttls_d24() -> None:
    _sender().send(MESSAGE)
    steps = [name for name, _ in FakeSMTP.calls]
    assert steps == ["connect", "starttls", "login", "send", "quit"]
    sent: EmailMessage = FakeSMTP.calls[3][1]
    assert sent["To"] == "karim@example.com" and sent["Reply-To"] == "help@analysisace.com"
    assert sent["Subject"] == "যাকাতের তারিখ"
    assert sent["Message-ID"].endswith("@analysisace.com>")
    assert "১ রমজান" in sent.get_content()


def test_smtp_implicit_tls_and_no_login_d24() -> None:
    _sender(port=465, security="ssl", username=None, password=None).send(MESSAGE)
    assert [name for name, _ in FakeSMTP.calls] == ["connect", "send", "quit"]
    assert FakeSMTP.calls[0][1] == ("smtp.example.com", 465, True)


def test_smtp_failure_is_an_email_error_without_the_password_d24() -> None:
    FakeSMTP.fail_with = smtplib.SMTPAuthenticationError(535, b"secret-value rejected")
    with pytest.raises(EmailSendError) as caught:
        _sender().send(MESSAGE)
    assert "secret-value" not in str(caught.value)
    assert "535" in str(caught.value)


def test_send_safely_reports_failure_instead_of_raising_d24() -> None:
    FakeSMTP.fail_with = OSError("connection refused")
    assert mail.send_safely(_sender(), MESSAGE) is False
    FakeSMTP.fail_with = None
    assert mail.send_safely(_sender(), MESSAGE) is True


def test_sender_chosen_from_settings_d24() -> None:
    assert isinstance(mail.sender_from_settings(Settings(email_backend="log")), LoggingEmailSender)
    smtp = mail.sender_from_settings(
        Settings(
            email_backend="smtp",
            smtp_host="email-smtp.ap-south-1.amazonaws.com",
            smtp_username="AKIA",
            smtp_password=SecretStr("pw"),
        )
    )
    assert isinstance(smtp, SmtpEmailSender) and smtp.password == "pw"
    with pytest.raises(RuntimeError):
        mail.sender_from_settings(Settings(email_backend="smtp", smtp_host=None))


def test_production_with_log_backend_is_reported_d24(caplog: pytest.LogCaptureFixture) -> None:
    mail.check_email_settings(Settings(environment="production", email_backend="log"))
    assert "not delivered" in caplog.text
    caplog.clear()
    mail.check_email_settings(Settings(environment="development", email_backend="log"))
    assert caplog.text == ""


def test_failed_job_emails_operators_m1(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[Email] = []

    class Box:
        def send(self, email: Email) -> None:
            sent.append(email)

    monkeypatch.setattr(worker, "get_email_sender", lambda: Box())
    monkeypatch.setattr(
        worker,
        "get_settings",
        lambda: Settings(environment="production", ops_alert_emails="ops@a.com, dev@a.com"),
    )
    assert worker.notify_operators("market_analytics", "ValueError('x')") == 2
    assert {e.to for e in sent} == {"ops@a.com", "dev@a.com"}
    assert sent[0].subject == "[analysisACE production] Job failed: market_analytics"


def test_alert_stays_in_the_app_when_its_email_fails_fr20_d24(demo_session) -> None:  # type: ignore[no-untyped-def]
    """The notice is kept and marked not emailed (sent_at empty) when the provider fails."""
    from sqlalchemy import select

    from app.models import AlertRule, User
    from app.seed.demo_personal import DEMO_EMAIL
    from app.services import alerts

    class Broken:
        def send(self, email: Email) -> None:
            raise EmailSendError("SMTPServerDisconnected")

    user = demo_session.scalar(select(User).where(User.email == DEMO_EMAIL))
    rule = demo_session.scalar(
        select(AlertRule).where(
            AlertRule.user_id == user.id, AlertRule.channel.in_(("EMAIL", "BOTH"))
        )
    )
    assert rule is not None
    row = alerts.notify(
        demo_session,
        Broken(),
        user,
        type=rule.type,
        message_key="GOAL_REACHED",
        data={"name": "Test goal"},
        link="/personal/goals",
        dedupe_key="test:email-failure",
        rules={rule.type: rule},
    )
    assert row is not None and row.sent_at is None


def test_alert_email_waits_for_a_confirmed_address_d25(demo_session) -> None:  # type: ignore[no-untyped-def]
    """An unconfirmed address gets the notice in the app but no email."""
    from sqlalchemy import select

    from app.models import AlertRule, User
    from app.seed.demo_personal import DEMO_EMAIL
    from app.services import alerts

    sent: list[Email] = []

    class Box:
        def send(self, email: Email) -> None:
            sent.append(email)

    user = demo_session.scalar(select(User).where(User.email == DEMO_EMAIL))
    rule = demo_session.scalar(
        select(AlertRule).where(
            AlertRule.user_id == user.id, AlertRule.channel.in_(("EMAIL", "BOTH"))
        )
    )
    user.email_verified_at = None
    row = alerts.notify(
        demo_session,
        Box(),
        user,
        type=rule.type,
        message_key="GOAL_REACHED",
        data={"name": "Test goal"},
        link="/personal/goals",
        dedupe_key="test:unverified",
        rules={rule.type: rule},
    )
    assert row is not None and row.sent_at is None and sent == []


def test_gmail_from_the_account_and_app_password_without_spaces_d27() -> None:
    """Gmail: From defaults to the account, and the app password's display spaces go."""
    settings = Settings(
        email_backend="smtp",
        smtp_username="analysisace.bd@gmail.com",
        smtp_password=SecretStr("abcd efgh ijkl mnop"),
    )
    sender = mail.sender_from_settings(settings)
    assert isinstance(sender, SmtpEmailSender)
    assert sender.host == "smtp.gmail.com" and sender.port == 587
    assert sender.security == "starttls"
    assert sender.sender == "analysisACE <analysisace.bd@gmail.com>"
    assert sender.password == "abcdefghijklmnop"

    sender.send(MESSAGE)
    sent: EmailMessage = next(m for name, m in FakeSMTP.calls if name == "send")
    assert sent["From"] == "analysisACE <analysisace.bd@gmail.com>"
    assert sent["Message-ID"].endswith("@gmail.com>")


def test_explicit_from_and_other_hosts_keep_the_password_d27() -> None:
    settings = Settings(
        email_backend="smtp",
        smtp_host="smtp.example.com",
        email_from="Team <team@analysisace.com>",
        smtp_username="user",
        smtp_password=SecretStr("pass with spaces"),
    )
    assert mail.from_address(settings) == "Team <team@analysisace.com>"
    assert mail.smtp_password(settings) == "pass with spaces"


def test_missing_gmail_credentials_are_reported_d27(caplog: pytest.LogCaptureFixture) -> None:
    mail.check_email_settings(Settings(environment="production", email_backend="smtp"))
    assert "SMTP_USERNAME, SMTP_PASSWORD not set" in caplog.text
    caplog.clear()
    mail.check_email_settings(
        Settings(
            environment="production",
            email_backend="smtp",
            smtp_username="analysisace.bd@gmail.com",
            smtp_password=SecretStr("x"),
            email_from="analysisACE <no-reply@analysisace.com>",
        )
    )
    assert "not the Gmail account" in caplog.text
