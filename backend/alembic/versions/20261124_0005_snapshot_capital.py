"""Keep capital at work on each net worth snapshot (D23).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "net_worth_snapshot",
        sa.Column("capital", sa.Numeric(precision=20, scale=2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("net_worth_snapshot", "capital")
