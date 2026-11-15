"""Reference and market data tables (PRD section 9).

Every market data row points at the `source` record it came from, so each number shown to a
user can be traced (PRD section 0, hard rules).
"""

import datetime as dt
import uuid
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin

PRICE = Numeric(18, 4)
RATIO = Numeric(18, 8)


class CorporateActionType(StrEnum):
    BONUS = "BONUS"  # ratio = bonus shares per share held (0.10 for a 10% stock dividend)
    RIGHTS = "RIGHTS"  # ratio = rights shares per share held; amount = issue price
    SPLIT = "SPLIT"  # ratio = new shares per old share (10 for a 1:10 split)
    CASH_DIVIDEND = "CASH_DIVIDEND"  # amount = taka per share; prices are not adjusted for it


class Source(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One fetch of one document or feed."""

    __tablename__ = "source"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64))


class Company(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "company"

    ticker: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(100), index=True)
    listing_date: Mapped[dt.date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("source.id"))


class PriceDaily(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "price_daily"
    __table_args__ = (UniqueConstraint("ticker", "date"),)

    ticker: Mapped[str] = mapped_column(String(20), ForeignKey("company.ticker"), nullable=False)
    date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    open: Mapped[Decimal | None] = mapped_column(PRICE)
    high: Mapped[Decimal | None] = mapped_column(PRICE)
    low: Mapped[Decimal | None] = mapped_column(PRICE)
    close: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    volume: Mapped[int | None] = mapped_column(BigInteger)
    # Back-adjusted for bonus, rights and splits. Null until the adjustment job has run.
    adj_close: Mapped[Decimal | None] = mapped_column(PRICE)
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("source.id"), nullable=False)


class IndexDaily(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Index levels only. The DSES constituent list is never stored (FR2.3)."""

    __tablename__ = "index_daily"
    __table_args__ = (UniqueConstraint("index_code", "date"),)

    index_code: Mapped[str] = mapped_column(String(20), nullable=False)
    date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    close: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("source.id"), nullable=False)


class CorporateAction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "corporate_action"
    __table_args__ = (UniqueConstraint("ticker", "ex_date", "type"),)

    ticker: Mapped[str] = mapped_column(String(20), ForeignKey("company.ticker"), nullable=False)
    ex_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    ratio: Mapped[Decimal | None] = mapped_column(RATIO)
    amount: Mapped[Decimal | None] = mapped_column(PRICE)
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("source.id"), nullable=False)


class MacroSeries(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """T-bill yields, policy rate, CPI, BDT/USD, Brent, gold price and similar series."""

    __tablename__ = "macro_series"
    __table_args__ = (UniqueConstraint("series_code", "date"),)

    series_code: Mapped[str] = mapped_column(String(40), nullable=False)
    date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("source.id"), nullable=False)


class ConfigVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stored copy of each config/*.yaml version that has been in use."""

    __tablename__ = "config_version"
    __table_args__ = (UniqueConstraint("domain", "version"),)

    domain: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    yaml: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(200))
    approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class DataIssue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A failed data quality check, shown in the admin review queue (PRD section 8)."""

    __tablename__ = "data_issue"

    check_name: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    dataset: Mapped[str] = mapped_column(String(40), nullable=False)
    entity: Mapped[str | None] = mapped_column(String(40))
    date: Mapped[dt.date | None] = mapped_column(Date)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", nullable=False, index=True)
    resolved_by: Mapped[str | None] = mapped_column(String(200))
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class JobRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """History of scheduled job runs (PRD section 12, observability)."""

    __tablename__ = "job_run"

    job: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONType)


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Admin actions, overrides and config changes (PRD section 13)."""

    __tablename__ = "audit_log"

    actor: Mapped[str] = mapped_column(String(200), nullable=False)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    entity: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(60))
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
