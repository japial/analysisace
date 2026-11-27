"""Accounts and sessions: PRD section 10 (Auth), section 13 and FR23."""

import re
from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_token, utcnow, verify_password
from app.main import app
from app.models import AuditLog, PasswordResetToken, User, UserSession
from app.services.email import Email, get_email_sender

PASSWORD = "correct horse battery"
EMAIL = "rahim@example.com"


class Outbox:
    def __init__(self) -> None:
        self.sent: list[Email] = []

    def send(self, email: Email) -> None:
        self.sent.append(email)


@pytest.fixture
def outbox(client: TestClient) -> Iterator[Outbox]:
    box = Outbox()
    app.dependency_overrides[get_email_sender] = lambda: box
    yield box


def register(client: TestClient, email: str = EMAIL, **overrides: object) -> dict[str, object]:
    body = {
        "email": email,
        "password": PASSWORD,
        "full_name": "Rahim Uddin",
        "locale": "bn",
        "accept_terms": True,
        **overrides,
    }
    response = client.post("/api/v1/auth/register", json=body)
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def bearer(token: object) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def login(client: TestClient, password: str = PASSWORD, email: str = EMAIL):  # type: ignore[no-untyped-def]
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


# --- registration ---------------------------------------------------------------------


def test_register_creates_user_and_signs_in(client: TestClient, session: Session) -> None:
    body = register(client, email="  Rahim@Example.COM ")
    user = body["user"]
    assert isinstance(user, dict)
    assert user["email"] == EMAIL  # stored trimmed and lower-case
    assert user["role"] == "USER"
    assert user["permissions"] == []
    assert user["consents"]["TERMS"]["granted"] is True
    assert client.get("/api/v1/me", headers=bearer(body["token"])).json()["email"] == EMAIL

    stored = session.scalar(select(User))
    assert stored is not None
    assert stored.password_hash != PASSWORD
    assert verify_password(PASSWORD, stored.password_hash)


def test_only_the_token_hash_is_stored(client: TestClient, session: Session) -> None:
    token = register(client)["token"]
    stored = session.scalar(select(UserSession))
    assert stored is not None
    assert stored.token_hash == hash_token(str(token))
    assert stored.token_hash != token


def test_register_requires_explicit_consent_fr23_1(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": EMAIL, "password": PASSWORD, "full_name": "R", "accept_terms": False},
    )
    assert (response.status_code, response.json()) == (400, {"detail": "TERMS_REQUIRED"})


def test_register_rejects_duplicate_email_and_weak_input(client: TestClient) -> None:
    register(client)
    duplicate = client.post(
        "/api/v1/auth/register",
        json={"email": EMAIL.upper(), "password": PASSWORD, "full_name": "R", "accept_terms": True},
    )
    assert (duplicate.status_code, duplicate.json()) == (409, {"detail": "EMAIL_TAKEN"})

    for bad in ({"password": "short"}, {"email": "not-an-email"}, {"full_name": ""}):
        body = {
            "email": "x@example.com",
            "password": PASSWORD,
            "full_name": "X",
            "accept_terms": True,
        }
        assert client.post("/api/v1/auth/register", json={**body, **bad}).status_code == 422


# --- sign-in and sign-out -------------------------------------------------------------


def test_login_and_logout(client: TestClient) -> None:
    register(client)
    response = login(client)
    assert response.status_code == 200
    token = response.json()["token"]
    assert client.get("/api/v1/me", headers=bearer(token)).status_code == 200

    assert client.post("/api/v1/auth/logout", headers=bearer(token)).status_code == 204
    after = client.get("/api/v1/me", headers=bearer(token))
    assert (after.status_code, after.json()) == (401, {"detail": "NOT_AUTHENTICATED"})


def test_wrong_password_and_unknown_email_look_the_same(client: TestClient) -> None:
    register(client)
    wrong = login(client, password="wrong password")
    unknown = login(client, email="nobody@example.com")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "INVALID_CREDENTIALS"}


def test_requests_without_a_valid_token_are_refused(client: TestClient) -> None:
    assert client.get("/api/v1/me").status_code == 401
    assert client.get("/api/v1/me", headers=bearer("made-up-token")).status_code == 401


def test_expired_session_is_refused(client: TestClient, session: Session) -> None:
    token = register(client)["token"]
    stored = session.scalar(select(UserSession))
    assert stored is not None
    stored.expires_at = utcnow() - timedelta(minutes=1)
    session.commit()
    assert client.get("/api/v1/me", headers=bearer(token)).status_code == 401


