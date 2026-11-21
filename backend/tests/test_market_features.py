"""Market layer services and API on the demo data set (F1 to F8, M1 data upkeep)."""

import datetime as dt
import uuid
from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    CompanyShariahStatus,
    DataIssue,
    Event,
    EventMetric,
    Financials,
    IndexDaily,
    MacroNote,
    MacroSeries,
    Notification,
    PriceDaily,
    RegimeMonth,
    Score,
    ShariahResult,
    ShariahStatusChange,
    User,
)
from app.seed.demo_market import END
from app.seed.demo_personal import ANALYST_EMAIL, DEMO_EMAIL
from app.services import macro_notes, market_data
from app.services.email import get_email_sender
from app.services.market_pipeline import run_market_analytics
from tests.personal_helpers import API, base, login
from tests.test_user_admin import make_user, sign_in

ADMIN = "admin@example.com"


@pytest.fixture
def analysed(demo_session: Session) -> Session:
    run_market_analytics(demo_session, get_email_sender())
    demo_session.commit()
    return demo_session


@pytest.fixture
def client(analysed: Session, demo_client: TestClient) -> Iterator[TestClient]:
    yield demo_client


def _admin(client: TestClient, session: Session) -> dict[str, str]:
    from app.core.permissions import Role

    make_user(session, ADMIN, Role.ADMIN)
    session.commit()
    return sign_in(client, ADMIN)


def _status(session: Session, ticker: str) -> CompanyShariahStatus:
    row = session.scalar(select(CompanyShariahStatus).where(CompanyShariahStatus.ticker == ticker))
    assert row is not None
    return row


# --- pipeline and F1 ------------------------------------------------------------------


def test_pipeline_screens_every_company_with_both_methods_fr1_2(analysed: Session) -> None:
    statuses = {r.ticker: r.status for r in analysed.scalars(select(CompanyShariahStatus))}
    assert len(statuses) == 13
    assert set(statuses.values()) == {"COMPLIANT", "NON_COMPLIANT", "UNDER_REVIEW"}
    # Stage 1 failures need no ratios.
    assert statuses["DMBANK"] == statuses["DMTOBAC"] == "NON_COMPLIANT"
    # DMTECH's report does not state non-permissible income (FR1 AC: missing -> review).
    assert statuses["DMTECH"] == "UNDER_REVIEW"
    methods = set(analysed.scalars(select(ShariahResult.method).distinct()))
    assert methods == {"aaoifi", "sp"}


def test_rerunning_the_pipeline_keeps_history_without_duplicates_fr1_4(analysed: Session) -> None:
    results = analysed.scalar(select(func.count()).select_from(ShariahResult))
    changes = analysed.scalar(select(func.count()).select_from(ShariahStatusChange))
    detail = run_market_analytics(analysed, get_email_sender())
    assert detail["status_changes"] == 0
    assert analysed.scalar(select(func.count()).select_from(ShariahResult)) == results
    assert analysed.scalar(select(func.count()).select_from(ShariahStatusChange)) == changes


def test_new_reviewed_financials_rescreen_fr1_4(client: TestClient, analysed: Session) -> None:
    headers = login(client, ANALYST_EMAIL)
    body = {
        "ticker": "DMTECH",
        "period_end": "2026-09-30",
        "period_type": "Q1",
        "total_debt_interest_bearing": "1000000",
        "cash_and_interest_securities": "1000000",
        "receivables": "1000000",
        "total_revenue": "50000000",
        "non_permissible_income": "100000",
        "shares_outstanding": 50000000,
        "source_name": "DMTECH Q1 report",
        "source_url": "https://example.test/dmtech-q1.pdf",
        "source_page": 12,
    }
    saved = client.put(f"{API}/admin/financials", json=body, headers=headers)
    assert saved.status_code == 200, saved.text
    assert saved.json()["reviewed_at"] is None
    pending = client.get(f"{API}/admin/financials?reviewed=false", headers=headers).json()
    assert [f["ticker"] for f in pending["items"]] == ["DMTECH"]

    reviewed = client.post(f"{API}/admin/financials/{saved.json()['id']}/review", headers=headers)
    assert reviewed.status_code == 200
    assert _status(analysed, "DMTECH").status == "COMPLIANT"
    page = client.get(f"{API}/companies/DMTECH/shariah").json()["data"]
    assert page["financials"]["source_url"] == "https://example.test/dmtech-q1.pdf"  # FR1.3
    assert page["financials"]["source_page"] == 12
    assert page["history"][0]["from_status"] == "UNDER_REVIEW"


