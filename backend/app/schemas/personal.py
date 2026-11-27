"""Request and response models for the personal finance API (F12 to F26).

Money is a Decimal and travels as a decimal string. Inputs are bounded so a typing slip
cannot store an absurd figure.
"""

import datetime as dt
import uuid
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import (
    AccountType,
    AlertFrequency,
    AlertType,
    AltAssetType,
    BankStatus,
    CashFlowType,
    Channel,
    GoalType,
    HouseholdRole,
    InstrumentType,
    LiabilityType,
    Liquidity,
    NisabBasis,
    ShariahFlag,
    TransactionType,
)

_CENT = Decimal("0.01")


def _to_cents(value: Decimal) -> Decimal:
    """Money always carries two decimals, so "1000" is stored and returned as "1000.00"."""
    return value.quantize(_CENT)


_MAX = Decimal("999999999999.99")
Money = Annotated[Decimal, Field(ge=0, le=_MAX, decimal_places=2), AfterValidator(_to_cents)]
PositiveMoney = Annotated[
    Decimal, Field(gt=0, le=_MAX, decimal_places=2), AfterValidator(_to_cents)
]
SignedMoney = Annotated[
    Decimal, Field(ge=-_MAX, le=_MAX, decimal_places=2), AfterValidator(_to_cents)
]
Units = Annotated[Decimal, Field(gt=0, le=Decimal("9999999999"), decimal_places=4)]
Pct = Annotated[Decimal, Field(ge=0, le=100, decimal_places=4)]
Rate = Annotated[Decimal, Field(ge=-100, le=1000, decimal_places=4)]
Name = Annotated[str, Field(min_length=1, max_length=120)]
LongName = Annotated[str, Field(min_length=1, max_length=200)]
Note = Annotated[str, Field(max_length=300)]
RecurringFrequency = Literal["WEEKLY", "MONTHLY", "QUARTERLY", "HALF_YEARLY", "YEARLY"]
PaymentFrequency = Literal["WEEKLY", "MONTHLY", "QUARTERLY", "HALF_YEARLY", "YEARLY", "AT_MATURITY"]


class Row(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- F24 households -------------------------------------------------------------------


class HouseholdIn(BaseModel):
    name: Name


class HouseholdOut(BaseModel):
    id: uuid.UUID
    name: str
    role: HouseholdRole
    member_id: uuid.UUID


class MemberIn(BaseModel):
    display_name: Name
    role: HouseholdRole = HouseholdRole.VIEWER
    birth_year: Annotated[int, Field(ge=1900, le=2100)] | None = None
    # An existing account to share the household with (US9).
    email: EmailStr | None = None


class MemberUpdateIn(BaseModel):
    display_name: Name | None = None
    role: HouseholdRole | None = None
    birth_year: Annotated[int, Field(ge=1900, le=2100)] | None = None
    hawl_date: dt.date | None = None
    nisab_basis: NisabBasis | None = None


class MemberOut(Row):
    id: uuid.UUID
    display_name: str
    role: HouseholdRole
    birth_year: int | None
    hawl_date: dt.date | None
    nisab_basis: str | None
    has_login: bool
    is_you: bool


class OwnerIn(BaseModel):
    pct: Annotated[Decimal, Field(gt=0, le=100, decimal_places=4)]
    member_id: uuid.UUID | None = None
    external_name: Name | None = None


class OwnersIn(BaseModel):
    owners: Annotated[list[OwnerIn], Field(max_length=20)]


class OwnerOut(BaseModel):
    pct: Decimal
    member_id: uuid.UUID | None
    external_name: str | None


# --- F12 costs ------------------------------------------------------------------------


class CategoryIn(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=80)]


class CategoryOut(Row):
    id: uuid.UUID
    key: str
    name_en: str
    name_bn: str
    is_default: bool


class ExpenseIn(BaseModel):
    date: dt.date
    amount: PositiveMoney
    category_id: uuid.UUID
    note: Note | None = None
    member_id: uuid.UUID | None = None


class ExpenseUpdateIn(BaseModel):
    date: dt.date | None = None
    amount: PositiveMoney | None = None
    category_id: uuid.UUID | None = None
    note: Note | None = None
    member_id: uuid.UUID | None = None


class ExpenseOut(Row):
    id: uuid.UUID
    date: dt.date
    amount: Decimal
    category_id: uuid.UUID
    note: str | None
    member_id: uuid.UUID | None
    recurring_id: uuid.UUID | None


