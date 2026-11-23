"""Income records and savings (F27)."""

import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import FirePlan, IncomeEntry, ScenarioResult, User
from app.seed.demo_personal import DEMO_EMAIL
from app.services import alerts, income
from tests.personal_helpers import add_user, base, household_id, login, member

D = Decimal


def test_income_summary_savings_by_hand_fr27_3(demo_session: Session) -> None:
    """Demo salaries are 120,000 + 45,000 a month from Sep 2025 and a 150,000 bonus in June.

    The 12 months to Nov 2026 hold 12 salary months and one bonus:
    income = 12 x 165,000 + 150,000 = 2,130,000. Savings are income less the costs of those
    months, and the rate is savings / income.
    """
    result = income.summary(demo_session, household_id(demo_session), as_of=date(2026, 11, 15))
    assert result.income_12m == D("2130000.00")
    assert result.savings_12m == result.income_12m - result.costs_12m
    assert result.savings_rate_pct == (result.savings_12m / result.income_12m * 100).quantize(
        D("0.01")
    )
    assert result.average_monthly_income == (result.income_12m / result.months_counted).quantize(
        D("0.01")
    )
    assert result.by_kind[0]["kind"] == "SALARY"
    assert result.by_kind[0]["total"] == D("2130000.00")
    # Every month's savings is that month's income less its costs.
    assert all(m["savings"] == m["income"] - m["costs"] for m in result.months)


def test_income_summary_without_income_has_no_rate_fr27_3(demo_session: Session) -> None:
    result = income.summary(demo_session, uuid.uuid4(), as_of=date(2026, 11, 15))
    assert result.income_12m == 0 and result.savings_rate_pct is None
    assert result.average_monthly_income is None and result.months == []


def test_income_entry_crud_and_validation_fr27_1(
    demo_client: TestClient, demo_session: Session
) -> None:
    owner, root = login(demo_client), base(demo_session)
    body = {"date": "2026-11-10", "amount": "5000", "kind": "RENT", "note": "Garage"}
    created = demo_client.post(f"{root}/income", headers=owner, json=body)
    assert created.status_code == 201
    entry = created.json()
    assert (entry["amount"], entry["kind"]) == ("5000.00", "RENT")

    patched = demo_client.patch(
        f"{root}/income/{entry['id']}", headers=owner, json={"amount": "6000"}
    )
    assert patched.json()["amount"] == "6000.00"
    listed = demo_client.get(f"{root}/income?kind=RENT", headers=owner).json()
    assert listed["total"] == 1

    for bad in (
        {**body, "amount": "0"},
        {**body, "amount": "-1"},
        {**body, "amount": "1.999"},
        {**body, "kind": "LOTTERY"},
    ):
        assert demo_client.post(f"{root}/income", headers=owner, json=bad).status_code == 422
    unknown_member = {**body, "member_id": "00000000-0000-0000-0000-000000000000"}
    assert demo_client.post(f"{root}/income", headers=owner, json=unknown_member).status_code == 404

    assert demo_client.delete(f"{root}/income/{entry['id']}", headers=owner).status_code == 204
    assert demo_client.get(f"{root}/income?kind=RENT", headers=owner).json()["total"] == 0


def test_viewer_cannot_record_income_fr27_1(demo_client: TestClient, demo_session: Session) -> None:
    add_user(demo_session, "viewer@example.com", role="VIEWER")
    viewer, root = login(demo_client, "viewer@example.com"), base(demo_session)
    assert demo_client.get(f"{root}/income", headers=viewer).status_code == 200
    body = {"date": "2026-11-10", "amount": "5000", "kind": "RENT"}
    assert demo_client.post(f"{root}/income", headers=viewer, json=body).status_code == 403