def test_account_locks_after_repeated_failures(client: TestClient, session: Session) -> None:
    """PRD section 13: rate limiting on auth. Five wrong passwords lock sign-in."""
    register(client)
    for _ in range(5):
        assert login(client, password="wrong password").status_code == 401
    locked = login(client)  # even the right password is refused while locked
    assert (locked.status_code, locked.json()) == (429, {"detail": "ACCOUNT_LOCKED"})

    user = session.scalar(select(User))
    assert user is not None
    user.locked_until = utcnow() - timedelta(seconds=1)
    session.commit()
    assert login(client).status_code == 200


def test_successful_login_resets_the_failure_count(client: TestClient, session: Session) -> None:
    register(client)
    for _ in range(4):
        login(client, password="wrong password")
    assert login(client).status_code == 200
    user = session.scalar(select(User))
    assert user is not None and user.failed_login_count == 0


# --- password reset and change --------------------------------------------------------


def test_password_reset_flow(client: TestClient, outbox: Outbox) -> None:
    old_token = register(client)["token"]
    outbox.sent.clear()  # sign-up sent the email confirmation link (D25)
    assert (
        client.post("/api/v1/auth/password-reset/request", json={"email": EMAIL}).status_code == 202
    )
    assert len(outbox.sent) == 1
    message = outbox.sent[0]
    assert message.to == EMAIL
    match = re.search(r"/bn/reset-password\?token=([\w-]+)", message.body)
    assert match is not None
    reset_token = match.group(1)

    new_password = "a brand new password"
    confirm = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": new_password},
    )
    assert confirm.status_code == 204
    assert login(client).status_code == 401
    assert login(client, password=new_password).status_code == 200
    # Sessions opened with the old password are closed.
    assert client.get("/api/v1/me", headers=bearer(old_token)).status_code == 401

    reused = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": "yet another password"},
    )
    assert (reused.status_code, reused.json()) == (400, {"detail": "INVALID_TOKEN"})


def test_reset_request_does_not_reveal_unknown_emails(client: TestClient, outbox: Outbox) -> None:
    response = client.post("/api/v1/auth/password-reset/request", json={"email": "no@example.com"})
    assert response.status_code == 202
    assert outbox.sent == []


def test_expired_reset_token_is_refused(
    client: TestClient, session: Session, outbox: Outbox
) -> None:
    register(client)
    client.post("/api/v1/auth/password-reset/request", json={"email": EMAIL})
    record = session.scalar(select(PasswordResetToken))
    assert record is not None
    record.expires_at = utcnow() - timedelta(minutes=1)
    session.commit()
    token = re.search(r"token=([\w-]+)", outbox.sent[0].body)
    assert token is not None
    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token.group(1), "new_password": "a brand new password"},
    )
    assert response.json() == {"detail": "INVALID_TOKEN"}


def test_change_password_keeps_this_session_and_ends_the_others(client: TestClient) -> None:
    first = register(client)["token"]
    second = login(client).json()["token"]

    wrong = client.post(
        "/api/v1/me/password",
        headers=bearer(first),
        json={"current_password": "not it", "new_password": "a brand new password"},
    )
    assert wrong.json() == {"detail": "WRONG_PASSWORD"}

    changed = client.post(
        "/api/v1/me/password",
        headers=bearer(first),
        json={"current_password": PASSWORD, "new_password": "a brand new password"},
    )
    assert changed.status_code == 204
    assert client.get("/api/v1/me", headers=bearer(first)).status_code == 200
    assert client.get("/api/v1/me", headers=bearer(second)).status_code == 401


# --- profile, consents, export, deletion ----------------------------------------------


def test_update_profile(client: TestClient) -> None:
    headers = bearer(register(client)["token"])
    response = client.patch(
        "/api/v1/me", headers=headers, json={"full_name": " Rahim U. ", "locale": "en"}
    )
    assert (response.json()["full_name"], response.json()["locale"]) == ("Rahim U.", "en")
    assert client.patch("/api/v1/me", headers=headers, json={"locale": "fr"}).status_code == 422


def test_consents_can_be_granted_and_withdrawn_fr23_1(client: TestClient, session: Session) -> None:
    headers = bearer(register(client)["token"])
    granted = client.patch(
        "/api/v1/me/consents",
        headers=headers,
        json={"consents": {"RELIGIOUS_PREFERENCES": True, "MARKETING": False}},
    ).json()
    assert granted["consents"]["RELIGIOUS_PREFERENCES"]["granted"] is True
    assert "MARKETING" not in granted["consents"]  # unchanged from "not granted"

    withdrawn = client.patch(
        "/api/v1/me/consents", headers=headers, json={"consents": {"RELIGIOUS_PREFERENCES": False}}
    ).json()
    assert withdrawn["consents"]["RELIGIOUS_PREFERENCES"]["granted"] is False

    changes = session.scalars(select(AuditLog).where(AuditLog.action == "CONSENT_CHANGED")).all()
    assert len(changes) == 2


