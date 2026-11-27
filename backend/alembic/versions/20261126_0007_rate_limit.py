"""Rate limits on sign-up, sign-in, reset and verification emails (D28).

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_hit",
        sa.Column("bucket", sa.String(length=40), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rate_limit_hit")),
    )
    op.create_index(
        "ix_rate_limit_hit_lookup", "rate_limit_hit", ["bucket", "key_hash", "created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_rate_limit_hit_lookup", table_name="rate_limit_hit")
    op.drop_table("rate_limit_hit")
