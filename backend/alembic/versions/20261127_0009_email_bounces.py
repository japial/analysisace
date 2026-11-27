"""Bounced email (D35): app_user.email_bounced_at and email_bounce_status.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("email_bounced_at", sa.DateTime(timezone=True)))
    op.add_column("app_user", sa.Column("email_bounce_status", sa.String(length=10)))


def downgrade() -> None:
    op.drop_column("app_user", "email_bounce_status")
    op.drop_column("app_user", "email_bounced_at")