class RecurringIn(BaseModel):
    category_id: uuid.UUID
    amount: PositiveMoney
    frequency: RecurringFrequency
    start_date: dt.date
    end_date: dt.date | None = None
    note: Note | None = None
    member_id: uuid.UUID | None = None


class RecurringUpdateIn(BaseModel):
    category_id: uuid.UUID | None = None
    amount: PositiveMoney | None = None
    end_date: dt.date | None = None
    note: Note | None = None
    is_active: bool | None = None


class RecurringOut(Row):
    id: uuid.UUID
    category_id: uuid.UUID
    amount: Decimal
    frequency: str
    start_date: dt.date
    end_date: dt.date | None
    note: str | None
    member_id: uuid.UUID | None
    is_active: bool


class CsvIn(BaseModel):
    csv: Annotated[str, Field(min_length=1, max_length=2_000_000)]


class BrokerCsvIn(CsvIn):
    account_id: uuid.UUID


class ImportOut(BaseModel):
    imported: int
    updated: int = 0
    errors: list[dict[str, Any]]


# --- F14 portfolio --------------------------------------------------------------------


class AccountIn(BaseModel):
    type: AccountType
    institution: LongName
    name: Name
    # Stored encrypted; only the last digits are ever shown again (FR23.3).
    number: Annotated[str, Field(max_length=40)] | None = None


class AccountUpdateIn(BaseModel):
    type: AccountType | None = None
    institution: LongName | None = None
    name: Name | None = None
    number: Annotated[str, Field(max_length=40)] | None = None
    is_active: bool | None = None


class AccountOut(Row):
    id: uuid.UUID
    type: str
    institution: str
    name: str
    masked_number: str | None
    is_active: bool


class HoldingIn(BaseModel):
    account_id: uuid.UUID
    instrument_type: InstrumentType
    name: LongName
    ticker: Annotated[str, Field(max_length=20)] | None = None
    product_id: uuid.UUID | None = None
    sukuk_issue_id: uuid.UUID | None = None
    quantity: Units = Decimal(1)
    cost: Money
    manual_value: Money | None = None
    start_date: dt.date | None = None
    maturity_date: dt.date | None = None
    expected_rate: Rate | None = None
    final_rate: Rate | None = None
    payment_frequency: PaymentFrequency | None = None
    profit_received: Money = Decimal(0)
    tax_deducted: Money = Decimal(0)
    is_interest_bearing: bool = False
    owners: Annotated[list[OwnerIn], Field(max_length=20)] | None = None


class HoldingUpdateIn(BaseModel):
    name: LongName | None = None
    quantity: Units | None = None
    cost: Money | None = None
    manual_value: Money | None = None
    start_date: dt.date | None = None
    maturity_date: dt.date | None = None
    expected_rate: Rate | None = None
    final_rate: Rate | None = None
    payment_frequency: PaymentFrequency | None = None
    profit_received: Money | None = None
    tax_deducted: Money | None = None
    is_interest_bearing: bool | None = None
    is_active: bool | None = None


class HoldingOut(Row):
    id: uuid.UUID
    account_id: uuid.UUID
    instrument_type: str
    name: str
    ticker: str | None
    product_id: uuid.UUID | None
    sukuk_issue_id: uuid.UUID | None
    quantity: Decimal
    cost: Decimal
    manual_value: Decimal | None
    start_date: dt.date | None
    maturity_date: dt.date | None
    expected_rate: Decimal | None
    final_rate: Decimal | None
    payment_frequency: str | None
    profit_received: Decimal
    tax_deducted: Decimal
    is_interest_bearing: bool
    is_active: bool


class TransactionIn(BaseModel):
    type: TransactionType
    date: dt.date
    amount: Money
    units: Units | None = None
    note: Note | None = None


class TransactionOut(Row):
    id: uuid.UUID
    date: dt.date
    type: str
    amount: Decimal
    units: Decimal | None
    note: str | None


class LiabilityIn(BaseModel):
    type: LiabilityType
    name: LongName
    lender: LongName | None = None
    outstanding: Money
    due_within_year: Money = Decimal(0)
    is_interest_bearing: bool = False
    end_date: dt.date | None = None
    owners: Annotated[list[OwnerIn], Field(max_length=20)] | None = None


class LiabilityUpdateIn(BaseModel):
    name: LongName | None = None
    lender: LongName | None = None
    outstanding: Money | None = None
    due_within_year: Money | None = None
    is_interest_bearing: bool | None = None
    end_date: dt.date | None = None
    is_active: bool | None = None