def test_recurring_income_generates_once_per_date_fr27_2(
    demo_client: TestClient, demo_session: Session
) -> None:
    owner, root = login(demo_client), base(demo_session)
    rule = demo_client.post(
        f"{root}/income-rules",
        headers=owner,
        json={
            "kind": "RENT",
            "amount": "8000",
            "frequency": "MONTHLY",
            "start_date": "2026-08-31",
        },
    )
    assert rule.status_code == 201
    rule_id = uuid.UUID(rule.json()["id"])

    def generated() -> list[date]:
        return sorted(
            demo_session.scalars(
                select(IncomeEntry.date).where(IncomeEntry.recurring_id == rule_id)
            )
        )

    # Due on 31 Aug, 30 Sep and 31 Oct; 30 Nov is still ahead of "today" (15 Nov).
    assert generated() == [date(2026, 8, 31), date(2026, 9, 30), date(2026, 10, 31)]
    # The daily job running again adds nothing for this rule.
    assert (
        income.generate_recurring(
            demo_session, date(2026, 11, 15), household_id=household_id(demo_session)
        )
        == 0
    )
    # A later run adds the November entries: this rule and the two demo salaries.
    assert income.generate_recurring(demo_session, date(2026, 12, 1)) == 3
    assert generated()[-1] == date(2026, 11, 30)

    stopped = demo_client.patch(
        f"{root}/income-rules/{rule_id}", headers=owner, json={"is_active": False}
    )
    assert stopped.json()["is_active"] is False
    income.generate_recurring(demo_session, date(2027, 6, 1))
    assert generated()[-1] == date(2026, 11, 30)

    bad = {"kind": "RENT", "amount": "1", "frequency": "DAILY", "start_date": "2026-01-01"}
    assert demo_client.post(f"{root}/income-rules", headers=owner, json=bad).status_code == 422
    backwards = {
        "kind": "RENT",
        "amount": "1",
        "frequency": "MONTHLY",
        "start_date": "2026-05-01",
        "end_date": "2026-04-01",
    }
    assert (
        demo_client.post(f"{root}/income-rules", headers=owner, json=backwards).status_code == 422
    )


def test_income_summary_endpoint_lists_kinds_and_sources_fr27_3(
    demo_client: TestClient, demo_session: Session
) -> None:
    owner, root = login(demo_client), base(demo_session)
    body = demo_client.get(f"{root}/income/summary", headers=owner).json()
    assert body["as_of"] and "sources" in body
    data = body["data"]
    assert "SALARY" in data["kinds"]
    assert D(data["savings_12m"]) == D(data["income_12m"]) - D(data["costs_12m"])


def test_ace_summary_earnings_has_income_and_savings_d19(
    demo_client: TestClient, demo_session: Session
) -> None:
    owner, root = login(demo_client), base(demo_session)
    earnings = demo_client.get(f"{root}/ace/summary", headers=owner).json()["data"]["earnings"]
    summary = demo_client.get(f"{root}/income/summary", headers=owner).json()["data"]
    assert earnings["income_trailing_12_months"] == summary["income_12m"]
    assert earnings["savings_rate_pct"] == summary["savings_rate_pct"]
    assert earnings["average_monthly_savings"] == summary["average_monthly_savings"]


def test_fire_defaults_use_average_monthly_savings_fr17_1(
    demo_client: TestClient, demo_session: Session
) -> None:
    owner, root = login(demo_client), base(demo_session)
    defaults = demo_client.get(f"{root}/fire/defaults", headers=owner).json()["data"]
    summary = demo_client.get(f"{root}/income/summary", headers=owner).json()["data"]
    expected = max(D(summary["average_monthly_savings"]), D(0))
    assert D(defaults["monthly_savings"]) == expected


def test_tax_statement_takes_salary_from_income_records_fr27_5(
    demo_client: TestClient, demo_session: Session
) -> None:
    """Karim's demo salary is 120,000 on the 1st of each month. Tax year 2026-27 runs from
    1 July 2026; with "today" at 15 November that is July to November: 5 x 120,000."""
    owner, root = login(demo_client), base(demo_session)
    karim = member(demo_session, "Karim")
    rent = {"date": "2026-10-05", "amount": "7000", "kind": "RENT", "member_id": str(karim.id)}
    assert demo_client.post(f"{root}/income", headers=owner, json=rent).status_code == 201
    bonus = {"date": "2026-10-06", "amount": "2500", "kind": "OTHER", "member_id": str(karim.id)}
    assert demo_client.post(f"{root}/income", headers=owner, json=bonus).status_code == 201
    income.create_entry(
        demo_session,
        household_id(demo_session),
        day=date(2026, 10, 7),
        amount=D("1000"),
        kind="OTHER",
        member_id=None,
    )
    demo_session.commit()

    recorded = demo_client.get(
        f"{root}/tax/recorded-income?member_id={karim.id}&tax_year=2026-27", headers=owner
    ).json()
    assert (recorded["salary"], recorded["other"]) == ("600000.00", "2500.00")
    # Rent is worked out from assets, so the record is listed, not counted twice.
    assert recorded["not_counted"] == [{"kind": "RENT", "amount": "7000.00"}]
    assert recorded["unassigned"] == "1000.00"

    snapshot = demo_client.post(
        f"{root}/tax/snapshots",
        headers=owner,
        json={"member_id": str(karim.id), "tax_year": "2026-27"},
    ).json()["data"]["items"]
    assert snapshot["income"]["salary"] == "600000.00"
    assert snapshot["income"]["other"] == "2500.00"
    assert snapshot["income_basis"]["salary"] == "RECORDS"

    typed = demo_client.post(
        f"{root}/tax/snapshots",
        headers=owner,
        json={"member_id": str(karim.id), "tax_year": "2026-27", "salary_income": "650000"},
    ).json()["data"]["items"]
    assert typed["income"]["salary"] == "650000.00"
    assert typed["income_basis"]["salary"] == "ENTERED"
    assert typed["income"]["other"] == "2500.00"


