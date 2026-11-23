"""Income records (F27): income_rule and income_entry.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _stamps() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "income_rule",
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("frequency", sa.String(length=20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_stamps(),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], name=op.f("fk_income_rule_household_id_household"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["household_member.id"], name=op.f("fk_income_rule_member_id_household_member"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_income_rule")),
    )
    op.create_index(op.f("ix_income_rule_household_id"), "income_rule", ["household_id"], unique=False)
    op.create_table(
        "income_entry",
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("recurring_id", sa.Uuid(), nullable=True),
        *_stamps(),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], name=op.f("fk_income_entry_household_id_household"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["household_member.id"], name=op.f("fk_income_entry_member_id_household_member"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["recurring_id"], ["income_rule.id"], name=op.f("fk_income_entry_recurring_id_income_rule"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_income_entry")),
        sa.UniqueConstraint("recurring_id", "date", name=op.f("uq_income_entry_recurring_id")),
    )
    op.create_index(op.f("ix_income_entry_date"), "income_entry", ["date"], unique=False)
    op.create_index(op.f("ix_income_entry_household_id"), "income_entry", ["household_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_income_entry_household_id"), table_name="income_entry")
    op.drop_index(op.f("ix_income_entry_date"), table_name="income_entry")
    op.drop_table("income_entry")
    op.drop_index(op.f("ix_income_rule_household_id"), table_name="income_rule")
    op.drop_table("income_rule")
