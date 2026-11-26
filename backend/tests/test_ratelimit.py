"""Rate limits on sign-up, sign-in, password reset and verification emails (D28)."""

import datetime as dt
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.main import app
from app.models import RateLimitHit
from app.services import ratelimit
from app.services.email import Email, get_email_sender

API = "/api/v1"
PASSWORD = "a long enough password"


class Outbox:
    def __init__(self) -> None:
        self.sent: list[Email] = []

    def send(self, email: Email) -> None:
        self.sent.append(email)


@pytest.fixture
def web(client: TestClient) -> TestClient:
    """Requests from a private address, as from the web server: X-Forwarded-For is trusted."""
    return TestClient(app, client=("10.0.0.5", 50000))


@pytest.fixture
def tight(client: TestClient) -> Iterator[Outbox]:
    """Small limits so the tests reach them quickly."""
    settings = Settings(
        rate_limit_signup_per_hour=2,
        rate_limit_login_per_15_minutes=3,
        rate_limit_reset_per_hour=4,
        rate_limit_reset_per_email_per_hour=2,
        rate_limit_verify_per_user_per_hour=1,
    )
    box = Outbox()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_email_sender] = lambda: box
    yield box
    app.dependency_overrides.pop(get_settings, None)
    app.dependency_overrides.pop(get_email_sender, None)


def _register(client: TestClient, email: str, ip: str | None = None) -> int:
    headers = {"X-Forwarded-For": ip} if ip else {}
    body = {
        "email": email,
        "password": PASSWORD,
        "full_name": "R",
        "locale": "en",
        "accept_terms": True,
    }
    return client.post(f"{API}/auth/register", json=body, headers=headers).status_code


def test_client_ip_trusts_forwarded_for_only_from_known_servers_d28() -> None:
    settings = Settings()
    assert ratelimit.client_ip("127.0.0.1", "203.0.113.7, 10.0.0.2", settings) == "203.0.113.7"
    assert ratelimit.client_ip("172.18.0.5", "198.51.100.9", settings) == "198.51.100.9"
    # A visitor on the internet cannot choose their own address.
    assert ratelimit.client_ip("203.0.113.50", "198.51.100.9", settings) == "203.0.113.50"
    assert ratelimit.client_ip("127.0.0.1", "not-an-ip", settings) == "127.0.0.1"
    assert ratelimit.client_ip(None, None, settings) == "unknown"


def test_development_exempts_only_this_machine_d28() -> None:
    assert ratelimit.is_loopback("127.0.0.1") and ratelimit.is_loopback("::1")
    assert not ratelimit.is_loopback("10.0.0.5") and not ratelimit.is_loopback("unknown")


def test_limit_counts_within_the_window_and_frees_after_d28(session: Session) -> None:
    window = dt.timedelta(hours=1)
    assert [ratelimit.allow(session, "t", "k", 2, window) for _ in range(3)] == [True, True, False]
    # Another key, or another bucket, has its own count.
    assert ratelimit.allow(session, "t", "other", 2, window)
    assert ratelimit.allow(session, "u", "k", 2, window)
    # Only hashes are stored.
    keys = list(session.scalars(select(RateLimitHit.key_hash)))
    assert all(len(k) == 64 and k != "k" for k in keys)
    # Old attempts stop counting and are purged.
    for row in session.scalars(select(RateLimitHit)):
        row.created_at = row.created_at - dt.timedelta(hours=2)
    session.flush()
    assert ratelimit.allow(session, "t", "k", 2, window)
    assert ratelimit.purge(session, dt.timedelta(hours=1)) == 4
    assert session.scalar(select(func.count()).select_from(RateLimitHit)) == 1


def test_sign_up_is_limited_per_visitor_even_when_it_fails_d28(
    web: TestClient, tight: Outbox
) -> None:
    client = web
    assert _register(client, "a@example.com", "203.0.113.1") == 201
    # A refused sign-up (address taken) still counts.
    assert _register(client, "a@example.com", "203.0.113.1") == 409
    third = client.post(
        f"{API}/auth/register",
        json={
            "email": "b@example.com",
            "password": PASSWORD,
            "full_name": "R",
            "locale": "en",
            "accept_terms": True,
        },
        headers={"X-Forwarded-For": "203.0.113.1"},
    )
    assert third.status_code == 429 and third.json()["detail"] == "RATE_LIMITED"
    # Another visitor is not affected.
    assert _register(client, "c@example.com", "203.0.113.2") == 201


def test_sign_in_is_limited_per_visitor_d28(web: TestClient, tight: Outbox) -> None:
    client = web
    _register(client, "login@example.com", "203.0.113.9")
    headers = {"X-Forwarded-For": "198.51.100.1"}
    wrong = {"email": "login@example.com", "password": "wrong password!"}
    codes = [
        client.post(f"{API}/auth/login", json=wrong, headers=headers).status_code for _ in range(4)
    ]
    assert codes[:3] == [401, 401, 401] and codes[3] == 429


def test_reset_floods_are_silent_per_address_and_refused_per_visitor_d28(
    web: TestClient, tight: Outbox
) -> None:
    client = web
    _register(client, "victim@example.com", "203.0.113.3")
    tight.sent.clear()
    headers = {"X-Forwarded-For": "198.51.100.2"}
    body = {"email": "victim@example.com"}
    codes = [
        client.post(f"{API}/auth/password-reset/request", json=body, headers=headers).status_code
        for _ in range(4)
    ]
    # Same answer every time, but only two emails reach the inbox.
    assert codes == [202, 202, 202, 202] and len(tight.sent) == 2
    fifth = client.post(f"{API}/auth/password-reset/request", json=body, headers=headers)
    assert fifth.status_code == 429


def test_verification_resend_is_limited_per_person_d28(client: TestClient, tight: Outbox) -> None:
    body = {
        "email": "v@example.com",
        "password": PASSWORD,
        "full_name": "R",
        "locale": "en",
        "accept_terms": True,
    }
    token = client.post(f"{API}/auth/register", json=body).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post(f"{API}/auth/verify-email/request", headers=headers).status_code == 202
    again = client.post(f"{API}/auth/verify-email/request", headers=headers)
    assert again.status_code == 429 and again.json()["detail"] == "RATE_LIMITED"
