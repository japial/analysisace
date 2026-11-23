"""Personal finance tables: households, holdings, costs, Zakat, tax, FIRE, goals.

PRD section 9, "Users and personal finance", for features F12 to F20 and F24 to F26.
Everything hangs off a household, so access is checked once: is the user a member of it.
Every table here holds personal data; new ones must be added to the export and deletion
code in services/auth.py (FR23.4).
"""

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin

MONEY = Numeric(20, 2)
QUANTITY = Numeric(20, 4)
PCT = Numeric(12, 6)


def _household_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        Uuid, ForeignKey("household.id", ondelete="CASCADE"), nullable=False, index=True
    )


# --- F24 households -------------------------------------------------------------------


class Household(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "household"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="SET NULL")
    )


class HouseholdMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A person in a household. Zakat and tax are worked out per member (FR24.3).

    `user_id` is null for a family member who has no login of their own.
    """

    __tablename__ = "household_member"
    __table_args__ = (UniqueConstraint("household_id", "user_id"),)

    household_id: Mapped[uuid.UUID] = _household_fk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="CASCADE"), index=True
    )
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    birth_year: Mapped[int | None] = mapped_column(Integer)  # for FIRE age (FR17.1)
    # Needs the RELIGIOUS_PREFERENCES consent before it is stored (FR23.2).
    hawl_date: Mapped[dt.date | None] = mapped_column(Date)  # next Zakat due date (FR13.5)
    nisab_basis: Mapped[str | None] = mapped_column(String(10))


# --- F14 accounts and holdings --------------------------------------------------------


class Account(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "account"

    household_id: Mapped[uuid.UUID] = _household_fk()
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    institution: Mapped[str] = mapped_column(String(200), nullable=False)  # broker or bank
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Only the last digits are shown. The full number is encrypted (FR23.3).
    masked_number: Mapped[str | None] = mapped_column(String(30))
    encrypted_number: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Holding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One position: shares of a ticker, a sukuk, a deposit, a certificate, cash."""

    __tablename__ = "holding"

    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instrument_type: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(20), ForeignKey("company.ticker"))
    product_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("islamic_product.id"))
    sukuk_issue_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("sukuk_issue.id"))
    # Units for shares and funds; 1 for a deposit or certificate.
    quantity: Mapped[Decimal] = mapped_column(QUANTITY, default=Decimal(1), nullable=False)
    cost: Mapped[Decimal] = mapped_column(MONEY, nullable=False)  # total paid in
    # Value entered by the user for anything without a DSE price (FR14.3).
    manual_value: Mapped[Decimal | None] = mapped_column(MONEY)
    start_date: Mapped[dt.date | None] = mapped_column(Date)
    maturity_date: Mapped[dt.date | None] = mapped_column(Date, index=True)
    expected_rate: Mapped[Decimal | None] = mapped_column(PCT)
    # Mudaraba profit is provisional until the bank declares the final rate (FR26.2).
    final_rate: Mapped[Decimal | None] = mapped_column(PCT)
    payment_frequency: Mapped[str | None] = mapped_column(String(20))
    profit_received: Mapped[Decimal] = mapped_column(MONEY, default=Decimal(0), nullable=False)
    tax_deducted: Mapped[Decimal] = mapped_column(MONEY, default=Decimal(0), nullable=False)
    # Interest-bearing items are flagged for the user's Zakat decision (Q2).
    is_interest_bearing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Transaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transaction"

    holding_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("holding.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)  # always positive
    units: Mapped[Decimal | None] = mapped_column(QUANTITY)
    note: Mapped[str | None] = mapped_column(String(300))


class OwnerShare(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Who owns what share of an asset or liability (FR24.1, FR25.8).

    No row means the whole asset belongs to the household jointly. A co-owner outside
    the household has `external_name` instead of `member_id`.
    """

    __tablename__ = "owner_share"

    asset_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    asset_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("household_member.id", ondelete="CASCADE")
    )
    external_name: Mapped[str | None] = mapped_column(String(120))
    pct: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)


# --- F25 alternative investments ------------------------------------------------------


class AltAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "alt_asset"

    household_id: Mapped[uuid.UUID] = _household_fk()
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    purchase_date: Mapped[dt.date | None] = mapped_column(Date)
    cost: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    counterparty: Mapped[str | None] = mapped_column(String(200))
    expected_exit_date: Mapped[dt.date | None] = mapped_column(Date)
    liquidity: Mapped[str] = mapped_column(String(10), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    # Gold and silver are valued from weight and purity (FR25.2).
    weight_grams: Mapped[Decimal | None] = mapped_column(QUANTITY)
    karat: Mapped[int | None] = mapped_column(Integer)
    revaluation_months: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    shariah_flag: Mapped[str] = mapped_column(String(20), default="UNKNOWN", nullable=False)
    shariah_reason: Mapped[str | None] = mapped_column(String(300))
    # Key into `assets` in config/zakat.yaml; null means "use the default for this type".
    zakat_rule: Mapped[str | None] = mapped_column(String(40))
    # Private loans count for Zakat only if the user expects to get them back (PRD 7.3).
    is_recoverable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # FR25.9: checklist answers for a private deal. No rating is derived from them.
    due_diligence: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Valuation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Value of an asset on a date. History is kept (FR25.2)."""

    __tablename__ = "valuation"
    __table_args__ = (UniqueConstraint("asset_kind", "asset_id", "date"),)

    asset_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    asset_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    value: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)


class CashFlow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Money in (positive) or out (negative) of an alternative asset; feeds XIRR (FR25.3)."""

    __tablename__ = "cash_flow"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("alt_asset.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(String(300))


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An encrypted attachment such as a deed or agreement (FR25.4)."""

    __tablename__ = "document"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("alt_asset.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    # Key of the encrypted object in storage. The file itself is never in the database.
    encrypted_blob_ref: Mapped[str] = mapped_column(String(300), nullable=False)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="SET NULL")
    )


