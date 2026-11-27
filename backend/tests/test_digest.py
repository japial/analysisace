"""Daily alert digest (FR7.3, D32): "once a day" alerts wait for one email and one push."""

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AlertRule, Notification, PushSubscription, User
from app.seed.demo_personal import DEMO_EMAIL
from app.services import alerts, push
from app.services import email_templates as templates
from app.services.email import Email, EmailSendError
from app.services.email_render import Item

FCM = "https://fcm.googleapis.com/fcm/send/digest-device"


class Outbox:
    def __init__(self, fail: bool = False) -> None:
        self.sent: list[Email] = []
        self.fail = fail

    def send(self, email: Email) -> None:
        if self.fail:
            raise EmailSendError("SMTPServerDisconnected")
        self.sent.append(email)


class Pushes:
    def __init__(self) -> None:
        self.sent: list[push.PushMessage] = []

    def send(self, subscription: PushSubscription, message: push.PushMessage) -> int | None:
        self.sent.append(message)
        return None


def _user(session: Session) -> User:
    user = session.scalar(select(User).where(User.email == DEMO_EMAIL))
    assert user is not None
    return user


def _rule(session: Session, user: User, kind: str, channel: str, frequency: str) -> AlertRule:
    rule = session.scalar(
        select(AlertRule).where(AlertRule.user_id == user.id, AlertRule.type == kind)
    )
    if rule is None:
        rule = AlertRule(
            user_id=user.id, type=kind, channel=channel, frequency=frequency, params={}
        )
        session.add(rule)
    rule.channel, rule.frequency, rule.is_active = channel, frequency, True
    session.flush()
    return rule


def _goal(session: Session, sender: Any, user: User, name: str) -> Notification | None:
    return alerts.notify(
        session,
        sender,
        user,
        type="GOAL_REACHED",
        message_key="GOAL_REACHED",
        data={"name": name},
        link="/personal/goals",
        dedupe_key=f"test:digest:{name}",
    )


def _hawl(session: Session, sender: Any, user: User) -> Notification | None:
    return alerts.notify(
        session,
        sender,
        user,
        type="HAWL_APPROACHING",
        message_key="HAWL_APPROACHING",
        data={"name": "Karim", "date": "2027-02-01", "days": "30"},
        link="/personal/zakat",
        dedupe_key="test:digest:hawl",
    )


def test_once_a_day_alerts_wait_for_one_email_fr7_3(demo_session: Session) -> None:
    user = _user(demo_session)
    _rule(demo_session, user, "GOAL_REACHED", "EMAIL", "DAILY_DIGEST")
    _rule(demo_session, user, "HAWL_APPROACHING", "EMAIL", "DAILY_DIGEST")
    outbox = Outbox()
    first = _goal(demo_session, outbox, user, "First crore")
    second = _hawl(demo_session, outbox, user)
    assert first is not None and second is not None
    # Nothing is emailed when the alert is raised; both wait, and both are in the app.
    assert outbox.sent == []
    assert first.digest_channel == "EMAIL" and first.sent_at is None and first.digested_at is None

    assert alerts.send_digests(demo_session, outbox) == 1
    assert len(outbox.sent) == 1
    digest = outbox.sent[0]
    assert digest.subject == "2 new notices from analysisACE"
    assert "First crore" in digest.body and "1 February 2027" in digest.body
    assert digest.html and "First crore" in digest.html
    assert "/en/unsubscribe/one-click?t=" in digest.headers["List-Unsubscribe"]  # D34
    assert first.digested_at is not None and first.sent_at is not None

    # A second run has nothing left to send.
    assert alerts.send_digests(demo_session, outbox) == 0
    assert len(outbox.sent) == 1


def test_straight_away_alerts_are_not_held_fr7_3(demo_session: Session) -> None:
    user = _user(demo_session)
    _rule(demo_session, user, "GOAL_REACHED", "EMAIL", "INSTANT")
    outbox = Outbox()
    row = _goal(demo_session, outbox, user, "Instant goal")
    assert row is not None and row.digest_channel is None and row.sent_at is not None
    assert len(outbox.sent) == 1
    assert alerts.send_digests(demo_session, outbox) == 0