def test_override_needs_permission_and_reason_and_alerts_holders_fr1_6_fr7_1(
    client: TestClient, analysed: Session
) -> None:
    analyst = login(client, ANALYST_EMAIL)
    body = {"status": "COMPLIANT", "reason": "Board ruling 2026-11"}
    assert (
        client.put(f"{API}/admin/shariah/DMCEMENT/override", json=body, headers=analyst).status_code
        == 403
    )

    admin = _admin(client, analysed)
    blank = client.put(
        f"{API}/admin/shariah/DMCEMENT/override",
        json={"status": "COMPLIANT", "reason": " "},
        headers=admin,
    )
    assert blank.status_code == 422
    done = client.put(f"{API}/admin/shariah/DMCEMENT/override", json=body, headers=admin)
    assert done.status_code == 200
    assert done.json()["status"] == "COMPLIANT"

    shown = client.get(f"{API}/companies/DMCEMENT/shariah").json()["data"]
    assert shown["status"] == "COMPLIANT"
    assert shown["screen_status"] == "NON_COMPLIANT"
    assert shown["override_reason"] == "Board ruling 2026-11"
    assert shown["history"][0]["cause"] == "OVERRIDE"
    assert (
        analysed.scalar(select(AuditLog).where(AuditLog.action == "shariah.override")) is not None
    )

    # The demo household holds DMCEMENT, so its owner is told (FR7.1).
    karim = analysed.scalar(select(User).where(User.email == DEMO_EMAIL))
    assert karim is not None
    notice = analysed.scalar(
        select(Notification).where(
            Notification.user_id == karim.id, Notification.message_key == "SHARIAH_STATUS_CHANGED"
        )
    )
    assert notice is not None
    assert notice.data == {
        "ticker": "DMCEMENT",
        "from_status": "NON_COMPLIANT",
        "to_status": "COMPLIANT",
    }

    cleared = client.put(
        f"{API}/admin/shariah/DMCEMENT/override",
        json={"status": None, "reason": "Ruling withdrawn"},
        headers=admin,
    )
    assert cleared.json()["status"] == "NON_COMPLIANT"


def test_classification_change_rescreens(client: TestClient, analysed: Session) -> None:
    admin = _admin(client, analysed)
    bad = client.put(
        f"{API}/admin/shariah/DMPHARMA/classification",
        json={"stage1_pass": False, "activity": "not_a_listed_activity", "reason": "x"},
        headers=admin,
    )
    assert bad.status_code == 422
    ok = client.put(
        f"{API}/admin/shariah/DMPHARMA/classification",
        json={"stage1_pass": False, "activity": "alcohol", "reason": "New line of business"},
        headers=admin,
    )
    assert ok.status_code == 200
    assert _status(analysed, "DMPHARMA").status == "NON_COMPLIANT"
    note = client.put(
        f"{API}/admin/shariah/DMPHARMA/board-note",
        json={"note": "Under board review"},
        headers=admin,
    )
    assert note.json()["board_note"] == "Under board review"
    listing = client.get(f"{API}/admin/shariah", headers=admin).json()
    assert (
        next(i for i in listing if i["ticker"] == "DMPHARMA")["classification"]["activity"]
        == "alcohol"
    )


