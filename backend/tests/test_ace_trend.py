"""ACE trend: Assets, Capital and Earnings month by month (D23)."""

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import NetWorthSnapshot
from app.services import ace, portfolio
from tests.personal_helpers import base, household_id, login

D = Decimal


def test_snapshot_keeps_capital_at_work_d23(demo_session: Session) -> None:
    hid = household_id(demo_session)
    row = portfolio.store_net_worth(demo_session, hid, date(2026, 11, 15))
    expected = ace.capital_at_work(portfolio.summary(demo_session, hid))
    assert row.capital == expected and row.capital > 0


def test_trend_takes_each_months_last_snapshot_and_records_d23(demo_session: Session) -> None:
    """The demo seed stores month-end snapshots, so every month has net worth and capital.
    Savings each month are income less costs, and the rate is savings / income."""
    hid = household_id(demo_session)
    data = ace.trend(demo_session, hid, months=12, as_of=date(2026, 11, 15))
    months = data["months"]
    assert len(months) == 12
    assert months[0]["month"] == date(2025, 12, 1) and months[-1]["month"] == date(2026, 11, 1)
    for row in months:
        assert row["net_worth"] is not None and row["capital"] is not None
        snap = demo_session.scalar(
            select(NetWorthSnapshot).where(
                NetWorthSnapshot.household_id == hid, NetWorthSnapshot.date == row["snapshot_date"]
            )
        )
        assert snap is not None and snap.net_worth == row["net_worth"]
        assert row["savings"] == row["income"] - row["costs"]
        if row["income"]:
            assert row["savings_rate_pct"] == (row["savings"] / row["income"] * 100).quantize(
                D("0.01")
            )
    change = data["change"]
    assert change["net_worth"] == months[-1]["net_worth"] - months[0]["net_worth"]
    assert change["savings_total"] == sum((m["savings"] for m in months), D(0))


def test_trend_months_without_snapshots_are_empty_not_zero_d23(demo_session: Session) -> None:
    hid = household_id(demo_session)
    demo_session.query(NetWorthSnapshot).filter(NetWorthSnapshot.household_id == hid).delete()
    demo_session.commit()
    data = ace.trend(demo_session, hid, months=6, as_of=date(2026, 11, 15))
    assert all(m["net_worth"] is None and m["capital"] is None for m in data["months"])
    assert data["change"]["net_worth"] is None


def test_trend_endpoint_d23(demo_client: TestClient, demo_session: Session) -> None:
    owner, root = login(demo_client), base(demo_session)
    body = demo_client.get(f"{root}/ace/trend?months=6", headers=owner).json()
    assert body["as_of"] and len(body["data"]["months"]) == 6
    assert demo_client.get(f"{root}/ace/trend?months=1", headers=owner).status_code == 422


def test_trend_without_income_records_leaves_savings_empty_d23(demo_session: Session) -> None:
    """Costs alone must not read as a loss: with no income in the period, income and savings
    are empty; costs still show."""
    from app.models import IncomeEntry

    hid = household_id(demo_session)
    demo_session.query(IncomeEntry).filter(IncomeEntry.household_id == hid).delete()
    demo_session.commit()
    data = ace.trend(demo_session, hid, months=6, as_of=date(2026, 11, 15))
    assert all(m["income"] is None and m["savings"] is None for m in data["months"])
    assert any(m["costs"] for m in data["months"])
    assert data["change"]["savings_total"] is None
