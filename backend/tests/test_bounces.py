"""Bounced email (D35): addresses that do not work stop getting alert and report emails."""

import smtplib
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.jobs.worker import cron_trigger
from app.models import AuditLog, User
from app.services import auth, bounces
from app.services.email import Email, EmailSendError, SmtpEmailSender
from tests.test_digest import Outbox, _goal, _rule, _user

SENDER = "analysisace.bd@gmail.com"


def _dsn(recipient: str, action: str, status: str, diagnostic: str = "") -> bytes:
    """A delivery report shaped like the ones Gmail sends back (RFC 3464)."""
    return f"""\
From: Mail Delivery Subsystem <mailer-daemon@googlemail.com>
To: {SENDER}
Subject: Delivery Status Notification (Failure)
MIME-Version: 1.0
Content-Type: multipart/report; report-type=delivery-status; boundary="b1"

--b1
Content-Type: text/plain; charset="UTF-8"

Address not found. Your message wasn't delivered to {recipient}.

--b1
Content-Type: message/delivery-status

Reporting-MTA: dns; googlemail.com
Arrival-Date: Fri, 27 Nov 2026 02:10:01 -0800 (PST)

Final-Recipient: rfc822; {recipient}
Action: {action}
Status: {status}
Remote-MTA: dns; mx.example.com. (192.0.2.1, the server for the domain example.com.)
Diagnostic-Code: smtp; {diagnostic or status + " The email account does not exist."}

--b1
Content-Type: text/rfc822-headers

From: analysisACE <{SENDER}>
To: {recipient}
Subject: Goal reached: First crore

--b1--
""".replace("\n", "\r\n").encode()


def test_a_report_of_no_such_mailbox_is_a_pausing_bounce_d35() -> None:
    (bounce,) = bounces.parse_bounce(_dsn("Karim@Example.com", "failed", "5.1.1"))
    assert bounce == bounces.Bounce("karim@example.com", "5.1.1")
    assert bounces.pauses(bounce.status)


def test_delays_and_full_mailboxes_do_not_pause_d35() -> None:
    assert bounces.parse_bounce(_dsn("k@example.com", "delayed", "4.4.7")) == []
    (full,) = bounces.parse_bounce(_dsn("k@example.com", "failed", "5.2.2"))
    assert not bounces.pauses(full.status)
    assert not bounces.pauses("5.7.1")  # a policy refusal is about the sender


def test_x_failed_recipients_is_used_without_a_delivery_report_d35() -> None:
    raw = (
        b"From: mailer-daemon@googlemail.com\r\nX-Failed-Recipients: gone@example.com\r\n"
        b"Subject: Delivery Status Notification (Failure)\r\nContent-Type: text/plain\r\n\r\n"
        b"550 5.1.1 The email account that you tried to reach does not exist.\r\n"
    )
    assert bounces.parse_bounce(raw) == [bounces.Bounce("gone@example.com", "5.1.1")]
    ordinary = b"From: friend@example.com\r\nSubject: Hello\r\n\r\nHi\r\n"
    assert bounces.parse_bounce(ordinary) == []


class FakeMailbox:
    def __init__(self, reports: list[bytes]) -> None:
        self.reports = {str(i).encode(): raw for i, raw in enumerate(reports)}
        self.seen: list[bytes] = []

    def unseen_reports(self, limit: int) -> list[tuple[bytes, bytes]]:
        return [(k, v) for k, v in self.reports.items() if k not in self.seen][:limit]

    def mark_seen(self, message_id: bytes) -> None:
        self.seen.append(message_id)


def test_the_mailbox_job_pauses_email_and_marks_reports_read_d35(demo_session: Session) -> None:
    user = _user(demo_session)
    mailbox = FakeMailbox(
        [
            _dsn(user.email.upper(), "failed", "5.1.1"),
            _dsn("nobody-here@example.com", "failed", "5.1.1"),  # not an account
            _dsn(user.email, "delayed", "4.4.7"),
        ]
    )
    counts = bounces.process_mailbox(demo_session, mailbox)
    assert counts == {"reports": 3, "bounces": 2, "paused": 1}
    assert sorted(mailbox.seen) == [b"0", b"1", b"2"]
    assert user.email_bounced_at is not None and user.email_bounce_status == "5.1.1"
    assert not bounces.can_email(user)
    entry = demo_session.scalar(select(AuditLog).where(AuditLog.action == "EMAIL_BOUNCED"))
    assert entry is not None and entry.after == {"status": "5.1.1"}
    assert user.email not in str(entry.after)  # ids and codes only
    # Read reports are not read again.
    assert bounces.process_mailbox(demo_session, mailbox)["reports"] == 0


