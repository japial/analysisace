"""Guided set-up of a new household (D22)."""

import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Expense, IncomeEntry
from tests.personal_helpers import API, add_user, login

D = Decimal


def _new_household(client: TestClient, session: Session, email: str) -> tuple[dict[str, str], str]:
    add_user(session, email)
    headers = login(client, email)
    created = client.post(f"{API}/households", headers=headers, json={"name": "New family"})
    assert created.status_code == 201, created.text
    return headers, f"{API}/households/{created.json()['id']}"


def test_setup_status_starts_empty_and_lists_the_form_d22(
    demo_client: TestClient, demo_session: Session
) -> None:
    headers, root = _new_household(demo_client, demo_session, "start@example.com")
    body = demo_client.get(f"{root}/setup/status", headers=headers).json()
    assert [s["key"] for s in body["steps"]] == ["you", "income", "costs", "savings", "plan"]
    assert body["done"] == 0 and body["complete"] is False
    assert "rent" in body["fixed_categories"] and "food_bazar" in body["variable_categories"]
    assert set(body["savings_kinds"]) == {"cash", "certificates", "islamic"}


def test_quick_start_records_the_basics_and_shows_a_savings_rate_d22(
    demo_client: TestClient, demo_session: Session
) -> None:
    """Income 1,00,000 a month; rent 25,000 as a rule and bazar 20,000 as this month's
    estimate: 45,000 of costs, so 55,000 saved, a 55% savings rate."""
    headers, root = _new_household(demo_client, demo_session, "quick@example.com")
    result = demo_client.post(
        f"{root}/setup/quick-start",
        headers=headers,
        json={
            "birth_year": 1990,
            "monthly_income": "100000",
            "costs": {"rent": "25000", "food_bazar": "20000", "utilities": "0"},
            "savings": {"cash": "300000", "islamic": "500000"},
            "locale": "bn",
        },
    )
    assert result.status_code == 201, result.text
    body = result.json()
    assert body["made"] == {"income_rules": 1, "cost_rules": 1, "cost_entries": 1, "holdings": 2}
    assert [s["done"] for s in body["steps"]] == [True, True, True, True, False]

    # The rule starts on the 1st, so this month already has its salary and rent.
    month = date(2026, 11, 1)
    hid = uuid.UUID(root.rsplit("/", 1)[1])
    entries = list(
        demo_session.scalars(select(IncomeEntry.date).where(IncomeEntry.household_id == hid))
    )
    assert month in entries
    rent = list(
        demo_session.scalars(
            select(Expense).where(
                Expense.household_id == hid, Expense.amount == D("25000"), Expense.date == month
            )
        )
    )
    assert len(rent) == 1 and rent[0].recurring_id is not None

    summary = demo_client.get(f"{root}/income/summary", headers=headers).json()["data"]
    assert summary["savings_rate_pct"] == "55.00"
    accounts = demo_client.get(f"{root}/accounts", headers=headers).json()
    assert {a["name"] for a in accounts} == {"নগদ ও ব্যাংক জমা", "ইসলামী আমানত ও সুকুক"}
    worth = demo_client.get(f"{root}/portfolio/summary", headers=headers).json()["data"]
    assert D(worth["assets"]) == D("800000.00")


def test_quick_start_refuses_unknown_categories_and_ages_d22(
    demo_client: TestClient, demo_session: Session
) -> None:
    headers, root = _new_household(demo_client, demo_session, "bad@example.com")
    for body in (
        {"costs": {"yacht": "1000"}},
        {"savings": {"crypto": "1000"}},
        {"birth_year": 2020},
        {"monthly_income": "-5"},
    ):
        response = demo_client.post(f"{root}/setup/quick-start", headers=headers, json=body)
        assert response.status_code == 422, body
    # Nothing was written by the refused requests.
    body = demo_client.get(f"{root}/setup/status", headers=headers).json()
    assert body["done"] == 0


def test_viewer_cannot_run_quick_start_d22(demo_client: TestClient, demo_session: Session) -> None:
    from tests.personal_helpers import base

    add_user(demo_session, "watcher@example.com", role="VIEWER")
    viewer = login(demo_client, "watcher@example.com")
    root = base(demo_session)
    assert demo_client.get(f"{root}/setup/status", headers=viewer).status_code == 200
    response = demo_client.post(
        f"{root}/setup/quick-start", headers=viewer, json={"monthly_income": "1000"}
    )
    assert response.status_code == 403