class LiabilityOut(Row):
    id: uuid.UUID
    type: str
    name: str
    lender: str | None
    outstanding: Decimal
    due_within_year: Decimal
    is_interest_bearing: bool
    end_date: dt.date | None
    is_active: bool


class PositionOut(BaseModel):
    kind: str
    id: uuid.UUID
    name: str
    type: str
    asset_class: str
    value: Decimal
    household_value: Decimal
    household_pct: Decimal
    cost: Decimal
    method: str
    valued_on: dt.date | None
    account_id: uuid.UUID | None
    institution: str | None
    ticker: str | None
    sector: str | None
    liquidity: str | None
    shariah: str
    quantity: Decimal | None
    owners: list[OwnerOut]


class NetWorthPointOut(Row):
    date: dt.date
    assets: Decimal
    liabilities: Decimal
    net_worth: Decimal
    capital: Decimal | None = None


class TargetIn(BaseModel):
    asset_class: Annotated[str, Field(min_length=1, max_length=40)]
    target_pct: Pct
    band_pct: Annotated[Decimal, Field(ge=0, le=50, decimal_places=4)]


class TargetsIn(BaseModel):
    targets: Annotated[list[TargetIn], Field(max_length=20)]


# --- F25 alternative investments ------------------------------------------------------


class AltAssetIn(BaseModel):
    type: AltAssetType
    name: LongName
    purchase_date: dt.date | None = None
    cost: Money
    current_value: Money | None = None
    counterparty: LongName | None = None
    expected_exit_date: dt.date | None = None
    liquidity: Liquidity
    notes: Annotated[str, Field(max_length=2000)] | None = None
    weight_grams: Units | None = None
    karat: Annotated[int, Field(ge=1, le=24)] | None = None
    revaluation_months: Literal[6, 12] = 12
    shariah_flag: ShariahFlag = ShariahFlag.UNKNOWN
    shariah_reason: Note | None = None
    zakat_rule: Annotated[str, Field(max_length=40)] | None = None
    is_recoverable: bool = True
    due_diligence: dict[str, bool | str] | None = None
    owners: Annotated[list[OwnerIn], Field(max_length=20)] | None = None


class AltAssetUpdateIn(BaseModel):
    name: LongName | None = None
    purchase_date: dt.date | None = None
    cost: Money | None = None
    counterparty: LongName | None = None
    expected_exit_date: dt.date | None = None
    liquidity: Liquidity | None = None
    notes: Annotated[str, Field(max_length=2000)] | None = None
    weight_grams: Units | None = None
    karat: Annotated[int, Field(ge=1, le=24)] | None = None
    revaluation_months: Literal[6, 12] | None = None
    shariah_flag: ShariahFlag | None = None
    shariah_reason: Note | None = None
    zakat_rule: Annotated[str, Field(max_length=40)] | None = None
    is_recoverable: bool | None = None
    due_diligence: dict[str, bool | str] | None = None
    is_active: bool | None = None


class AltAssetOut(Row):
    id: uuid.UUID
    type: str
    name: str
    purchase_date: dt.date | None
    cost: Decimal
    counterparty: str | None
    expected_exit_date: dt.date | None
    liquidity: str
    notes: str | None
    weight_grams: Decimal | None
    karat: int | None
    revaluation_months: int
    shariah_flag: str
    shariah_reason: str | None
    zakat_rule: str | None
    is_recoverable: bool
    due_diligence: dict[str, Any] | None
    is_active: bool


class AltAssetViewOut(AltAssetOut):
    value: Decimal
    household_value: Decimal
    household_pct: Decimal
    value_method: str
    valued_on: dt.date | None
    asset_class: str
    xirr_pct: Decimal | None
    cash_received: Decimal
    revaluation_due: dt.date | None
    owners: list[OwnerOut]


class ValuationIn(BaseModel):
    date: dt.date
    value: Money


class ValuationOut(Row):
    id: uuid.UUID
    date: dt.date
    value: Decimal
    method: str


class CashFlowIn(BaseModel):
    date: dt.date
    # Positive for money received, negative for money put in.
    amount: SignedMoney
    type: CashFlowType
    note: Note | None = None


class CashFlowOut(Row):
    id: uuid.UUID
    date: dt.date
    amount: Decimal
    type: str
    note: str | None


class DocumentIn(BaseModel):
    type: Annotated[str, Field(min_length=1, max_length=40)]
    filename: Annotated[str, Field(min_length=1, max_length=255)]
    # The file, base64-encoded. The size limit is in config/personal.yaml.
    content_base64: Annotated[str, Field(min_length=1, max_length=8_000_000)]