def test_public_shariah_endpoints_have_as_of_and_sources(client: TestClient) -> None:
    detail = client.get(f"{API}/companies/DMPHARMA/shariah").json()
    assert detail["as_of"] is not None and detail["sources"]
    data = detail["data"]
    assert {r["method"] for r in data["results"]} == {"aaoifi", "sp"}
    rule = next(r for r in data["results"][0]["ratios"] if r["rule"] == "debt_to_market_cap")
    assert {"value_pct", "threshold_pct", "passed"} <= set(rule)
    assert data["config_approved"] is False  # provisional until Q1

    listing = client.get(f"{API}/shariah/list?status=COMPLIANT&sort=market_cap&order=desc").json()
    items = listing["data"]["items"]
    assert items and all(i["status"] == "COMPLIANT" for i in items)
    caps = [Decimal(i["market_cap"]) for i in items]
    assert caps == sorted(caps, reverse=True)
    assert listing["sources"]
    assert client.get(f"{API}/companies/NOPE/shariah").status_code == 404


def test_basket_rebased_against_indices_fr2_2(client: TestClient, analysed: Session) -> None:
    body = client.get(f"{API}/shariah/basket?years=3").json()
    series = body["data"]["series"]
    assert set(series) == {"AACE_SHARIAH_EW", "DSES", "DSEX"}
    for points in series.values():
        assert points[0]["value"] == "100.00"
    assert body["data"]["members"] == sorted(
        r.ticker for r in analysed.scalars(select(CompanyShariahStatus)) if r.status == "COMPLIANT"
    )
    assert body["as_of"] is not None


# --- F3 -------------------------------------------------------------------------------


def test_rate_scores_for_stocks_and_sectors_fr3(client: TestClient, analysed: Session) -> None:
    rows = list(analysed.scalars(select(Score)))
    assert {r.subject_type for r in rows} == {"TICKER", "SECTOR"}
    assert {r.score_type for r in rows} == {"RATE_SENSITIVITY", "RATE_SENSITIVITY_NO_MARKET"}
    cement = next(r for r in rows if r.subject == "DMCEMENT" and r.score_type == "RATE_SENSITIVITY")
    # The demo path builds in -4% per point; floor-price weeks are left out (FR3.2).
    assert cement.value is not None and cement.value < 0
    assert cement.n_obs >= 104
    assert cement.sample_start is not None and cement.sample_end is not None

    scores = client.get(f"{API}/companies/DMCEMENT/scores").json()
    assert {(s["subject_type"], s["score_type"]) for s in scores["data"]} >= {
        ("TICKER", "RATE_SENSITIVITY"),
        ("SECTOR", "RATE_SENSITIVITY"),
    }
    overview = client.get(f"{API}/rates/overview").json()["data"]
    assert [a["code"] for a in overview["latest_auctions"]] == [
        "TBILL_91D",
        "TBILL_182D",
        "TBILL_364D",
    ]
    assert len(overview["yield_trend"]) > 40  # weekly auctions over 12 months (FR3.5)


# --- series ---------------------------------------------------------------------------


def test_index_and_macro_series(client: TestClient) -> None:
    dsex = client.get(f"{API}/indices/DSEX/series?start=2026-11-01").json()
    assert dsex["data"]["code"] == "DSEX" and dsex["data"]["points"]
    assert dsex["sources"] and dsex["as_of"]
    gold = client.get(f"{API}/macro/series/GOLD_22K_BDT_PER_GRAM?start=2026-11-10").json()
    assert gold["data"]["points"]
    assert "TBILL_91D" in client.get(f"{API}/macro/series").json()["macro"]
    assert client.get(f"{API}/indices/NOPE/series").status_code == 404


