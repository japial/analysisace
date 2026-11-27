"""Export and deletion cover every piece of personal data (FR23.4, D33).

The guard tests read the database schema, so a table added later that holds someone's data
fails here until it is exported (or listed below with the reason it is left out).
"""

from fastapi.testclient import TestClient
from sqlalchemy import Table, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401  (registers every table)
from app.models import (
    AlertRule,
    AuditLog,
    Base,
    Firm,
    FirmSeat,
    Notification,
    PushSubscription,
    Subscription,
    User,
)
from app.services import household_data
from app.services.auth import register_user

PASSWORD = "correct horse battery"

# Tables a person owns (deleted with the account), and where their export shows them.
USER_EXPORT = {
    "alert_rule": "alert_rules",
    "notification": "notifications",
    "firm_seat": "firm_seats",
    "subscription": "subscriptions",
    "push_subscription": "push_subscriptions",
    "watchlist": "watchlist",
    "user_session": "sessions",
    "household_member": "households",
}
# Left out of the export on purpose.
USER_EXCLUDED = {
    "password_reset_token": "only a hash of a one-time link is stored",
    "email_verification_token": "only a hash of a one-time link is stored",
}
# Reached from a household by something other than a foreign key to the household.
HOUSEHOLD_SPECIAL = {
    "owner_share": "exported by asset id in household_data.export_household",
    "valuation": "exported by asset id in household_data.export_household",
}


def _tables() -> dict[str, Table]:
    return dict(Base.metadata.tables)


def test_every_table_a_person_owns_is_exported_fr23_4() -> None:
    owned = {
        table.name
        for table in _tables().values()
        for column in table.columns
        for fk in column.foreign_keys
        if fk.column.table.name == "app_user" and fk.ondelete == "CASCADE"
    }
    missing = owned - set(USER_EXPORT) - set(USER_EXCLUDED)
    assert not missing, f"export (auth.export_user_data) or exclude: {sorted(missing)}"


def test_every_table_under_a_household_is_exported_fr23_4() -> None:
    tables = _tables()
    reached = {"household"}
    changed = True
    while changed:
        changed = False
        for table in tables.values():
            if table.name in reached:
                continue
            parents = {fk.column.table.name for c in table.columns for fk in c.foreign_keys}
            if parents & reached:
                reached.add(table.name)
                changed = True
    reached.discard("household")
    covered = {m.__tablename__ for m in household_data._HOUSEHOLD_TABLES}
    covered |= {m.__tablename__ for m, _, _ in household_data._CHILD_TABLES}
    covered |= set(HOUSEHOLD_SPECIAL)
    missing = reached - covered
    assert not missing, f"add to household_data._HOUSEHOLD_TABLES/_CHILD_TABLES: {sorted(missing)}"


def _register(client: TestClient, email: str) -> str:
    body = {
        "email": email,
        "password": PASSWORD,
        "full_name": "R",
        "locale": "en",
        "accept_terms": True,
    }
    response = client.post("/api/v1/auth/register", json=body)
    assert response.status_code == 201, response.text
    return str(response.json()["token"])


def test_export_holds_notices_seats_subscriptions_and_own_activity_fr23_4(
    client: TestClient, session: Session
) -> None:
    token = _register(client, "rahim@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    client.patch("/api/v1/me/consents", headers=headers, json={"consents": {"MARKETING": True}})
    user = session.scalar(select(User).where(User.email == "rahim@example.com"))
    assert user is not None
    other = register_user(
        session,
        email="other@example.com",
        password=PASSWORD,
        full_name="O",
        locale="en",
        accept_terms=True,
    )
    firm = Firm(name="Test Securities", seat_limit=5)
    session.add(firm)
    session.flush()
    session.add_all(
        [
            FirmSeat(firm_id=firm.id, user_id=user.id, role="ADMIN"),
            Notification(
                user_id=user.id, type="GOAL_REACHED", message_key="GOAL_REACHED", data={"name": "G"}
            ),
            Subscription(user_id=user.id, plan="PRO", status="ACTIVE", provider="MANUAL"),
            # Something done to another account by this person: listed, without its details.
            AuditLog(
                actor=str(user.id),
                action="TEST_ACTION",
                entity="app_user",
                entity_id=str(other.id),
                after={"secret": "x"},
                at=user.created_at,
            ),
        ]
    )
    session.commit()

    data = client.get("/api/v1/me/export", headers=headers).json()
    assert data["account"]["email_verified_at"] is None
    assert data["notifications"][0]["message_key"] == "GOAL_REACHED"
    assert data["firm_seats"] == [
        {"firm": "Test Securities", "role": "ADMIN", "since": data["firm_seats"][0]["since"]}
    ]
    assert data["subscriptions"][0]["plan"] == "PRO"
    actions = {a["action"]: a for a in data["activity"]}
    assert actions["CONSENT_CHANGED"]["after"] == {"MARKETING": True}
    assert "after" not in actions["TEST_ACTION"] and "secret" not in str(actions["TEST_ACTION"])
    assert "USER_REGISTERED" in actions


def test_deletion_leaves_no_personal_rows_and_hands_the_firm_over_fr23_4(
    client: TestClient, session: Session
) -> None:
    token = _register(client, "leaver@example.com")
    leaver = session.scalar(select(User).where(User.email == "leaver@example.com"))
    colleague = register_user(
        session,
        email="colleague@example.com",
        password=PASSWORD,
        full_name="C",
        locale="en",
        accept_terms=True,
    )
    assert leaver is not None
    firm = Firm(name="Handover Ltd", seat_limit=5)
    session.add(firm)
    session.flush()
    session.add_all(
        [
            FirmSeat(firm_id=firm.id, user_id=leaver.id, role="ADMIN"),
            FirmSeat(firm_id=firm.id, user_id=colleague.id, role="MEMBER"),
            Notification(
                user_id=leaver.id, type="GOAL_REACHED", message_key="GOAL_REACHED", data={}
            ),
            Subscription(user_id=leaver.id, plan="PRO", status="ACTIVE", provider="MANUAL"),
            AlertRule(
                user_id=leaver.id,
                type="GOAL_REACHED",
                channel="EMAIL",
                frequency="INSTANT",
                params={},
            ),
            PushSubscription(
                user_id=leaver.id,
                endpoint="https://fcm.googleapis.com/x",
                keys={"p256dh": "k", "auth": "a"},
            ),
        ]
    )
    session.commit()
    leaver_id = leaver.id

    response = client.request(
        "DELETE",
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"password": PASSWORD},
    )
    assert response.status_code == 204
    session.expire_all()
    for model in (Notification, Subscription, AlertRule, PushSubscription, FirmSeat):
        rows = list(session.scalars(select(model).where(model.user_id == leaver_id)))
        assert rows == [], model.__tablename__
    # The firm still has someone to run it.
    seat = session.scalar(select(FirmSeat).where(FirmSeat.user_id == colleague.id))
    assert seat is not None and seat.role == "ADMIN"
    handover = session.scalar(select(AuditLog).where(AuditLog.action == "FIRM_ADMIN_HANDED_OVER"))
    assert handover is not None and handover.after == {"user_id": str(colleague.id)}
