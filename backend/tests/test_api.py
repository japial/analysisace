"""Public API: health, meta and companies (PRD section 10)."""

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Company, PriceDaily, Source


def _seed(session: Session, source: Source) -> None:
    session.add_all(
        [
            Company(ticker="GP", name="Grameenphone Ltd.", sector="Telecom", source_id=source.id),
            Company(ticker="BATBC", name="British American Tobacco", sector="Food & Allied"),
            Company(ticker="OLDCO", name="Delisted Co", is_active=False),
        ]
    )
    session.flush()
    for day, close in ((date(2026, 11, 11), "300.0"), (date(2026, 11, 12), "304.2")):
        session.add(
            PriceDaily(ticker="GP", date=day, close=Decimal(close), volume=10, source_id=source.id)
        )
    session.flush()


def test_health_reports_database(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_meta_lists_config_versions(client: TestClient) -> None:
    body = client.get("/api/v1/meta").json()
    assert body["api_version"] == "v1"
    assert set(body["config_versions"]) >= {"shariah", "zakat", "trading_calendar"}


def test_company_list_has_envelope_with_as_of_and_sources(
    client: TestClient, session: Session, source: Source
) -> None:
    """PRD section 10: data-derived responses include `as_of` and `sources`."""
    _seed(session, source)
    body = client.get("/api/v1/companies").json()

    assert [c["ticker"] for c in body["data"]["items"]] == ["BATBC", "GP"]
    assert body["data"]["total"] == 2
    assert body["as_of"] is not None
    assert body["sources"][0]["name"] == "Test feed"


def test_company_list_filters(client: TestClient, session: Session, source: Source) -> None:
    _seed(session, source)

    def tickers(query: str) -> list[str]:
        items = client.get(f"/api/v1/companies?{query}").json()["data"]["items"]
        return [c["ticker"] for c in items]

    assert tickers("q=grameen") == ["GP"]
    assert tickers("sector=Telecom") == ["GP"]
    assert tickers("active_only=false") == ["BATBC", "GP", "OLDCO"]
    assert tickers("limit=1&offset=1") == ["GP"]


def test_empty_list_has_no_as_of(client: TestClient) -> None:
    body = client.get("/api/v1/companies").json()
    assert body == {
        "data": {"items": [], "total": 0, "limit": 100, "offset": 0},
        "as_of": None,
        "sources": [],
    }


def test_company_detail_returns_latest_price_as_string(
    client: TestClient, session: Session, source: Source
) -> None:
    _seed(session, source)
    body = client.get("/api/v1/companies/gp").json()

    assert body["data"]["ticker"] == "GP"
    price = body["data"]["latest_price"]
    assert price["date"] == "2026-11-12"
    assert price["close"] == "304.2000"  # decimal string, never a float
    assert len(body["sources"]) == 1


def test_company_without_prices(client: TestClient, session: Session, source: Source) -> None:
    _seed(session, source)
    body = client.get("/api/v1/companies/BATBC").json()
    assert body["data"]["latest_price"] is None
    assert body["sources"] == []


def test_unknown_company_is_404(client: TestClient) -> None:
    assert client.get("/api/v1/companies/NOPE").status_code == 404