def test_metal_price_entry_q9(client: TestClient, analysed: Session) -> None:
    analyst = login(client, ANALYST_EMAIL)
    latest = analysed.scalar(
        select(MacroSeries)
        .where(MacroSeries.series_code == "GOLD_22K_BDT_PER_GRAM")
        .order_by(MacroSeries.date.desc())
    )
    assert latest is not None
    day = (latest.date + dt.timedelta(days=1)).isoformat()
    too_big = str((latest.value * Decimal("1.5")).quantize(Decimal("0.01")))
    refused = client.post(
        f"{API}/admin/metal-prices",
        json={"code": "GOLD_22K_BDT_PER_GRAM", "date": day, "value": too_big},
        headers=analyst,
    )
    assert refused.status_code == 422
    assert refused.json()["detail"] == "PRICE_CHANGE_TOO_LARGE"
    value = str((latest.value * Decimal("1.01")).quantize(Decimal("0.01")))
    ok = client.post(
        f"{API}/admin/metal-prices",
        json={"code": "GOLD_22K_BDT_PER_GRAM", "date": day, "value": value},
        headers=analyst,
    )
    assert ok.status_code == 201
    assert (
        client.post(
            f"{API}/admin/metal-prices",
            json={"code": "BRENT_USD", "date": day, "value": "80"},
            headers=analyst,
        ).status_code
        == 422
    )
    user = login(client, DEMO_EMAIL)
    assert (
        client.post(
            f"{API}/admin/metal-prices",
            json={"code": "GOLD_22K_BDT_PER_GRAM", "date": day, "value": value},
            headers=user,
        ).status_code
        == 403
    )


def test_series_csv_import_is_all_or_nothing(client: TestClient, analysed: Session) -> None:
    analyst = login(client, ANALYST_EMAIL)
    bad = "code,date,value\nDSEX,2026-11-15,7000\nFOO,2026-11-15,1\n"
    result = client.post(
        f"{API}/admin/series/import",
        json={"kind": "index", "content": bad, "source_name": "Backfill"},
        headers=analyst,
    ).json()
    assert result["errors"] and result["inserted"] == 0
    assert (
        analysed.scalar(
            select(IndexDaily).where(
                IndexDaily.index_code == "DSEX", IndexDaily.date == dt.date(2026, 11, 15)
            )
        )
        is None
    )
    good = "code,date,value\nDSEX,2026-11-15,7000\nDSES,2026-11-15,1500\n"
    result = client.post(
        f"{API}/admin/series/import",
        json={"kind": "index", "content": good, "source_name": "Backfill"},
        headers=analyst,
    ).json()
    assert result == {"inserted": 2, "updated": 0, "errors": []}


def test_adjusted_closes_match_seed_and_follow_new_actions(
    client: TestClient, analysed: Session
) -> None:
    seeded = {
        r.date: r.adj_close
        for r in analysed.scalars(select(PriceDaily).where(PriceDaily.ticker == "DMPHARMA"))
    }
    for row in analysed.scalars(select(PriceDaily).where(PriceDaily.ticker == "DMPHARMA")):
        row.adj_close = None
    analysed.flush()
    assert market_data.recompute_adjusted_closes(analysed) > 0
    again = {
        r.date: r.adj_close
        for r in analysed.scalars(select(PriceDaily).where(PriceDaily.ticker == "DMPHARMA"))
    }
    assert again == seeded

    analyst = login(client, ANALYST_EMAIL)
    action = {
        "ticker": "DMAGRO",
        "ex_date": "2026-10-01",
        "type": "SPLIT",
        "ratio": "2",
        "source_name": "DSE notice",
    }
    assert (
        client.post(f"{API}/admin/corporate-actions", json=action, headers=analyst).status_code
        == 201
    )
    before = analysed.scalar(
        select(PriceDaily)
        .where(PriceDaily.ticker == "DMAGRO", PriceDaily.date < dt.date(2026, 10, 1))
        .order_by(PriceDaily.date.desc())
    )
    assert before is not None and before.adj_close is not None
    assert before.adj_close == (before.close / 2).quantize(Decimal("0.0001"))
    assert (
        client.post(f"{API}/admin/corporate-actions", json=action, headers=analyst).status_code
        == 409
    )


# --- data quality, review queue, audit ------------------------------------------------


