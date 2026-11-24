"""Browser push (D26): subscribing, sending on alerts, and dropping dead subscriptions."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.main import app
from app.models import AlertRule, PushSubscription, User
from app.seed.demo_personal import DEMO_EMAIL
from app.services import alerts, push
from app.services.email import Email
from tests.personal_helpers import API, login

FCM = "https://fcm.googleapis.com/fcm/send/abc123-device-token"
BODY = {"endpoint": FCM, "keys": {"p256dh": "B" * 87, "auth": "a" * 22}}


class Recorder:
    def __init__(self, refuse: int | None = None) -> None:
        self.sent: list[tuple[str, push.PushMessage]] = []
        self.refuse = refuse

    def send(self, subscription: PushSubscription, message: push.PushMessage) -> int | None:
        self.sent.append((subscription.endpoint, message))
        return self.refuse


@pytest.fixture
def push_on() -> Any:
    settings = Settings(webpush_public_key="BPUBLIC", webpush_private_key="private")  # type: ignore[arg-type]
    app.dependency_overrides[get_settings] = lambda: settings
    yield settings
    app.dependency_overrides.pop(get_settings, None)


def test_endpoints_must_come_from_a_browser_push_service_d26() -> None:
    assert push.endpoint_allowed(FCM)
    assert push.endpoint_allowed("https://updates.push.services.mozilla.com/wpush/v2/x")
    assert push.endpoint_allowed("https://web.push.apple.com/QK-x")
    assert not push.endpoint_allowed("http://fcm.googleapis.com/fcm/send/x")
    assert not push.endpoint_allowed("https://evil.example.com/fcm.googleapis.com")
    assert not push.endpoint_allowed("https://googleapis.com.evil.example/x")


def test_subscribe_and_unsubscribe_d26(
    demo_client: TestClient, demo_session: Session, push_on: Settings
) -> None:
    owner = login(demo_client)
    config = demo_client.get(f"{API}/push/config", headers=owner).json()
    assert config == {"enabled": True, "public_key": "BPUBLIC", "subscriptions": 0}
    made = demo_client.post(f"{API}/push/subscriptions", headers=owner, json=BODY)
    assert made.status_code == 201 and made.json()["subscriptions"] == 1
    # The same browser subscribing again is not a second subscription.
    demo_client.post(f"{API}/push/subscriptions", headers=owner, json=BODY)
    assert demo_client.get(f"{API}/push/config", headers=owner).json()["subscriptions"] == 1
    bad = {**BODY, "endpoint": "https://attacker.example.com/collect"}
    refused = demo_client.post(f"{API}/push/subscriptions", headers=owner, json=bad)
    assert refused.json()["detail"] == "PUSH_ENDPOINT_INVALID"
    gone = demo_client.post(
        f"{API}/push/subscriptions/remove", headers=owner, json={"endpoint": FCM}
    )
    assert gone.status_code == 204
    assert demo_client.get(f"{API}/push/config", headers=owner).json()["subscriptions"] == 0


def test_push_off_without_keys_d26(demo_client: TestClient) -> None:
    owner = login(demo_client)
    app.dependency_overrides[get_settings] = lambda: Settings(webpush_public_key=None)
    try:
        assert demo_client.get(f"{API}/push/config", headers=owner).json()["enabled"] is False
        refused = demo_client.post(f"{API}/push/subscriptions", headers=owner, json=BODY)
        assert refused.json()["detail"] == "PUSH_NOT_CONFIGURED"
    finally:
        app.dependency_overrides.pop(get_settings, None)
    assert demo_client.get(f"{API}/push/config").status_code == 401


def _alert(demo_session: Session, channel: str, recorder: Recorder, monkeypatch: Any) -> Any:
    monkeypatch.setattr(push, "get_push_sender", lambda: recorder)
    user = demo_session.scalar(select(User).where(User.email == DEMO_EMAIL))
    assert user is not None
    push.subscribe(demo_session, user, FCM, BODY["keys"], "test")
    rule = demo_session.scalar(select(AlertRule).where(AlertRule.user_id == user.id))
    assert rule is not None
    rule.channel = channel

    class Quiet:
        def send(self, email: Email) -> None:
            pass

    return alerts.notify(
        demo_session,
        Quiet(),
        user,
        type=rule.type,
        message_key="GOAL_REACHED",
        data={"name": "First crore"},
        link="/personal/goals",
        dedupe_key=f"test:push:{channel}",
        rules={rule.type: rule},
    )


def test_alert_pushes_when_the_rule_asks_fr7_1_d26(
    demo_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = Recorder()
    assert _alert(demo_session, "PUSH", recorder, monkeypatch) is not None
    assert len(recorder.sent) == 1
    endpoint, message = recorder.sent[0]
    assert endpoint == FCM and "First crore" in message.body
    assert message.url.endswith("/personal/goals")


def test_email_only_rule_does_not_push_d26(
    demo_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = Recorder()
    _alert(demo_session, "EMAIL", recorder, monkeypatch)
    assert recorder.sent == []


def test_a_subscription_the_browser_dropped_is_forgotten_d26(
    demo_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _alert(demo_session, "BOTH", Recorder(refuse=410), monkeypatch)
    assert (
        demo_session.scalar(select(PushSubscription).where(PushSubscription.endpoint == FCM))
        is None
    )
