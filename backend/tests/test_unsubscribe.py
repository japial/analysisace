"""One-click unsubscribe from alert and report emails (RFC 8058, FR7.3, D34)."""

import uuid
from urllib.parse import parse_qs, unquote, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AlertRule, AuditLog, Notification
from app.services import alerts, unsubscribe
from app.services.auth import register_user
from tests.test_digest import Outbox, _goal, _hawl, _rule, _user

BASE = "https://analysisace.com"


def _token(email_header: str) -> str:
    url = email_header.strip("<>")
    return unquote(parse_qs(urlparse(url).query)["t"][0])


def test_alert_email_carries_one_click_headers_and_a_stop_link_d34(
    demo_session: Session,
) -> None:
    user = _user(demo_session)
    _rule(demo_session, user, "GOAL_REACHED", "EMAIL", "INSTANT")
    outbox = Outbox()
    _goal(demo_session, outbox, user, "First crore")
    (email,) = outbox.sent
    header = email.headers["List-Unsubscribe"]
    assert "/unsubscribe/one-click?t=" in header
    assert email.headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    # People get the confirmation page, not the one-click address.
    assert "/unsubscribe?t=" in email.body and "Stop these emails" in email.body
    assert email.html is not None and "/unsubscribe?t=" in email.html


def test_unsubscribing_stops_email_only_and_keeps_the_notice_d34(demo_session: Session) -> None:
    user = _user(demo_session)
    goal = _rule(demo_session, user, "GOAL_REACHED", "EMAIL", "INSTANT")
    hawl = _rule(demo_session, user, "HAWL_APPROACHING", "BOTH", "INSTANT")
    outbox = Outbox()
    _goal(demo_session, outbox, user, "Before")
    token = _token(outbox.sent[0].headers["List-Unsubscribe"])

    assert unsubscribe.describe(demo_session, token) == {
        "scope": "GOAL_REACHED",
        "emailing": True,
    }
    assert unsubscribe.unsubscribe(demo_session, token)["changed"] == 1
    assert goal.channel == "APP"
    assert hawl.channel == "BOTH"  # other alerts are not touched
    # A second press is harmless.
    assert unsubscribe.unsubscribe(demo_session, token)["changed"] == 0
    assert unsubscribe.describe(demo_session, token)["emailing"] is False

    outbox.sent.clear()
    row = _goal(demo_session, outbox, user, "After")
    assert row is not None and outbox.sent == []  # still in the app, not emailed
    audit = demo_session.scalar(select(AuditLog).where(AuditLog.action == "EMAIL_UNSUBSCRIBED"))
    assert audit is not None and audit.after == {"channel": "APP"}


def test_both_becomes_push_so_browser_notices_carry_on_d34(demo_session: Session) -> None:
    user = _user(demo_session)
    rule = _rule(demo_session, user, "HAWL_APPROACHING", "BOTH", "INSTANT")
    token = unsubscribe.make_token(user.id, "HAWL_APPROACHING")
    unsubscribe.unsubscribe(demo_session, token)
    assert rule.channel == "PUSH"


def test_digest_link_stops_every_once_a_day_email_and_the_waiting_ones_d34(
    demo_session: Session,
) -> None:
    user = _user(demo_session)
    goal = _rule(demo_session, user, "GOAL_REACHED", "EMAIL", "DAILY_DIGEST")
    hawl = _rule(demo_session, user, "HAWL_APPROACHING", "BOTH", "DAILY_DIGEST")
    instant = _rule(demo_session, user, "MATURITY_DUE", "EMAIL", "INSTANT")
    outbox = Outbox()
    _goal(demo_session, outbox, user, "Queued")
    _hawl(demo_session, outbox, user)
    alerts.send_digests(demo_session, outbox)
    (digest,) = outbox.sent
    token = _token(digest.headers["List-Unsubscribe"])
    assert unsubscribe.describe(demo_session, token)["scope"] == "DIGEST"

    _goal(demo_session, outbox, user, "Waiting")  # queued before the press
    unsubscribe.unsubscribe(demo_session, token)
    assert (goal.channel, hawl.channel, instant.channel) == ("APP", "PUSH", "EMAIL")
    waiting = demo_session.scalars(
        select(Notification.digest_channel).where(
            Notification.user_id == user.id, Notification.digested_at.is_(None)
        )
    ).all()
    assert "EMAIL" not in waiting and "BOTH" not in waiting

    outbox.sent.clear()
    alerts.send_digests(demo_session, outbox)
    assert outbox.sent == []


def test_app_only_alerts_are_neither_emailed_nor_queued_d34(demo_session: Session) -> None:
    user = _user(demo_session)
    _rule(demo_session, user, "GOAL_REACHED", "APP", "DAILY_DIGEST")
    outbox = Outbox()
    row = _goal(demo_session, outbox, user, "Quiet")
    assert row is not None and row.digest_channel is None and outbox.sent == []


def test_monthly_report_link_stops_the_report_email_d34(demo_session: Session) -> None:
    user = _user(demo_session)
    rule = _rule(demo_session, user, "MONTHLY_REPORT", "EMAIL", "INSTANT")
    links = unsubscribe.links(BASE, "bn", user.id, "MONTHLY_REPORT")
    assert links is not None and links.page.startswith(f"{BASE}/bn/unsubscribe?t=")
    unsubscribe.unsubscribe(demo_session, _token(links.one_click))
    assert rule.channel == "APP"


def test_api_checks_and_applies_without_sign_in_d34(client: TestClient, session: Session) -> None:
    user = register_user(
        session,
        email="leila@example.com",
        password="correct horse battery",
        full_name="L",
        locale="en",
        accept_terms=True,
    )
    session.add(
        AlertRule(user_id=user.id, type="GOAL_REACHED", channel="EMAIL", frequency="INSTANT")
    )
    session.commit()
    token = unsubscribe.make_token(user.id, "GOAL_REACHED")

    check = client.post("/api/v1/email/unsubscribe/check", json={"token": token})
    assert check.status_code == 200 and check.json() == {
        "scope": "GOAL_REACHED",
        "emailing": True,
    }
    done = client.post("/api/v1/email/unsubscribe", json={"token": token})
    assert done.status_code == 200 and done.json()["changed"] == 1
    session.expire_all()
    rule = session.scalar(select(AlertRule).where(AlertRule.user_id == user.id))
    assert rule is not None and rule.channel == "APP"


def test_forged_or_stale_tokens_are_refused_d34(client: TestClient) -> None:
    sealed = unsubscribe.make_token(uuid.uuid4(), "DIGEST")  # an account that does not exist
    for bad in ("x" * 40, sealed[:-6] + "AAAAAA", sealed):
        response = client.post("/api/v1/email/unsubscribe", json={"token": bad})
        assert response.status_code == 400
        assert response.json()["detail"] == "UNSUBSCRIBE_LINK_INVALID"
    with pytest.raises(ValueError):
        unsubscribe.make_token(uuid.uuid4(), "EVERYTHING")