class DocumentOut(Row):
    id: uuid.UUID
    type: str
    filename: str
    size_bytes: int
    created_at: dt.datetime


class AltAssetDetailOut(BaseModel):
    asset: AltAssetViewOut
    valuations: list[ValuationOut]
    cash_flows: list[CashFlowOut]
    documents: list[DocumentOut]


# --- F26 sukuk and Islamic bank products ----------------------------------------------


class IslamicProductOut(Row):
    id: uuid.UUID
    bank: str
    product_type: str
    name: str
    tenor_months: int | None
    expected_rate_pct: Decimal | None
    rate_is_provisional: bool
    min_amount: Decimal | None
    as_of: dt.date


class SukukIssueOut(Row):
    id: uuid.UUID
    code: str
    name: str
    issuer: str
    structure: str
    is_government: bool
    ticker: str | None
    issue_date: dt.date | None
    maturity_date: dt.date | None
    rate_pct: Decimal | None
    payment_frequency: str | None
    min_investment: Decimal | None
    auction_date: dt.date | None
    individual_quota_pct: Decimal | None


class SourceLink(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=200)]
    url: Annotated[str, Field(min_length=8, max_length=500, pattern=r"^https?://")]


class BankFlagIn(BaseModel):
    bank: LongName
    status: BankStatus
    note_en: Annotated[str, Field(min_length=1, max_length=2000)]
    note_bn: Annotated[str, Field(min_length=1, max_length=2000)]
    source_links: Annotated[list[SourceLink], Field(max_length=10)] = []


class BankFlagOut(Row):
    id: uuid.UUID
    bank: str
    status: str
    note_en: str
    note_bn: str
    source_links: list[dict[str, str]]
    updated_at: dt.datetime


# --- F13 Zakat and tax ----------------------------------------------------------------


class ZakatIn(BaseModel):
    member_id: uuid.UUID
    date: dt.date | None = None
    nisab_basis: NisabBasis | None = None
    # Leave out to use the stored gold or silver price for the date (FR13.2).
    price_per_gram: PositiveMoney | None = None
    shares_method: Literal["MARKET_VALUE", "ZAKATABLE_ASSETS"] | None = None


class ZakatSnapshotOut(Row):
    id: uuid.UUID
    member_id: uuid.UUID
    date: dt.date
    nisab_basis: str
    price_per_gram: Decimal
    nisab_value: Decimal
    shares_method: str
    items: list[dict[str, Any]]
    total_zakatable: Decimal
    total_deductions: Decimal
    net_zakatable: Decimal
    zakat_due: Decimal
    config_version: str
    created_at: dt.datetime


class TaxIn(BaseModel):
    member_id: uuid.UUID
    tax_year: Annotated[str, Field(pattern=r"^\d{4}-\d{2}$")]
    # Left out, they are taken from the income records (FR27.5).
    salary_income: Money | None = None
    other_income: Money | None = None


class TaxSnapshotOut(Row):
    id: uuid.UUID
    member_id: uuid.UUID
    tax_year: str
    as_of: dt.date
    items: dict[str, Any]
    created_at: dt.datetime


# --- F17 FIRE, F18 scenarios, F19 goals -----------------------------------------------


class FirePlanIn(BaseModel):
    name: Name
    member_id: uuid.UUID | None = None
    net_worth: SignedMoney
    monthly_savings: Money
    yearly_expenses: PositiveMoney
    nominal_return_pct: Annotated[Decimal, Field(ge=-50, le=100, decimal_places=4)]
    inflation_pct: Annotated[Decimal, Field(ge=-20, le=100, decimal_places=4)]
    withdrawal_rate_pct: Annotated[Decimal, Field(gt=0, le=50, decimal_places=4)]
    current_age: Annotated[int, Field(ge=10, le=99)]
    include_illiquid: bool = False


class FirePlanOut(Row):
    id: uuid.UUID
    member_id: uuid.UUID | None
    name: str
    inputs: dict[str, Any]
    fire_number: Decimal
    fire_age: Decimal | None
    projection: list[dict[str, Any]]
    computed_at: dt.datetime


class ScenarioIn(BaseModel):
    plan_id: uuid.UUID
    preset: Literal[
        "MARKET_CRASH", "EVENT_REPLAY", "EXPENSES_UP", "RETIRE_EARLIER", "INFLATION_SHOCK"
    ]
    params: dict[str, str | int | float] = {}