def test_a_paused_address_gets_no_alert_email_but_keeps_the_notice_d35(
    demo_session: Session,
) -> None:
    user = _user(demo_session)
    _rule(demo_session, user, "GOAL_REACHED", "EMAIL", "INSTANT")
    bounces.record(demo_session, user, "5.1.1")
    outbox = Outbox()
    row = _goal(demo_session, outbox, user, "Paused")
    assert row is not None and outbox.sent == [] and row.sent_at is None


class RefusingSender:
    def send(self, email: Email) -> None:
        raise EmailSendError("SMTPRecipientsRefused 550", "5.1.1")


def test_a_refusal_while_sending_counts_as_a_bounce_d35(demo_session: Session) -> None:
    user = _user(demo_session)
    _rule(demo_session, user, "GOAL_REACHED", "EMAIL", "INSTANT")
    row = _goal(demo_session, RefusingSender(), user, "Refused")
    assert row is not None and row.sent_at is None
    assert user.email_bounce_status == "5.1.1"


def test_smtp_recipient_refusal_carries_the_status_d35(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSMTP:
        def __init__(self, *args: Any, **kwargs: Any) -> None: ...
        def __enter__(self) -> "FakeSMTP":
            return self

        def __exit__(self, *args: Any) -> None: ...
        def starttls(self, **kwargs: Any) -> None: ...
        def login(self, *args: Any) -> None: ...
        def send_message(self, message: Any) -> None:
            raise smtplib.SMTPRecipientsRefused(
                {"gone@example.com": (550, b"5.1.1 The email account does not exist.")}
            )

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    sender = SmtpEmailSender(
        host="smtp.example.com",
        port=587,
        security="starttls",
        username=None,
        password=None,
        sender=SENDER,
    )
    with pytest.raises(EmailSendError) as caught:
        sender.send(Email(to="gone@example.com", subject="S", body="B"))
    assert caught.value.refused_status == "5.1.1"
    assert "gone@example.com" not in str(caught.value)


def test_confirming_the_address_again_resumes_email_d35(demo_session: Session) -> None:
    user = _user(demo_session)
    bounces.record(demo_session, user, "5.1.1")
    outbox = Outbox()
    assert auth.start_email_verification(demo_session, user, outbox, Settings())
    (mail,) = outbox.sent
    token = mail.body.split("verify-email?token=")[1].split()[0]
    auth.confirm_email_verification(demo_session, token)
    assert user.email_bounced_at is None and bounces.can_email(user)
    cleared = demo_session.scalar(select(AuditLog).where(AuditLog.action == "EMAIL_BOUNCE_CLEARED"))
    assert cleared is not None and cleared.before == {"status": "5.1.1"}
    # A confirmed address that never bounced has nothing to confirm.
    assert not auth.start_email_verification(demo_session, user, outbox, Settings())


def test_the_export_shows_a_paused_address_d35(demo_session: Session) -> None:
    user = _user(demo_session)
    bounces.record(demo_session, user, "5.1.1")
    exported = auth.export_user_data(demo_session, user)
    assert exported["account"]["email_bounced_at"] is not None


def test_imap_mailbox_peeks_and_marks_only_what_it_handled_d35() -> None:
    class FakeImap:
        def __init__(self) -> None:
            self.calls: list[tuple[Any, ...]] = []

        def uid(self, command: str, *args: Any) -> tuple[str, list[Any]]:
            self.calls.append((command, *args))
            if command == "SEARCH":
                return "OK", [b"7 9"]
            if command == "FETCH":
                return "OK", [(b"7 (UID 7 BODY[] {5}", b"raw-" + args[0].encode()), b")"]
            return "OK", []

    client = FakeImap()
    mailbox = bounces.ImapMailbox(client)  # type: ignore[arg-type]
    assert mailbox.unseen_reports(1) == [(b"7", b"raw-7")]
    assert client.calls[1] == ("FETCH", "7", "(BODY.PEEK[])")
    mailbox.mark_seen(b"7")
    assert client.calls[-1] == ("STORE", "7", "+FLAGS", "(\\Seen)")


def test_bounce_reading_needs_smtp_and_a_mailbox_d35() -> None:
    assert not bounces.imap_configured(Settings(email_backend="log"))
    on = Settings(email_backend="smtp", smtp_username=SENDER, smtp_password="abcd efgh ijkl mnop")
    assert bounces.imap_configured(on)
    assert not bounces.imap_configured(on.model_copy(update={"bounce_imap_host": ""}))


def test_every_hours_repeats_a_schedule_d35() -> None:
    trigger = cron_trigger({"days": "daily", "at": "00:10", "every_hours": 1}, "Asia/Dhaka")
    assert "hour='0-23/1'" in str(trigger) and "minute='10'" in str(trigger)


def test_user_out_reports_the_pause_d35(demo_session: Session) -> None:
    from app.schemas.auth import UserOut

    user = demo_session.scalar(select(User).limit(1))
    assert user is not None
    bounces.record(demo_session, user, "5.1.1")
    assert UserOut.model_validate(user).email_bounced_at is not None
