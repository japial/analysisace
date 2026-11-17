"""Helpers shared by the personal finance API tests."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Household, HouseholdMember
from app.seed.demo_personal import DEMO_EMAIL
from app.services.auth import register_user
from tests.conftest import DEMO_PASSWORD

API = "/api/v1"


def login(client: TestClient, email: str = DEMO_EMAIL) -> dict[str, str]:
    response = client.post(f"{API}/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def household_id(session: Session) -> uuid.UUID:
    hid = session.scalar(select(Household.id).where(Household.name == "Rahman family"))
    assert hid is not None
    return hid


def base(session: Session) -> str:
    return f"{API}/households/{household_id(session)}"


def member(session: Session, name: str) -> HouseholdMember:
    row = session.scalar(
        select(HouseholdMember).where(HouseholdMember.display_name.like(f"{name}%"))
    )
    assert row is not None
    return row


def add_user(session: Session, email: str, *, role: str | None = None) -> None:
    """Register another login and, with `role`, put it in the demo household."""
    user = register_user(
        session,
        email=email,
        password=DEMO_PASSWORD,
        full_name=email.split("@")[0].title(),
        locale="en",
        accept_terms=True,
    )
    if role:
        session.add(
            HouseholdMember(
                household_id=household_id(session),
                user_id=user.id,
                display_name=user.full_name,
                role=role,
            )
        )
    session.commit()
