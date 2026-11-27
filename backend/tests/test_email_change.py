"""Changing the sign-in email (D39): a link to the new address, a notice to the old one."""

import re
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.models import AuditLog, EmailChangeToken, User
from app.services.auth import register_user
from app.services.email_templates import mask_email
from tests.test_auth import EMAIL, PASSWORD, Outbox, bearer, login, outbox, register

__all__ = ["outbox"]  # the fixture, imported for pytest

NEW = "rahim.new@example.com"


def _ask(client: TestClient, token: object, new: str = NEW, password: str = PASSWORD):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/v1/auth/email-change",
        headers=bearer(token),
        json={"new_email": new, "password": password},
    )


def _link_token(box: Outbox) -> str:
    match = re.search(r"/bn/confirm-email-change\?token=([\w-]+)", box.sent[-1].body)
    assert match is not None
    return match.group(1)


def test_the_link_goes_to_the_new_address_and_nothing_changes_until_it_is_opened_d39(
    client: TestClient, outbox: Outbox
) -> None:
    token = register(client)["token"]
    outbox.sent.clear()
    response = _ask(client, token, new="  Rahim.New@Example.com ")
    assert response.status_code == 202 and response.json()["new_email"] == NEW
    (mail,) = outbox.sent
    assert mail.to == NEW and "confirm-email-change?token=" in mail.body
    # Still the old address until the link is opened.
    assert client.get("/api/v1/me", headers=bearer(token)).json()["email"] == EMAIL
    assert login(client).status_code == 200
    pending = client.get("/api/v1/auth/email-change", headers=bearer(token)).json()
    assert pending["new_email"] == NEW


def test_opening_the_link_switches_the_email_and_tells_the_old_address_d39(
    client: TestClient, outbox: Outbox, session: Session
) -> None:
    token = register(client)["token"]
    client.post("/api/v1/auth/password-reset/request", json={"email": EMAIL})
    reset = re.search(r"reset-password\?token=([\w-]+)", outbox.sent[-1].body)
    assert reset is not None
    _ask(client, token)
    link = _link_token(outbox)
    outbox.sent.clear()

    confirmed = client.post("/api/v1/auth/email-change/confirm", json={"token": link})
    assert confirmed.status_code == 204
    me = client.get("/api/v1/me", headers=bearer(token)).json()
    assert me["email"] == NEW and me["email_verified_at"] is not None
    assert login(client, email=NEW).status_code == 200
    assert login(client).status_code == 401  # the old address no longer signs in
    # The old address is told, with the new one only partly shown.
    (notice,) = outbox.sent
    assert notice.to == EMAIL and "r•••@example.com" in notice.body
    assert NEW not in notice.body
    # A reset link sent to the old address no longer works.
    stale = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": reset.group(1), "new_password": "a whole new password"},
    )
    assert stale.status_code == 400
    # The link works once.
    again = client.post("/api/v1/auth/email-change/confirm", json={"token": link})
    assert again.json()["detail"] == "EMAIL_CHANGE_TOKEN_INVALID"
    assert client.get("/api/v1/auth/email-change", headers=bearer(token)).json() is None
    actions = set(session.scalars(select(AuditLog.action)))
    assert {"EMAIL_CHANGE_REQUESTED", "EMAIL_CHANGED"} <= actions
    assert NEW not in str(list(session.scalars(select(AuditLog.after))))


def test_the_password_is_asked_and_the_address_must_be_new_and_free_d39(
    client: TestClient, outbox: Outbox, session: Session
) -> None:
    token = register(client)["token"]
    register_user(
        session,
        email="taken@example.com",
        password=PASSWORD,
        full_name="T",
        locale="en",
        accept_terms=True,
    )
    session.commit()
    assert _ask(client, token, password="wrong password").json()["detail"] == "WRONG_PASSWORD"
    assert _ask(client, token, new=EMAIL.upper()).json()["detail"] == "EMAIL_UNCHANGED"
    taken = _ask(client, token, new="taken@example.com")
    assert taken.status_code == 409 and taken.json()["detail"] == "EMAIL_TAKEN"


def test_an_address_taken_before_the_link_is_opened_is_refused_d39(
    client: TestClient, outbox: Outbox, session: Session
) -> None:
    token = register(client)["token"]
    _ask(client, token)
    link = _link_token(outbox)
    register_user(
        session, email=NEW, password=PASSWORD, full_name="N", locale="en", accept_terms=True
    )
    session.commit()
    response = client.post("/api/v1/auth/email-change/confirm", json={"token": link})
    assert response.status_code == 409


def test_a_new_request_or_cancelling_retires_the_earlier_link_d39(
    client: TestClient, outbox: Outbox
) -> None:
    token = register(client)["token"]
    _ask(client, token, new="first@example.com")
    first = _link_token(outbox)
    _ask(client, token)
    second = _link_token(outbox)
    assert (
        client.post("/api/v1/auth/email-change/confirm", json={"token": first}).status_code == 400
    )
    assert client.delete("/api/v1/auth/email-change", headers=bearer(token)).status_code == 204
    assert client.get("/api/v1/auth/email-change", headers=bearer(token)).json() is None
    assert (
        client.post("/api/v1/auth/email-change/confirm", json={"token": second}).status_code == 400
    )


def test_an_expired_link_does_not_work_d39(
    client: TestClient, outbox: Outbox, session: Session
) -> None:
    token = register(client)["token"]
    _ask(client, token)
    link = _link_token(outbox)
    for record in session.scalars(select(EmailChangeToken)):
        record.expires_at = utcnow() - timedelta(minutes=1)
    session.commit()
    response = client.post("/api/v1/auth/email-change/confirm", json={"token": link})
    assert response.json()["detail"] == "EMAIL_CHANGE_TOKEN_INVALID"


def test_a_pending_change_is_exported_and_deleted_with_the_account_d39(
    client: TestClient, outbox: Outbox, session: Session
) -> None:
    token = register(client)["token"]
    _ask(client, token)
    exported = client.get("/api/v1/me/export", headers=bearer(token)).json()
    assert exported["pending_email_change"]["new_email"] == NEW
    user = session.scalar(select(User).where(User.email == EMAIL))
    assert user is not None
    user_id = user.id
    deleted = client.request(
        "DELETE", "/api/v1/me", headers=bearer(token), json={"password": PASSWORD}
    )
    assert deleted.status_code == 204
    session.expire_all()
    assert (
        list(session.scalars(select(EmailChangeToken).where(EmailChangeToken.user_id == user_id)))
        == []
    )


def test_mask_email_keeps_the_first_letter_and_the_domain_d39() -> None:
    assert mask_email("rahim@example.com") == "r•••@example.com"
    assert mask_email("not-an-address") == "not-an-address"