class ScenarioOut(Row):
    id: uuid.UUID
    fire_plan_id: uuid.UUID
    preset: str
    params: dict[str, Any]
    result: dict[str, Any]
    computed_at: dt.datetime


class FirePlanDetailOut(BaseModel):
    plan: FirePlanOut
    scenarios: list[ScenarioOut]


class EventOut(Row):
    id: uuid.UUID
    slug: str
    type: str
    t0: dt.date
    title_en: str
    title_bn: str


class GoalIn(BaseModel):
    type: GoalType
    name: Name
    member_id: uuid.UUID | None = None
    target_amount: PositiveMoney | None = None
    target_date: dt.date | None = None
    target_age: Annotated[int, Field(ge=18, le=100)] | None = None


class GoalUpdateIn(BaseModel):
    name: Name | None = None
    target_amount: PositiveMoney | None = None
    target_date: dt.date | None = None
    target_age: Annotated[int, Field(ge=18, le=100)] | None = None
    is_active: bool | None = None


class GoalOut(Row):
    id: uuid.UUID
    type: str
    name: str
    member_id: uuid.UUID | None
    target_amount: Decimal | None
    target_date: dt.date | None
    target_age: int | None
    achieved_at: dt.datetime | None
    is_active: bool


class GoalProgressOut(BaseModel):
    goal: GoalOut
    current: Decimal | None
    target: Decimal | None
    progress_pct: Decimal | None
    reached: bool
    on_track: bool | None
    days_left: int | None


# --- F20 alerts -----------------------------------------------------------------------


class AlertRuleIn(BaseModel):
    channel: Channel = Channel.EMAIL
    frequency: AlertFrequency = AlertFrequency.DAILY_DIGEST
    is_active: bool = True
    params: dict[str, str | int | float] | None = None


class AlertRuleOut(Row):
    type: AlertType
    channel: str
    frequency: str
    is_active: bool
    params: dict[str, Any]


class NotificationOut(Row):
    id: uuid.UUID
    type: str
    message_key: str
    data: dict[str, Any]
    link: str | None
    created_at: dt.datetime
    read_at: dt.datetime | None


class NotificationsOut(BaseModel):
    items: list[NotificationOut]
    unread: int


class MarkReadIn(BaseModel):
    id: uuid.UUID | None = None


# --- F27 income records ----------------------------------------------------------------


class IncomeIn(BaseModel):
    date: dt.date
    amount: PositiveMoney
    kind: Annotated[str, Field(min_length=1, max_length=20)]
    note: Note | None = None
    member_id: uuid.UUID | None = None


class IncomeUpdateIn(BaseModel):
    date: dt.date | None = None
    amount: PositiveMoney | None = None
    kind: Annotated[str, Field(min_length=1, max_length=20)] | None = None
    note: Note | None = None
    member_id: uuid.UUID | None = None


class IncomeOut(Row):
    id: uuid.UUID
    date: dt.date
    amount: Decimal
    kind: str
    note: str | None
    member_id: uuid.UUID | None
    recurring_id: uuid.UUID | None


class IncomeRuleIn(BaseModel):
    kind: Annotated[str, Field(min_length=1, max_length=20)]
    amount: PositiveMoney
    frequency: RecurringFrequency
    start_date: dt.date
    end_date: dt.date | None = None
    note: Note | None = None
    member_id: uuid.UUID | None = None


class IncomeRuleUpdateIn(BaseModel):
    kind: Annotated[str, Field(min_length=1, max_length=20)] | None = None
    amount: PositiveMoney | None = None
    end_date: dt.date | None = None
    note: Note | None = None
    is_active: bool | None = None


class IncomeRuleOut(Row):
    id: uuid.UUID
    kind: str
    amount: Decimal
    frequency: str
    start_date: dt.date
    end_date: dt.date | None
    note: str | None
    member_id: uuid.UUID | None
    is_active: bool


# --- D22 guided set-up -------------------------------------------------------------------


class QuickStartIn(BaseModel):
    birth_year: Annotated[int, Field(ge=1900, le=2100)] | None = None
    monthly_income: Money | None = None
    # Default expense category key -> amount for a typical month.
    costs: Annotated[dict[str, Money], Field(max_length=20)] = {}
    # Savings kind from `setup.savings` in config -> amount held today.
    savings: Annotated[dict[str, Money], Field(max_length=10)] = {}
    locale: Literal["en", "bn"] = "en"
