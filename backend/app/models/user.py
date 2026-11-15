"""Accounts, sessions and password reset tokens.

The table is `app_user` because `user` is a reserved word in PostgreSQL.
"""

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.permissions import Role
from app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "app_user"

    # Stored trimmed and lower-case; see services.auth.normalise_email.
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    locale: Mapped[str] = mapped_column(String(5), default="bn", nullable=False)
    role: Mapped[str] = mapped_column(String(20), default=Role.USER.value, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # {purpose: {"granted": bool, "at": ISO time}} (FR23.1, FR23.2).
    consents: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    last_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class UserSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One signed-in device. Web and mobile both hold an opaque token (DECISIONS D10)."""

    __tablename__ = "user_session"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    client: Mapped[str] = mapped_column(String(20), default="web", nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(300))
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class PasswordResetToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "password_reset_token"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
