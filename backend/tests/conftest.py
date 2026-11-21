"""Shared fixtures. Unit tests use in-memory SQLite (docs/DECISIONS.md, D6)."""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import get_db
from app.core.trading_calendar import TradingCalendar
from app.main import app
from app.models import Base, Source
from app.seed.demo_market import seed_demo_market
from app.seed.demo_personal import seed_demo_personal
from app.services import valuation
from app.services.storage import LocalEncryptedStorage, get_document_storage


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    # SQLite ignores foreign keys unless asked; PostgreSQL always enforces them.
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as db:
        yield db
    engine.dispose()


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def source(session: Session) -> Source:
    row = Source(
        name="Test feed",
        url="https://example.test/feed",
        fetched_at=datetime(2026, 11, 12, 11, 0, tzinfo=UTC),
    )
    session.add(row)
    session.flush()
    return row


@pytest.fixture
def calendar() -> TradingCalendar:
    """Sunday to Thursday, no holidays."""
    return TradingCalendar(trading_weekdays=frozenset({6, 0, 1, 2, 3}))


# --- demo household -------------------------------------------------------------------

DEMO_PASSWORD = "demo-pass-1234"
# A Sunday three days after the last demo price (12 November 2026).
DEMO_NOW = datetime(2026, 11, 15, 6, 0, tzinfo=UTC)


def _sqlite_engine():  # type: ignore[no-untyped-def]
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    return engine


@pytest.fixture(scope="session")
def _demo_template():  # type: ignore[no-untyped-def]
    """The demo data set, seeded once. Each test works on its own copy."""
    engine = _sqlite_engine()
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as db:
        seed_demo_market(db, TradingCalendar(trading_weekdays=frozenset({6, 0, 1, 2, 3})))
        seed_demo_personal(db, DEMO_PASSWORD)
        db.commit()
    yield engine
    engine.dispose()


@pytest.fixture
def demo_session(_demo_template, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:  # type: ignore[no-untyped-def]
    """A fresh copy of the seeded demo database, with the clock fixed at DEMO_NOW."""
    monkeypatch.setattr(valuation, "utcnow", lambda: DEMO_NOW)
    engine = _sqlite_engine()
    source, target = _demo_template.raw_connection(), engine.raw_connection()
    source.driver_connection.backup(target.driver_connection)
    source.close()
    target.close()
    with sessionmaker(bind=engine, expire_on_commit=False)() as db:
        yield db
    engine.dispose()


@pytest.fixture
def demo_client(demo_session: Session, tmp_path: Path) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: demo_session
    app.dependency_overrides[get_document_storage] = lambda: LocalEncryptedStorage(tmp_path)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