def test_a_failed_digest_email_keeps_the_notices_for_next_time_fr7_3(
    demo_session: Session,
) -> None:
    user = _user(demo_session)
    _rule(demo_session, user, "GOAL_REACHED", "EMAIL", "DAILY_DIGEST")
    row = _goal(demo_session, Outbox(), user, "Retry goal")
    assert row is not None
    assert alerts.send_digests(demo_session, Outbox(fail=True)) == 0
    assert row.digested_at is None and row.sent_at is None
    outbox = Outbox()
    assert alerts.send_digests(demo_session, outbox) == 1
    assert len(outbox.sent) == 1 and row.digested_at is not None


def test_unconfirmed_address_gets_no_digest_email_fr7_3_d25(demo_session: Session) -> None:
    user = _user(demo_session)
    user.email_verified_at = None
    _rule(demo_session, user, "GOAL_REACHED", "EMAIL", "DAILY_DIGEST")
    row = _goal(demo_session, Outbox(), user, "Unconfirmed goal")
    outbox = Outbox()
    alerts.send_digests(demo_session, outbox)
    assert outbox.sent == []
    assert row is not None and row.digested_at is not None and row.sent_at is None


def test_push_digest_is_one_summary_fr7_3_d26(
    demo_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _user(demo_session)
    pushes = Pushes()
    monkeypatch.setattr(push, "get_push_sender", lambda: pushes)
    push.subscribe(demo_session, user, FCM, {"p256dh": "B" * 87, "auth": "a" * 22}, "test")
    _rule(demo_session, user, "GOAL_REACHED", "PUSH", "DAILY_DIGEST")
    _rule(demo_session, user, "HAWL_APPROACHING", "PUSH", "DAILY_DIGEST")
    outbox = Outbox()
    _goal(demo_session, outbox, user, "Push goal")
    _hawl(demo_session, outbox, user)
    assert pushes.sent == []  # held back
    alerts.send_digests(demo_session, outbox)
    assert outbox.sent == []  # push only
    assert len(pushes.sent) == 1
    assert pushes.sent[0].title == "2 new notices"
    assert pushes.sent[0].url.endswith("/en/personal/alerts")


@pytest.mark.parametrize("locale", ["en", "bn"])
def test_digest_email_caps_the_list_and_reads_in_both_languages_d32(locale: str) -> None:
    items = [
        item
        for n in range(23)
        if (
            item := templates.digest_item(
                locale, "GOAL_REACHED", {"name": f"Goal {n}"}, "/personal/goals", "https://a.com"
            )
        )
        is not None
    ]
    assert all(isinstance(i, Item) for i in items)
    email = templates.digest_email("k@example.com", locale, items, "https://a.com")
    assert "{" not in email.body and email.html and "{" not in email.html
    assert "Goal 19" in email.body and "Goal 20" not in email.body
    more = "And 3 more in the app." if locale == "en" else "অ্যাপে আরও ৩টি আছে।"
    assert more in email.body
    one = templates.digest_email("k@example.com", locale, items[:1], "https://a.com")
    assert one.subject in ("1 new notice from analysisACE", "analysisACE থেকে ১টি নতুন নোটিশ")
    assert templates.digest_push_title(locale, 1) in ("1 new notice", "১টি নতুন নোটিশ")


def test_digest_job_runs_from_the_worker_d32(
    demo_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.jobs import worker

    assert "alert_digest" in worker.JOBS
    user = _user(demo_session)
    _rule(demo_session, user, "GOAL_REACHED", "EMAIL", "DAILY_DIGEST")
    _goal(demo_session, Outbox(), user, "Worker goal")
    outbox = Outbox()
    monkeypatch.setattr(worker, "get_email_sender", lambda: outbox)
    assert worker.JOBS["alert_digest"](demo_session) == {"people": 1}
    assert len(outbox.sent) == 1
