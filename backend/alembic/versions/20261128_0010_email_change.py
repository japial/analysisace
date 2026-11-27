"""Changing the sign-in email (D39): email_change_token.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_change_token",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("new_email", sa.String(length=254), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_email_change_token_user_id"), "email_change_token", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_email_change_token_user_id"), table_name="email_change_token")
    op.drop_table("email_change_token")