def test_quality_checks_fill_the_review_queue(client: TestClient, analysed: Session) -> None:
    from app.core.trading_calendar import TradingCalendar

    calendar = TradingCalendar(trading_weekdays=frozenset({6, 0, 1, 2, 3}))
    # A day well after the last demo price: prices are stale.
    result = market_data.run_quality_checks(analysed, calendar, END + dt.timedelta(days=14))
    assert result["added"] >= 1
    again = market_data.run_quality_checks(analysed, calendar, END + dt.timedelta(days=14))
    assert again["added"] == 0  # open issues are not repeated
    analysed.commit()

    analyst = login(client, ANALYST_EMAIL)
    queue = client.get(f"{API}/admin/data-issues", headers=analyst).json()
    assert queue["total"] >= 1 and queue["open_by_dataset"]
    issue = queue["items"][0]
    done = client.patch(
        f"{API}/admin/data-issues/{issue['id']}",
        json={"status": "RESOLVED", "note": "Holiday"},
        headers=analyst,
    )
    assert done.json()["status"] == "RESOLVED"
    issue_row = analysed.get(DataIssue, uuid.UUID(done.json()["id"]))
    assert issue_row is not None and issue_row.resolved_at is not None
    assert (
        client.get(f"{API}/admin/data-issues", headers=login(client, DEMO_EMAIL)).status_code == 403
    )


def test_audit_log_viewer_needs_audit_view(client: TestClient, analysed: Session) -> None:
    admin = _admin(client, analysed)
    client.put(f"{API}/admin/shariah/DMPHARMA/board-note", json={"note": "x"}, headers=admin)
    page = client.get(f"{API}/admin/audit?action=board_note", headers=admin).json()
    assert page["total"] == 1 and page["items"][0]["entity_id"] == "DMPHARMA"
    assert client.get(f"{API}/admin/audit", headers=login(client, ANALYST_EMAIL)).status_code == 403
    assert client.get(f"{API}/admin/jobs", headers=admin).status_code == 200


# --- F4 -------------------------------------------------------------------------------


def test_macro_note_draft_has_a_source_for_every_figure_fr4(
    client: TestClient, analysed: Session
) -> None:
    notes = macro_notes.generate_draft(analysed, END)
    analysed.commit()
    assert {n.locale for n in notes} == {"en", "bn"}
    en = next(n for n in notes if n.locale == "en")
    assert en.week_start == dt.date(2026, 11, 8)  # the Sunday of that DSE week
    codes = {f["code"] for f in en.figures}
    assert {"TBILL_91D", "POLICY_RATE", "CPI_YOY", "BDT_USD", "BRENT_USD", "DSEX", "DSES"} <= codes
    assert all(f["source_id"] and f["source_name"] for f in en.figures)
    assert "Not investment advice" in en.body

    # Unpublished notes are not public.
    assert client.get(f"{API}/macro/notes/2026-11-08?locale=en").status_code == 404
    editor = login(client, ANALYST_EMAIL)
    edited = client.patch(
        f"{API}/admin/notes/{en.id}",
        json={"title": "Week of 8 November", "body": en.body},
        headers=editor,
    )
    assert edited.status_code == 200
    assert (
        client.post(
            f"{API}/admin/notes/{en.id}/publish", json={"published": True}, headers=editor
        ).status_code
        == 200
    )
    public = client.get(f"{API}/macro/notes/2026-11-10?locale=en").json()
    assert public["data"]["title"] == "Week of 8 November"
    assert public["sources"] and public["as_of"]
    assert [n["locale"] for n in client.get(f"{API}/macro/notes?locale=en").json()] == ["en"]

    # The job never overwrites a published note.
    macro_notes.generate_draft(analysed, END, replace_draft=True)
    note = analysed.get(MacroNote, en.id)
    assert note is not None and note.title == "Week of 8 November"


# --- F5 -------------------------------------------------------------------------------


def test_event_metrics_and_similar_events_fr5(client: TestClient, analysed: Session) -> None:
    events = client.get(f"{API}/events").json()
    slugs = [e["slug"] for e in events]
    assert "maheshkhali-lng-fire-2026" not in slugs  # unpublished
    detail = client.get(f"{API}/events/strikes-on-iran-2026").json()
    metrics = detail["data"]["metrics"]
    assert {m["subject_type"] for m in metrics} == {"TICKER", "SECTOR", "INDEX"}
    dsex = next(m for m in metrics if m["subject"] == "DSEX")
    assert Decimal(dsex["ret_1"]) < 0  # the demo shock pattern starts with a fall
    assert [e["slug"] for e in detail["data"]["similar"]] == [
        "us-strikes-iran-israel-war-2025",
        "russia-ukraine-2022",
    ]
    assert client.get(f"{API}/events/maheshkhali-lng-fire-2026").status_code == 404
    per_stock = client.get(f"{API}/companies/DMPOWER/events").json()["data"]
    assert len(per_stock) == 3


