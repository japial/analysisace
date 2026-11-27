"""Daily alert digest (FR7.3, D32): notification.digest_channel and digested_at.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("notification", sa.Column("digest_channel", sa.String(length=10), nullable=True))
    op.add_column(
        "notification", sa.Column("digested_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        op.f("ix_notification_digest_channel"), "notification", ["digest_channel"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_digest_channel"), table_name="notification")
    op.drop_column("notification", "digested_at")
    op.drop_column("notification", "digest_channel")
