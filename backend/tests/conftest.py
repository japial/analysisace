"""Shared fixtures. Unit tests use in-memory SQLite (docs/DECISIONS.md, D6)."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import get_db
from app.core.trading_calendar import TradingCalendar
from app.main import app
from app.models import Base, Source


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
