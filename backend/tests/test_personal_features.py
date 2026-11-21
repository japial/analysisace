"""Smoke tests for portfolio, assets, sukuk, Zakat, tax, FIRE, goals and alerts (F13 to F26),
on the demo household."""

import base64
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Notification
from app.services import alerts, portfolio
from app.services.email import Email
from tests.personal_helpers import API, base, login, member

D = Decimal


class Outbox:
    def __init__(self) -> None:
        self.sent: list[Email] = []

    def send(self, email: Email) -> None:
        self.sent.append(email)


def test_portfolio_summary_and_net_worth_fr14(
    demo_client: TestClient, demo_session: Session
) -> None:
    owner, root = login(demo_client), base(demo_session)
    body = demo_client.get(f"{root}/portfolio/summary", headers=owner).json()
    data = body["data"]
    assert body["as_of"] and body["sources"]
    assert D(data["net_worth"]) == D(data["assets"]) - D(data["liabilities"])
    shares = [p for p in data["positions"] if p["type"] == "DSE_SHARE"]
    assert len(shares) == 6 and all(p["method"] == "MARKET_PRICE" for p in shares)
    point = demo_client.post(f"{root}/portfolio/history", headers=owner).json()
    assert point["net_worth"] == data["net_worth"]
    assert portfolio.store_all_net_worth(demo_session, date(2026, 11, 15)) == 1


def test_transactions_and_broker_import_fr14_2(
    demo_client: TestClient, demo_session: Session
) -> None:
    owner, root = login(demo_client), base(demo_session)
    accounts = demo_client.get(f"{root}/accounts", headers=owner).json()
    bo = next(a for a in accounts if a["type"] == "BO")
    csv = (
        "Client: demo\nTrading Code,Total Qty,Avg Cost\nDMPHARMA,600,200\nNOPE,10,1\nDMFOOD,50,30\n"
    )
    result = demo_client.post(
        f"{root}/imports/broker-statement",
        headers=owner,
        json={"account_id": bo["id"], "csv": csv},
    ).json()
    assert (result["imported"], result["updated"]) == (1, 1)
    assert result["errors"][0]["code"] == "UNKNOWN_TICKER"
    summary = demo_client.get(f"{root}/portfolio/summary", headers=owner).json()["data"]
    pharma = next(p for p in summary["positions"] if p["ticker"] == "DMPHARMA")
    sell = demo_client.post(
        f"{root}/holdings/{pharma['id']}/transactions",
        headers=owner,
        json={"type": "SELL", "date": "2026-11-12", "amount": "30000", "units": "100"},
    )
    assert sell.status_code == 201
    holding = demo_client.get(f"{root}/holdings/{pharma['id']}", headers=owner).json()
    assert (D(holding["quantity"]), D(holding["cost"])) == (500, D("100000.00"))
    too_many = demo_client.post(
        f"{root}/holdings/{pharma['id']}/transactions",
        headers=owner,
        json={"type": "SELL", "date": "2026-11-12", "amount": "1", "units": "9999"},
    )
    assert too_many.json()["detail"] == "NOT_ENOUGH_UNITS"


def test_account_number_is_encrypted_fr23_3(demo_client: TestClient, demo_session: Session) -> None:
    owner, root = login(demo_client), base(demo_session)
    made = demo_client.post(
        f"{root}/accounts",
        headers=owner,
        json={"type": "CASH", "institution": "Bank", "name": "Savings", "number": "1234 5678 9012"},
    ).json()
    assert made["masked_number"] == "••••9012" and "number" not in made


def test_performance_and_allocation_fr15_fr16(
    demo_client: TestClient, demo_session: Session
) -> None:
    owner, root = login(demo_client), base(demo_session)
    perf = demo_client.get(f"{root}/portfolio/performance?period=1Y", headers=owner).json()["data"]
    assert perf["twr_pct"] is not None and perf["volatility_pct"] is not None
    assert {b["code"] for b in perf["benchmarks"]} == {"DSEX", "DSES", "DS30"}
    alloc = demo_client.get(f"{root}/portfolio/allocation", headers=owner).json()["data"]
    assert abs(sum(D(r["pct"]) for r in alloc["by_class"]) - 100) <= D("0.1")
    assert alloc["drift"]
    bad = demo_client.put(
        f"{root}/portfolio/targets",
        headers=owner,
        json={"targets": [{"asset_class": "EQUITY", "target_pct": "50", "band_pct": "5"}]},
    )
    assert bad.json()["detail"] == "TARGETS_MUST_TOTAL_100"


def test_alt_assets_valuation_cash_flows_documents_fr25(
    demo_client: TestClient, demo_session: Session
) -> None:
    owner, root = login(demo_client), base(demo_session)
    assets = demo_client.get(f"{root}/alt-assets", headers=owner).json()["data"]
    flat = next(a for a in assets if a["type"] == "RENTAL_PROPERTY")
    assert flat["xirr_pct"] is not None and D(flat["household_pct"]) == 60
    gold = next(a for a in assets if a["type"] == "GOLD")
    assert gold["value_method"] == "METAL_PRICE"
    url = f"{root}/alt-assets/{flat['id']}"
    assert (
        demo_client.post(
            f"{url}/valuations", headers=owner, json={"date": "2026-11-01", "value": "6000000"}
        ).status_code
        == 201
    )
    content = base64.b64encode(b"deed text").decode()
    doc = demo_client.post(
        f"{url}/documents",
        headers=owner,
        json={"type": "DEED", "filename": "C:\\x\\deed.pdf", "content_base64": content},
    ).json()
    assert doc["filename"] == "deed.pdf"
    download = demo_client.get(f"{url}/documents/{doc['id']}", headers=owner)
    assert download.content == b"deed text"
    assert download.headers["content-type"] == "application/octet-stream"


