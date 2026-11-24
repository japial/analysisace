"""Email verification at sign-up (D25): app_user.email_verified_at and its tokens.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "app_user", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_table(
        "email_verification_token",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], name=op.f("fk_email_verification_token_user_id_app_user"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_verification_token")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_email_verification_token_token_hash")),
    )
    op.create_index(op.f("ix_email_verification_token_user_id"), "email_verification_token", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_email_verification_token_user_id"), table_name="email_verification_token")
    op.drop_table("email_verification_token")
    op.drop_column("app_user", "email_verified_at")
