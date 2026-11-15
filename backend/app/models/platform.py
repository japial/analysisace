"""Platform tables: watchlists, alerts, notifications, firms, API keys, subscriptions.

PRD section 9 for features F7, F9 and F20, and the paid plans.
"""

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin


def _user_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True
    )


# --- F7 and F20 alerts ----------------------------------------------------------------


class Watchlist(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A stock the user follows without holding it. Held stocks alert automatically."""

    __tablename__ = "watchlist"
    __table_args__ = (UniqueConstraint("user_id", "ticker"),)

    user_id: Mapped[uuid.UUID] = _user_fk()
    ticker: Mapped[str] = mapped_column(String(20), ForeignKey("company.ticker"), nullable=False)


class AlertRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Which alerts a user wants, by which channel and how often (FR7.3, FR20.1)."""

    __tablename__ = "alert_rule"
    __table_args__ = (UniqueConstraint("user_id", "type"),)

    user_id: Mapped[uuid.UUID] = _user_fk()
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    # Type-specific settings, e.g. {"max_volatility_pct": "25"} for VOLATILITY.
    params: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One alert addressed to one user. Shown in the app; also sent by email or push."""

    __tablename__ = "notification"

    user_id: Mapped[uuid.UUID] = _user_fk()
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    # Message key and values, so the text is rendered in the reader's language.
    message_key: Mapped[str] = mapped_column(String(80), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    link: Mapped[str | None] = mapped_column(String(300))
    # Stops the same event being reported twice to the same user.
    dedupe_key: Mapped[str | None] = mapped_column(String(160), index=True)
    sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class PushSubscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A browser's Web Push endpoint (FR7.1)."""

    __tablename__ = "push_subscription"

    user_id: Mapped[uuid.UUID] = _user_fk()
    endpoint: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    keys: Mapped[dict[str, str]] = mapped_column(JSONType, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(300))


# --- F9 firms -------------------------------------------------------------------------


class Firm(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A broker, asset manager or bank on the Firm plan."""

    __tablename__ = "firm"

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    # White-label weekly PDF (FR9.1).
    logo_ref: Mapped[str | None] = mapped_column(String(300))
    report_disclaimer: Mapped[str | None] = mapped_column(Text)
    seat_limit: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class FirmSeat(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "firm_seat"
    __table_args__ = (UniqueConstraint("firm_id", "user_id"),)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("firm.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = _user_fk()
    role: Mapped[str] = mapped_column(String(20), nullable=False)


class ApiKey(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A firm's key for the read-only API. Only the hash is stored (FR9.2)."""

    __tablename__ = "api_key"

    firm_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("firm.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # First characters of the key, shown so a firm can tell its keys apart.
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    last_used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class ApiUsage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Calls per key, endpoint and day."""

    __tablename__ = "api_usage"
    __table_args__ = (UniqueConstraint("api_key_id", "date", "endpoint"),)

    api_key_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("api_key.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    endpoint: Mapped[str] = mapped_column(String(120), nullable=False)
    calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


# --- Paid plans -----------------------------------------------------------------------


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A plan held by a user or a firm, kept apart from any payment provider (DECISIONS D1).

    Exactly one of `user_id` and `firm_id` is set.
    TODO(owner): Q4 - paid plans stay behind a feature flag until the BSEC check is done.
    """

    __tablename__ = "subscription"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="CASCADE"), index=True
    )
    firm_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("firm.id", ondelete="CASCADE"), index=True
    )
    plan: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(30))  # SSLCOMMERZ, BKASH, MANUAL
    provider_ref: Mapped[str | None] = mapped_column(String(200))
    current_period_end: Mapped[dt.date | None] = mapped_column(Date)
