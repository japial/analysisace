"""Market intelligence tables: screening, scores, events, regimes, notes, Islamic products.

PRD section 9, "Reference and market data", for features F1 to F9 and F26.
Derived tables (`shariah_result`, `score`, `event_metric`, `regime_month`) are written only
by analytics jobs, never typed in, so every value can be reproduced from stored inputs.
"""

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
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
PCT = Numeric(12, 6)  # percentages and returns, e.g. 4.420000 or -0.153210
TICKER = String(20)


# --- F1 Shariah screen ----------------------------------------------------------------


class Financials(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Figures taken from a company report. Shown only after a person has reviewed them."""

    __tablename__ = "financials"
    __table_args__ = (UniqueConstraint("ticker", "period_end", "period_type"),)

    ticker: Mapped[str] = mapped_column(TICKER, ForeignKey("company.ticker"), nullable=False)
    period_end: Mapped[dt.date] = mapped_column(Date, nullable=False)
    period_type: Mapped[str] = mapped_column(String(10), nullable=False)
    # Any of these may be null when the report does not state it; screening then gives
    # UNDER_REVIEW (FR1 acceptance criteria).
    total_debt_interest_bearing: Mapped[Decimal | None] = mapped_column(MONEY)
    cash_and_interest_securities: Mapped[Decimal | None] = mapped_column(MONEY)
    receivables: Mapped[Decimal | None] = mapped_column(MONEY)
    total_revenue: Mapped[Decimal | None] = mapped_column(MONEY)
    non_permissible_income: Mapped[Decimal | None] = mapped_column(MONEY)
    zakatable_assets: Mapped[Decimal | None] = mapped_column(MONEY)
    shares_outstanding: Mapped[int | None] = mapped_column(BigInteger)
    # FR1.3: each figure links to its source document, with the page if known.
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("source.id"), nullable=False)
    source_page: Mapped[int | None] = mapped_column(Integer)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class BusinessClassification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stage 1 of the screen: is the core business permissible (PRD 7.1). Admin-maintained."""

    __tablename__ = "business_classification"

    ticker: Mapped[str] = mapped_column(
        TICKER, ForeignKey("company.ticker"), unique=True, nullable=False
    )
    stage1_pass: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # One of `stage1_excluded_activities` in config/shariah.yaml when it fails.
    activity: Mapped[str | None] = mapped_column(String(60))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    method_version: Mapped[str] = mapped_column(String(40), nullable=False)
    set_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="SET NULL")
    )


class ShariahResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One run of one methodology for one reporting period. Never updated; history is kept."""

    __tablename__ = "shariah_result"
    __table_args__ = (UniqueConstraint("ticker", "period_end", "method", "method_version"),)

    ticker: Mapped[str] = mapped_column(TICKER, ForeignKey("company.ticker"), nullable=False)
    period_end: Mapped[dt.date] = mapped_column(Date, nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)  # aaoifi | sp
    method_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # FR1.2: [{rule, value_pct, threshold_pct, passed, note}] for every rule tested.
    ratios: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSONType, nullable=False)
    financials_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("financials.id"))
    screened_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CompanyShariahStatus(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The status shown for a company now: the default method's latest result, or an override."""

    __tablename__ = "company_shariah_status"

    ticker: Mapped[str] = mapped_column(
        TICKER, ForeignKey("company.ticker"), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    method_version: Mapped[str] = mapped_column(String(40), nullable=False)
    result_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("shariah_result.id"))
    screened_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Income ratio used for dividend purification (FR6.3). Null when unknown.
    non_permissible_income_ratio: Mapped[Decimal | None] = mapped_column(PCT)
    # FR1.6: a manual override needs a reason and is audited.
    override_status: Mapped[str | None] = mapped_column(String(20))
    override_reason: Mapped[str | None] = mapped_column(Text)
    override_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="SET NULL")
    )
    board_note: Mapped[str | None] = mapped_column(Text)