def test_publishing_an_event_computes_metrics_and_alerts_opted_in_users_fr7_2(
    client: TestClient, analysed: Session
) -> None:
    editor = login(client, ANALYST_EMAIL)
    events = client.get(f"{API}/admin/events", headers=editor).json()
    lng = next(e for e in events if e["slug"] == "maheshkhali-lng-fire-2026")
    published = client.post(
        f"{API}/admin/events/{lng['id']}/publish", json={"published": True}, headers=editor
    )
    assert published.status_code == 200
    count = analysed.scalar(
        select(func.count())
        .select_from(EventMetric)
        .where(EventMetric.event_id == uuid.UUID(published.json()["id"]))
    )
    assert count and count > 10
    # The demo owner turned SHOCK_EVENT alerts on.
    karim = analysed.scalar(select(User).where(User.email == DEMO_EMAIL))
    assert karim is not None
    assert (
        analysed.scalar(
            select(Notification).where(
                Notification.user_id == karim.id,
                Notification.message_key == "SHOCK_EVENT_PUBLISHED",
            )
        )
        is not None
    )


def test_event_crud(client: TestClient, analysed: Session) -> None:
    editor = login(client, ANALYST_EMAIL)
    body = {
        "slug": "policy-rate-cut-2026",
        "type": "POLICY",
        "t0": "2026-10-05",
        "title_en": "Policy rate cut",
        "title_bn": "নীতি সুদহার কমানো",
        "description_en": "Bangladesh Bank cut the policy rate.",
        "description_bn": "বাংলাদেশ ব্যাংক নীতি সুদহার কমিয়েছে।",
        "source_links": [{"label": "Press release", "url": "https://example.test/pr"}],
    }
    created = client.post(f"{API}/admin/events", json=body, headers=editor)
    assert created.status_code == 201
    assert client.post(f"{API}/admin/events", json=body, headers=editor).status_code == 409
    bad = {**body, "slug": "x-2", "source_links": [{"label": "x", "url": "javascript:alert(1)"}]}
    assert client.post(f"{API}/admin/events", json=bad, headers=editor).status_code == 422
    event_id = created.json()["id"]
    body.pop("slug")
    changed = client.patch(
        f"{API}/admin/events/{event_id}",
        json={**body, "title_en": "Policy rate cut by 50 bp"},
        headers=editor,
    )
    assert changed.json()["title_en"] == "Policy rate cut by 50 bp"
    assert client.delete(f"{API}/admin/events/{event_id}", headers=editor).status_code == 204
    analysed.expire_all()
    assert analysed.get(Event, uuid.UUID(event_id)) is None


# --- F6 -------------------------------------------------------------------------------


def test_market_check_weights_and_groups_fr6(client: TestClient, analysed: Session) -> None:
    headers = login(client, DEMO_EMAIL)
    body = client.get(f"{base(analysed)}/portfolio/market-check", headers=headers).json()
    data = body["data"]
    assert data["holdings"]
    assert sum(Decimal(h["weight_pct"]) for h in data["holdings"]) == 100  # FR6 AC
    assert sum(Decimal(s["weight_pct"]) for s in data["shariah_share"]) == 100
    assert data["rate_sensitivity"]["weighted_pct"] is not None
    assert data["shock_exposure"] and data["shock_exposure"][0]["ret_1"] is not None
    assert "total" in data["purification"]
    assert body["as_of"]