def test_sukuk_views_fr26(demo_client: TestClient, demo_session: Session) -> None:
    owner, root = login(demo_client), base(demo_session)
    holdings = demo_client.get(f"{root}/sukuk/holdings", headers=owner).json()["data"]
    assert len(holdings) == 3 and all(h["rate_pct"] for h in holdings)
    calendar = demo_client.get(f"{root}/sukuk/calendar", headers=owner).json()
    kinds = {e["kind"] for e in calendar}
    assert {"MATURITY", "SUKUK_AUCTION"} <= kinds
    compare = demo_client.get(f"{API}/islamic-products/compare", headers=owner).json()["data"]
    assert compare["tbill_pct"] and all("real_rate_pct" in r for r in compare["rows"])
    safety = demo_client.get(f"{root}/sukuk/bank-safety", headers=owner).json()
    assert abs(sum(D(r["share_pct"]) for r in safety) - 100) <= D("0.1")


def test_zakat_and_tax_snapshots_fr13(demo_client: TestClient, demo_session: Session) -> None:
    owner, root = login(demo_client), base(demo_session)
    karim = member(demo_session, "Karim")
    snap = demo_client.post(
        f"{root}/zakat/snapshots", headers=owner, json={"member_id": str(karim.id)}
    )
    assert snap.status_code == 201, snap.text
    data = snap.json()["data"]
    assert data["nisab_basis"] == "GOLD" and D(data["zakat_due"]) > 0
    assert D(data["zakat_due"]) == (D(data["net_zakatable"]) * D("0.025")).quantize(D("0.01"))
    home = next(i for i in data["items"] if i["rule"] == "family_home")
    assert D(home["zakatable"]) == 0
    tax = demo_client.post(
        f"{root}/tax/snapshots",
        headers=owner,
        json={"member_id": str(karim.id), "tax_year": "2025-26", "salary_income": "900000"},
    ).json()["data"]
    assert D(tax["items"]["income"]["dividends"]) == D("3600.00")
    csv = demo_client.get(f"{root}/tax/snapshots/{tax['id']}/export.csv", headers=owner).text
    assert "Not investment advice" in csv
    bad = demo_client.post(
        f"{root}/tax/snapshots",
        headers=owner,
        json={"member_id": str(karim.id), "tax_year": "2025-27"},
    )
    assert bad.json()["detail"] == "TAX_YEAR_INVALID"


def test_fire_plan_scenarios_and_goals_fr17_fr18_fr19(
    demo_client: TestClient, demo_session: Session
) -> None:
    owner, root = login(demo_client), base(demo_session)
    defaults = demo_client.get(f"{root}/fire/defaults", headers=owner).json()["data"]
    assert D(defaults["illiquid_excluded"]) > 0 and defaults["current_age"] == 38
    plan = demo_client.post(
        f"{root}/fire/plan",
        headers=owner,
        json={
            "name": "Base",
            "net_worth": defaults["net_worth"],
            "monthly_savings": "60000",
            "yearly_expenses": defaults["yearly_expenses"],
            "nominal_return_pct": defaults["nominal_return_pct"],
            "inflation_pct": defaults["inflation_pct"],
            "withdrawal_rate_pct": "4",
            "current_age": 38,
        },
    ).json()
    assert plan["fire_age"] is not None
    crash = demo_client.post(
        f"{root}/fire/scenarios",
        headers=owner,
        json={"plan_id": plan["id"], "preset": "MARKET_CRASH"},
    ).json()["data"]
    assert D(crash["result"]["fire_age_change"]) >= 0
    events = demo_client.get(f"{API}/events").json()
    replay = demo_client.post(
        f"{root}/fire/scenarios",
        headers=owner,
        json={
            "plan_id": plan["id"],
            "preset": "EVENT_REPLAY",
            "params": {"event_id": events[0]["id"]},
        },
    )
    assert replay.status_code == 201, replay.text
    goals = demo_client.get(f"{root}/goals", headers=owner).json()["data"]
    assert len(goals) == 3 and all(g["progress_pct"] is not None for g in goals)


def test_alerts_and_monthly_report_fr20(demo_client: TestClient, demo_session: Session) -> None:
    outbox = Outbox()
    created = alerts.run_personal_alerts(demo_session, outbox, date(2026, 11, 15))
    assert created > 0
    assert alerts.run_personal_alerts(demo_session, outbox, date(2026, 11, 15)) == 0  # deduped
    types = set(demo_session.scalars(select(Notification.type)))
    assert {"ALLOCATION_DRIFT", "REVALUATION_DUE"} <= types
    assert all("Not investment advice" in e.body for e in outbox.sent)
    assert alerts.send_monthly_reports(demo_session, outbox, "http://x", date(2026, 12, 1)) == 1
    owner = login(demo_client)
    listed = demo_client.get(f"{API}/notifications", headers=owner).json()
    assert listed["unread"] > 0
    demo_client.post(f"{API}/notifications/read", headers=owner, json={})
    assert demo_client.get(f"{API}/notifications", headers=owner).json()["unread"] == 0


def test_community_needs_consent_and_a_large_group_fr21(
    demo_client: TestClient, demo_session: Session
) -> None:
    owner = login(demo_client)
    refused = demo_client.get(f"{API}/community/benchmarks", headers=owner)
    assert refused.json()["detail"] == "CONSENT_REQUIRED"