class ShariahStatusChange(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Status history (FR1.4). Each row can trigger holder alerts (FR7.1)."""

    __tablename__ = "shariah_status_change"

    ticker: Mapped[str] = mapped_column(
        TICKER, ForeignKey("company.ticker"), nullable=False, index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    cause: Mapped[str] = mapped_column(String(20), nullable=False)  # SCREEN | OVERRIDE
    result_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("shariah_result.id"))
    changed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# --- F3 scores, F5 events, F8 regimes -------------------------------------------------


class Score(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A computed score for a stock or a sector, with its sample and confidence (FR3)."""

    __tablename__ = "score"
    __table_args__ = (UniqueConstraint("subject_type", "subject", "score_type"),)

    subject_type: Mapped[str] = mapped_column(String(10), nullable=False)
    subject: Mapped[str] = mapped_column(String(100), nullable=False)  # ticker or sector name
    score_type: Mapped[str] = mapped_column(String(40), nullable=False)
    # Percent move per 1-point rise in the 91-day yield. Null when data is insufficient.
    value: Mapped[Decimal | None] = mapped_column(PCT)
    std_error: Mapped[Decimal | None] = mapped_column(PCT)
    t_stat: Mapped[Decimal | None] = mapped_column(PCT)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    n_obs: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_start: Mapped[dt.date | None] = mapped_column(Date)
    sample_end: Mapped[dt.date | None] = mapped_column(Date)
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Event(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A shock in the admin-curated event library (FR5.1)."""

    __tablename__ = "event"

    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # First day of the event. Returns are measured from the last session before it.
    t0: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    title_en: Mapped[str] = mapped_column(String(200), nullable=False)
    title_bn: Mapped[str] = mapped_column(String(200), nullable=False)
    description_en: Mapped[str] = mapped_column(Text, nullable=False)
    description_bn: Mapped[str] = mapped_column(Text, nullable=False)
    source_links: Mapped[list[dict[str, str]]] = mapped_column(JSONType, nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class EventMetric(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """How one stock or sector behaved around one event (FR5.2)."""

    __tablename__ = "event_metric"
    __table_args__ = (UniqueConstraint("event_id", "subject_type", "subject"),)

    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("event.id", ondelete="CASCADE"), nullable=False
    )
    subject_type: Mapped[str] = mapped_column(String(10), nullable=False)
    subject: Mapped[str] = mapped_column(String(100), nullable=False)
    # Percent returns after 1, 5 and 20 sessions. Null when the data does not reach that far.
    ret_1: Mapped[Decimal | None] = mapped_column(PCT)
    ret_5: Mapped[Decimal | None] = mapped_column(PCT)
    ret_20: Mapped[Decimal | None] = mapped_column(PCT)
    max_dd_60: Mapped[Decimal | None] = mapped_column(PCT)
    # Null means "not recovered" within the data available.
    sessions_to_recover: Mapped[int | None] = mapped_column(Integer)
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RegimeMonth(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The rules-based macro regime for one month (FR8.1)."""

    __tablename__ = "regime_month"

    month: Mapped[dt.date] = mapped_column(Date, unique=True, nullable=False)  # first of month
    label: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    components: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    config_version: Mapped[str] = mapped_column(String(40), nullable=False)


class RegimeSectorStat(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A sector's record in past months that carried the same regime label (FR8.2)."""

    __tablename__ = "regime_sector_stat"
    __table_args__ = (UniqueConstraint("label", "sector"),)

    label: Mapped[str] = mapped_column(String(120), nullable=False)
    sector: Mapped[str] = mapped_column(String(100), nullable=False)
    avg_monthly_return: Mapped[Decimal] = mapped_column(PCT, nullable=False)
    hit_rate: Mapped[Decimal] = mapped_column(PCT, nullable=False)  # share of months above zero
    n_months: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# --- F4 weekly macro note -------------------------------------------------------------


class MacroNote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Weekly note: generated as a draft from stored data, then edited and published (FR4)."""

    __tablename__ = "macro_note"
    __table_args__ = (UniqueConstraint("week_start", "locale"),)

    week_start: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)  # a Sunday
    locale: Mapped[str] = mapped_column(String(5), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # [{code, label, value, change, as_of, source_id}]: no figure without a source (FR4 AC).
    figures: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False)
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="SET NULL")
    )
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


# --- F26 sukuk and Islamic bank products ----------------------------------------------


class SukukIssue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sukuk_issue"

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    issuer: Mapped[str] = mapped_column(String(200), nullable=False)
    structure: Mapped[str] = mapped_column(String(40), nullable=False)  # IJARAH, MUDARABA, ...
    is_government: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ticker: Mapped[str | None] = mapped_column(TICKER)  # when listed on the DSE
    issue_date: Mapped[dt.date | None] = mapped_column(Date)
    maturity_date: Mapped[dt.date | None] = mapped_column(Date)
    rate_pct: Mapped[Decimal | None] = mapped_column(PCT)
    payment_frequency: Mapped[str | None] = mapped_column(String(20))
    min_investment: Mapped[Decimal | None] = mapped_column(MONEY)
    # Upcoming auction, for notices (FR26.3).
    auction_date: Mapped[dt.date | None] = mapped_column(Date, index=True)
    individual_quota_pct: Mapped[Decimal | None] = mapped_column(PCT)
    source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("source.id"))


class IslamicProduct(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Catalogue of Islamic bank products. Names vary by bank, so it is data, not code."""

    __tablename__ = "islamic_product"
    __table_args__ = (UniqueConstraint("bank", "name", "tenor_months"),)

    bank: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    product_type: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    tenor_months: Mapped[int | None] = mapped_column(Integer)
    expected_rate_pct: Mapped[Decimal | None] = mapped_column(PCT)
    # Mudaraba rates are provisional until the bank declares the final rate (FR26.2).
    rate_is_provisional: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    as_of: Mapped[dt.date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("source.id"))


class BankFlag(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Admin-maintained notice about a bank, neutral and sourced (FR26.5)."""

    __tablename__ = "bank_flag"

    bank: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    note_en: Mapped[str] = mapped_column(Text, nullable=False)
    note_bn: Mapped[str] = mapped_column(Text, nullable=False)
    source_links: Mapped[list[dict[str, str]]] = mapped_column(JSONType, nullable=False)
    set_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="SET NULL")
    )