def test_terms_consent_cannot_be_withdrawn_in_place(client: TestClient) -> None:
    headers = bearer(register(client)["token"])
    response = client.patch(
        "/api/v1/me/consents", headers=headers, json={"consents": {"TERMS": False}}
    )
    assert response.json() == {"detail": "CONSENT_NOT_CHANGEABLE"}


def test_export_returns_the_users_data_without_secrets_fr23_4(client: TestClient) -> None:
    token = register(client)["token"]
    body = client.get("/api/v1/me/export", headers=bearer(token))
    assert body.status_code == 200
    data = body.json()
    assert data["account"]["email"] == EMAIL
    assert len(data["sessions"]) == 1
    assert "password" not in body.text
    assert str(token) not in body.text


def test_delete_account_removes_everything_fr23_4(client: TestClient, session: Session) -> None:
    token = register(client)["token"]
    wrong = client.request("DELETE", "/api/v1/me", headers=bearer(token), json={"password": "nope"})
    assert wrong.json() == {"detail": "WRONG_PASSWORD"}

    deleted = client.request(
        "DELETE", "/api/v1/me", headers=bearer(token), json={"password": PASSWORD}
    )
    assert deleted.status_code == 204
    assert session.scalars(select(User)).all() == []
    assert session.scalars(select(UserSession)).all() == []
    assert client.get("/api/v1/me", headers=bearer(token)).status_code == 401
    assert login(client).status_code == 401

    # The audit trail keeps the id only.
    entry = session.scalar(select(AuditLog).where(AuditLog.action == "USER_DELETED"))
    assert entry is not None
    assert EMAIL not in f"{entry.actor}{entry.before}{entry.after}"


def test_password_reset_answers_the_same_when_email_fails_d24(client: TestClient) -> None:
    """A provider outage must not reveal which emails have accounts, or break the request."""
    from app.services.email import EmailSendError

    class Broken:
        def send(self, email: Email) -> None:
            raise EmailSendError("SMTPServerDisconnected")

    app.dependency_overrides[get_email_sender] = lambda: Broken()
    register(client)
    known = client.post("/api/v1/auth/password-reset/request", json={"email": EMAIL})
    unknown = client.post("/api/v1/auth/password-reset/request", json={"email": "no@example.com"})
    assert known.status_code == unknown.status_code == 202


def test_sign_up_sends_a_confirmation_link_that_confirms_once_d25(
    client: TestClient, outbox: Outbox
) -> None:
    body = register(client)
    assert body["user"]["email_verified_at"] is None
    assert len(outbox.sent) == 1 and outbox.sent[0].to == EMAIL
    match = re.search(r"/bn/verify-email\?token=([\w-]+)", outbox.sent[0].body)
    assert match is not None
    token = match.group(1)

    assert (
        client.post("/api/v1/auth/verify-email/confirm", json={"token": token}).status_code == 204
    )
    me = client.get("/api/v1/me", headers=bearer(body["token"])).json()
    assert me["email_verified_at"] is not None
    again = client.post("/api/v1/auth/verify-email/confirm", json={"token": token})
    assert again.json()["detail"] == "VERIFY_TOKEN_INVALID"

    # Already confirmed: asking again sends nothing.
    outbox.sent.clear()
    resend = client.post("/api/v1/auth/verify-email/request", headers=bearer(body["token"]))
    assert resend.status_code == 202 and outbox.sent == []


def test_a_new_confirmation_link_replaces_the_old_one_d25(
    client: TestClient, outbox: Outbox
) -> None:
    body = register(client)
    first = re.search(r"token=([\w-]+)", outbox.sent[0].body)
    assert first is not None
    assert (
        client.post("/api/v1/auth/verify-email/request", headers=bearer(body["token"])).status_code
        == 202
    )
    second = re.search(r"token=([\w-]+)", outbox.sent[-1].body)
    assert second is not None and second.group(1) != first.group(1)
    old = client.post("/api/v1/auth/verify-email/confirm", json={"token": first.group(1)})
    assert old.json()["detail"] == "VERIFY_TOKEN_INVALID"
    new = client.post("/api/v1/auth/verify-email/confirm", json={"token": second.group(1)})
    assert new.status_code == 204
    assert client.post("/api/v1/auth/verify-email/request").status_code == 401
