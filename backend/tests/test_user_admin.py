"""Roles, permissions and user management (PRD sections 10 and 13)."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import ROLE_PERMISSIONS, Permission, Role, has_permission
from app.models import AuditLog, User
from app.services.auth import register_user

PASSWORD = "correct horse battery"


def make_user(session: Session, email: str, role: Role = Role.USER) -> User:
    user = register_user(
        session,
        email=email,
        password=PASSWORD,
        full_name=email.split("@")[0].title(),
        locale="en",
        accept_terms=True,
        role=role,
    )
    session.commit()
    return user


def sign_in(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


# --- permission model -----------------------------------------------------------------


def test_role_permissions() -> None:
    assert ROLE_PERMISSIONS[Role.USER] == frozenset()
    assert ROLE_PERMISSIONS[Role.ANALYST] == {Permission.DATA_REVIEW, Permission.CONTENT_PUBLISH}
    assert ROLE_PERMISSIONS[Role.ADMIN] == frozenset(Permission)
    assert has_permission("ADMIN", Permission.USERS_MANAGE)
    assert not has_permission(Role.ANALYST, Permission.USERS_MANAGE)


def test_me_lists_the_permissions_of_the_role(client: TestClient, session: Session) -> None:
    make_user(session, "analyst@example.com", Role.ANALYST)
    me = client.get("/api/v1/me", headers=sign_in(client, "analyst@example.com")).json()
    assert me["role"] == "ANALYST"
    assert me["permissions"] == ["CONTENT_PUBLISH", "DATA_REVIEW"]


# --- access control -------------------------------------------------------------------


def test_admin_routes_need_the_users_manage_permission(
    client: TestClient, session: Session
) -> None:
    make_user(session, "user@example.com")
    make_user(session, "analyst@example.com", Role.ANALYST)

    assert client.get("/api/v1/admin/users").status_code == 401
    for email in ("user@example.com", "analyst@example.com"):
        for path in ("/api/v1/admin/users", "/api/v1/admin/roles"):
            response = client.get(path, headers=sign_in(client, email))
            assert (response.status_code, response.json()) == (403, {"detail": "FORBIDDEN"})


# --- listing --------------------------------------------------------------------------


def test_admin_lists_and_filters_users(client: TestClient, session: Session) -> None:
    make_user(session, "admin@example.com", Role.ADMIN)
    make_user(session, "karim@example.com")
    make_user(session, "analyst@example.com", Role.ANALYST)
    headers = sign_in(client, "admin@example.com")

    everyone = client.get("/api/v1/admin/users", headers=headers).json()
    assert everyone["total"] == 3
    assert "password_hash" not in everyone["items"][0]

    def emails(query: str) -> list[str]:
        items = client.get(f"/api/v1/admin/users?{query}", headers=headers).json()["items"]
        return sorted(u["email"] for u in items)

    assert emails("q=karim") == ["karim@example.com"]
    assert emails("role=ANALYST") == ["analyst@example.com"]
    assert len(emails("limit=2")) == 2


def test_roles_endpoint_describes_each_role(client: TestClient, session: Session) -> None:
    make_user(session, "admin@example.com", Role.ADMIN)
    body = client.get("/api/v1/admin/roles", headers=sign_in(client, "admin@example.com")).json()
    by_role = {r["role"]: r["permissions"] for r in body["roles"]}
    assert by_role["USER"] == []
    assert "USERS_MANAGE" in by_role["ADMIN"]
    assert "USERS_MANAGE" not in by_role["ANALYST"]
    assert set(body["permissions"]) == {p.value for p in Permission}


# --- changing users -------------------------------------------------------------------


def test_admin_changes_a_role_and_it_is_audited(client: TestClient, session: Session) -> None:
    admin = make_user(session, "admin@example.com", Role.ADMIN)
    target = make_user(session, "karim@example.com")
    headers = sign_in(client, "admin@example.com")

    response = client.patch(
        f"/api/v1/admin/users/{target.id}", headers=headers, json={"role": "ANALYST"}
    )
    assert response.status_code == 200
    assert response.json()["role"] == "ANALYST"

    entry = session.scalar(select(AuditLog).where(AuditLog.action == "USER_UPDATED"))
    assert entry is not None
    assert entry.actor == str(admin.id)
    assert (entry.before, entry.after) == (
        {"role": "USER", "is_active": True},
        {"role": "ANALYST", "is_active": True},
    )


def test_deactivating_a_user_signs_them_out_and_blocks_sign_in(
    client: TestClient, session: Session
) -> None:
    make_user(session, "admin@example.com", Role.ADMIN)
    target = make_user(session, "karim@example.com")
    target_headers = sign_in(client, "karim@example.com")
    admin_headers = sign_in(client, "admin@example.com")

    response = client.patch(
        f"/api/v1/admin/users/{target.id}", headers=admin_headers, json={"is_active": False}
    )
    assert response.json()["is_active"] is False
    assert client.get("/api/v1/me", headers=target_headers).status_code == 401
    blocked = client.post(
        "/api/v1/auth/login", json={"email": "karim@example.com", "password": PASSWORD}
    )
    assert (blocked.status_code, blocked.json()) == (403, {"detail": "ACCOUNT_DISABLED"})

    client.patch(
        f"/api/v1/admin/users/{target.id}", headers=admin_headers, json={"is_active": True}
    )
    sign_in(client, "karim@example.com")


def test_admin_cannot_change_their_own_role_or_state(client: TestClient, session: Session) -> None:
    admin = make_user(session, "admin@example.com", Role.ADMIN)
    make_user(session, "second@example.com", Role.ADMIN)
    headers = sign_in(client, "admin@example.com")
    for change in ({"role": "USER"}, {"is_active": False}):
        response = client.patch(f"/api/v1/admin/users/{admin.id}", headers=headers, json=change)
        assert (response.status_code, response.json()) == (409, {"detail": "CANNOT_CHANGE_SELF"})


def test_the_last_active_admin_cannot_be_removed(client: TestClient, session: Session) -> None:
    first = make_user(session, "admin@example.com", Role.ADMIN)
    second = make_user(session, "second@example.com", Role.ADMIN)
    first_headers = sign_in(client, "admin@example.com")
    second_headers = sign_in(client, "second@example.com")

    # With two admins, one can demote the other.
    demoted = client.patch(
        f"/api/v1/admin/users/{second.id}", headers=first_headers, json={"role": "USER"}
    )
    assert demoted.status_code == 200
    # The demoted admin has lost access at once.
    assert client.get("/api/v1/admin/users", headers=second_headers).status_code == 403

    # The one admin left cannot delete their own account.
    response = client.request(
        "DELETE", "/api/v1/me", headers=first_headers, json={"password": PASSWORD}
    )
    assert (response.status_code, response.json()) == (409, {"detail": "LAST_ADMIN"})
    assert session.get(User, first.id) is not None


def test_unknown_user_is_404(client: TestClient, session: Session) -> None:
    make_user(session, "admin@example.com", Role.ADMIN)
    response = client.patch(
        "/api/v1/admin/users/00000000-0000-0000-0000-000000000000",
        headers=sign_in(client, "admin@example.com"),
        json={"role": "ANALYST"},
    )
    assert (response.status_code, response.json()) == (404, {"detail": "USER_NOT_FOUND"})