class Liability(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A debt. Net worth is assets minus liabilities (FR14.4)."""

    __tablename__ = "liability"

    household_id: Mapped[uuid.UUID] = _household_fk()
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    lender: Mapped[str | None] = mapped_column(String(200))
    outstanding: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    # Only the part due within the lunar year is deducted for Zakat (PRD 7.3).
    due_within_year: Mapped[Decimal] = mapped_column(MONEY, default=Decimal(0), nullable=False)
    is_interest_bearing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    end_date: Mapped[dt.date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# --- F12 daily cost records -----------------------------------------------------------


class ExpenseCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Default categories have no household; a household can add its own (FR12.1)."""

    __tablename__ = "expense_category"
    __table_args__ = (UniqueConstraint("household_id", "key"),)

    household_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("household.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(40), nullable=False)
    name_en: Mapped[str] = mapped_column(String(80), nullable=False)
    name_bn: Mapped[str] = mapped_column(String(80), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)


class RecurringRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A cost that repeats, such as rent or a DPS instalment (FR12.2)."""

    __tablename__ = "recurring_rule"

    household_id: Mapped[uuid.UUID] = _household_fk()
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("household_member.id", ondelete="SET NULL")
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("expense_category.id"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    note: Mapped[str | None] = mapped_column(String(300))
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[dt.date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Expense(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "expense"
    # One generated entry per rule per date, so a job that runs twice makes no duplicates.
    __table_args__ = (UniqueConstraint("recurring_id", "date"),)

    household_id: Mapped[uuid.UUID] = _household_fk()
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("household_member.id", ondelete="SET NULL")
    )
    date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("expense_category.id"), nullable=False, index=True
    )
    note: Mapped[str | None] = mapped_column(String(300))
    recurring_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("recurring_rule.id", ondelete="SET NULL")
    )


class IncomeRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Income that repeats, such as a monthly salary or rent (FR27.2)."""

    __tablename__ = "income_rule"

    household_id: Mapped[uuid.UUID] = _household_fk()
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("household_member.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    note: Mapped[str | None] = mapped_column(String(300))
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[dt.date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class IncomeEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Money that came in on a date (FR27.1)."""

    __tablename__ = "income_entry"
    # One generated entry per rule per date, so a job that runs twice makes no duplicates.
    __table_args__ = (UniqueConstraint("recurring_id", "date"),)

    household_id: Mapped[uuid.UUID] = _household_fk()
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("household_member.id", ondelete="SET NULL")
    )
    date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(String(300))
    recurring_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("income_rule.id", ondelete="SET NULL")
    )


# --- F13 Zakat and tax ----------------------------------------------------------------


class ZakatSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A Zakat calculation for one person on one date, with every line kept (FR13.1)."""

    __tablename__ = "zakat_snapshot"

    member_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("household_member.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    nisab_basis: Mapped[str] = mapped_column(String(10), nullable=False)
    price_per_gram: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    nisab_value: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    shares_method: Mapped[str] = mapped_column(String(30), nullable=False)
    # [{label, asset_kind, asset_id, value, owner_pct, treatment, zakatable, flag}]
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False)
    total_zakatable: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    total_deductions: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    net_zakatable: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    zakat_due: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    config_version: Mapped[str] = mapped_column(String(40), nullable=False)


class TaxSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Figures for a person's tax return. analysisACE never files returns (FR13.6)."""

    __tablename__ = "tax_snapshot"

    member_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("household_member.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tax_year: Mapped[str] = mapped_column(String(9), nullable=False)  # "2026-27"
    as_of: Mapped[dt.date] = mapped_column(Date, nullable=False)
    # {assets: [...], liabilities: [...], income: {...}, tax_deducted: ..., rebate_eligible: [...]}
    items: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)


# --- F14 net worth, F16 allocation, F17 FIRE, F18 scenarios, F19 goals ----------------


class NetWorthSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Daily net worth history (FR14.4)."""

    __tablename__ = "net_worth_snapshot"
    __table_args__ = (UniqueConstraint("household_id", "date"),)

    household_id: Mapped[uuid.UUID] = _household_fk()
    date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    assets: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    liabilities: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    net_worth: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    breakdown: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)  # by asset class


class TargetAllocation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A target the user set, with a tolerance band. analysisACE never proposes one (FR16.2)."""

    __tablename__ = "target_allocation"
    __table_args__ = (UniqueConstraint("household_id", "asset_class"),)

    household_id: Mapped[uuid.UUID] = _household_fk()
    asset_class: Mapped[str] = mapped_column(String(40), nullable=False)
    target_pct: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    band_pct: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)


class FirePlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fire_plan"

    household_id: Mapped[uuid.UUID] = _household_fk()
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("household_member.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # FR17.1 inputs as decimal strings: net_worth, monthly_savings, yearly_expenses,
    # nominal_return_pct, inflation_pct, withdrawal_rate_pct, current_age, include_illiquid.
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    fire_number: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    # Null when the plan does not reach the FIRE number within the projection horizon.
    fire_age: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    projection: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False)
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ScenarioResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A what-if run against a FIRE plan (FR18)."""

    __tablename__ = "scenario_result"

    fire_plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fire_plan.id", ondelete="CASCADE"), nullable=False, index=True
    )
    preset: Mapped[str] = mapped_column(String(40), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    # {fire_age, fire_age_change, worst_year_net_worth, projection}
    result: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Goal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "goal"

    household_id: Mapped[uuid.UUID] = _household_fk()
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("household_member.id", ondelete="SET NULL")
    )
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    target_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    target_date: Mapped[dt.date | None] = mapped_column(Date)
    target_age: Mapped[int | None] = mapped_column(Integer)
    achieved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