def test_monthly_report_shows_income_and_savings_fr20_2(demo_session: Session) -> None:
    """October 2026: both demo salaries, 120,000 + 45,000 = 165,000; savings are income
    less October's costs."""
    user = demo_session.scalar(select(User).where(User.email == DEMO_EMAIL))
    assert user is not None
    karim = member(demo_session, "Karim")
    figures = alerts.monthly_figures(
        demo_session, user, household_id(demo_session), karim, date(2026, 11, 15)
    )
    assert figures["month"] == "2026-10"
    assert figures["income"] == D("165000.00")
    assert figures["savings"] == figures["income"] - figures["spending"]


def test_monthly_savings_goal_uses_average_savings_fr19_1_fr27_4(
    demo_client: TestClient, demo_session: Session
) -> None:
    owner, root = login(demo_client), base(demo_session)
    created = demo_client.post(
        f"{root}/goals",
        headers=owner,
        json={"type": "MONTHLY_SAVINGS", "name": "Save every month", "target_amount": "1"},
    )
    assert created.status_code == 201, created.text
    summary = demo_client.get(f"{root}/income/summary", headers=owner).json()["data"]
    goals = demo_client.get(f"{root}/goals", headers=owner).json()["data"]
    goal = next(g for g in goals if g["goal"]["type"] == "MONTHLY_SAVINGS")
    assert goal["current"] == summary["average_monthly_savings"]
    # The demo household saves more than 1 taka a month, so the goal is reached.
    assert goal["reached"] is True and goal["progress_pct"] == "100.00"


def test_fire_progress_estimates_from_costs_without_a_plan_fr17_2(
    demo_client: TestClient, demo_session: Session
) -> None:
    """No plan yet: the FIRE number is a year of costs x 100 / 4 (the configured rate)."""
    owner, root = login(demo_client), base(demo_session)
    hid = household_id(demo_session)
    plan_ids = select(FirePlan.id).where(FirePlan.household_id == hid)
    demo_session.execute(delete(ScenarioResult).where(ScenarioResult.fire_plan_id.in_(plan_ids)))
    demo_session.execute(delete(FirePlan).where(FirePlan.household_id == hid))
    demo_session.commit()
    data = demo_client.get(f"{root}/fire/progress", headers=owner).json()["data"]
    assert data["basis"] == "ESTIMATE" and data["plan"] is None
    costs = D(data["yearly_costs"])
    assert D(data["fire_number"]) == (costs * 100 / D("4.0")).quantize(D("0.01"))
    expected = min(D(data["investable"]) / D(data["fire_number"]) * 100, D(100))
    assert D(data["progress_pct"]) == expected.quantize(D("0.01"))
    assert D(data["gap"]) == max(D(data["fire_number"]) - D(data["investable"]), D(0))


def test_fire_progress_uses_the_newest_plan_fr17(
    demo_client: TestClient, demo_session: Session
) -> None:
    owner, root = login(demo_client), base(demo_session)
    plan = demo_client.post(
        f"{root}/fire/plan",
        headers=owner,
        json={
            "name": "Check",
            "net_worth": "5000000",
            "monthly_savings": "50000",
            "yearly_expenses": "1000000",
            "nominal_return_pct": "9",
            "inflation_pct": "7",
            "withdrawal_rate_pct": "4",
            "current_age": 38,
        },
    )
    assert plan.status_code == 201, plan.text
    body = demo_client.get(f"{root}/fire/progress", headers=owner).json()
    data = body["data"]
    assert body["as_of"] and data["basis"] == "PLAN"
    assert data["plan"]["id"] == plan.json()["id"]
    assert D(data["fire_number"]) == D("25000000.00")
    if data["plan"]["fire_age"] is not None:
        assert D(data["plan"]["years_to_fire"]) == D(data["plan"]["fire_age"]) - 38
    assert data["savings_rate_pct"] is not None


def test_fire_progress_without_costs_gives_no_number_fr17_2(
    demo_client: TestClient, demo_session: Session
) -> None:
    """A brand-new household with no records: nothing to estimate from."""
    add_user(demo_session, "fresh@example.com")
    headers = login(demo_client, "fresh@example.com")
    household = demo_client.post("/api/v1/households", headers=headers, json={"name": "Fresh"})
    assert household.status_code == 201, household.text
    hid = household.json()["id"]
    body = demo_client.get(f"/api/v1/households/{hid}/fire/progress", headers=headers).json()
    data = body["data"]
    assert data["basis"] == "NO_COSTS"
    assert data["fire_number"] is None and data["progress_pct"] is None