def test_purification_uses_dividends_and_income_ratio_fr6_3(
    client: TestClient, analysed: Session
) -> None:
    headers = login(client, DEMO_EMAIL)
    summary = client.get(f"{base(analysed)}/portfolio/market-check", headers=headers).json()["data"]
    holding = next(h for h in summary["holdings"] if h["non_permissible_income_ratio"])
    added = client.post(
        f"{base(analysed)}/holdings/{holding['holding_id']}/transactions",
        json={"date": "2026-11-01", "type": "DIVIDEND", "amount": "1000"},
        headers=headers,
    )
    assert added.status_code == 201, added.text
    after = client.get(f"{base(analysed)}/portfolio/market-check", headers=headers).json()["data"]
    row = next(h for h in after["holdings"] if h["holding_id"] == holding["holding_id"])
    expected = (
        Decimal(row["dividends_12m"]) * Decimal(row["non_permissible_income_ratio"])
    ).quantize(Decimal("0.01"))
    assert Decimal(row["purification"]) == expected and expected > 0


# --- F8 -------------------------------------------------------------------------------


def test_regime_dashboard_fr8(client: TestClient, analysed: Session) -> None:
    body = client.get(f"{API}/regime?months=12").json()
    data = body["data"]
    assert data["current"]["label"].count("|") == 2
    assert len(data["history"]) == 12
    assert data["sectors"] and all(s["n_months"] >= 1 for s in data["sectors"])
    assert analysed.scalar(select(func.count()).select_from(RegimeMonth)) >= 60


def test_regime_change_alerts_opted_in_users(analysed: Session) -> None:
    from app.models.enums import AlertFrequency, AlertType, Channel
    from app.services.alerts import set_rule

    karim = analysed.scalar(select(User).where(User.email == DEMO_EMAIL))
    assert karim is not None
    set_rule(
        analysed,
        karim,
        type=AlertType.REGIME_CHANGE,
        channel=Channel.PUSH,
        frequency=AlertFrequency.INSTANT,
        is_active=True,
    )
    newest = analysed.scalar(select(RegimeMonth).order_by(RegimeMonth.month.desc()))
    assert newest is not None
    newest.label = "TIGHTENING|LOW|SHOCK"
    analysed.flush()
    detail = run_market_analytics(analysed, get_email_sender())
    assert detail["alerts"] >= 1
    assert (
        analysed.scalar(select(Notification).where(Notification.message_key == "REGIME_CHANGED"))
        is not None
    )


# --- watchlist ------------------------------------------------------------------------


def test_watchlist(client: TestClient, analysed: Session) -> None:
    headers = login(client, DEMO_EMAIL)
    assert client.put(f"{API}/watchlist/DMTEL", headers=headers).status_code == 204
    assert client.put(f"{API}/watchlist/DMTEL", headers=headers).status_code == 204
    items = {i["ticker"]: i for i in client.get(f"{API}/watchlist", headers=headers).json()}
    assert items["DMTEL"]["status"] == "COMPLIANT"
    assert client.put(f"{API}/watchlist/NOPE", headers=headers).status_code == 404
    assert client.delete(f"{API}/watchlist/DMTEL", headers=headers).status_code == 204
    assert "DMTEL" not in {
        i["ticker"] for i in client.get(f"{API}/watchlist", headers=headers).json()
    }
    assert client.get(f"{API}/watchlist").status_code == 401


def test_admin_can_run_the_analytics_now(client: TestClient, analysed: Session) -> None:
    admin = _admin(client, analysed)
    result = client.post(f"{API}/admin/jobs/market-analytics/run", headers=admin)
    assert result.status_code == 200 and result.json()["scores"] > 0
    assert (
        client.post(
            f"{API}/admin/jobs/market-analytics/run", headers=login(client, ANALYST_EMAIL)
        ).status_code
        == 403
    )


def test_unreviewed_financials_are_not_screened(analysed: Session) -> None:
    row = analysed.scalar(
        select(Financials)
        .where(Financials.ticker == "DMTEL")
        .order_by(Financials.period_end.desc())
    )
    assert row is not None
    row.reviewed_at = None
    analysed.flush()
    run_market_analytics(analysed, get_email_sender())
    current = _status(analysed, "DMTEL")
    result = analysed.get(ShariahResult, current.result_id)
    assert result is not None and result.period_end < row.period_end
