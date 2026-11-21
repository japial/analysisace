"""Request and response models for the market layer (F1 to F8) and its admin screens."""

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EventType, PeriodType, ShariahStatus
from app.models.market import CorporateActionType


class _Orm(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- series ---------------------------------------------------------------------------


class SeriesPoint(BaseModel):
    date: dt.date
    value: Decimal


class SeriesOut(BaseModel):
    code: str
    points: list[SeriesPoint]


class SeriesCodesOut(BaseModel):
    indices: list[str]
    macro: list[str]


# --- F1 Shariah -----------------------------------------------------------------------


class ShariahResultOut(_Orm):
    id: uuid.UUID
    period_end: dt.date
    method: str
    method_version: str
    status: str
    ratios: list[dict[str, Any]]
    reasons: list[str]
    screened_at: dt.datetime


class FinancialsOut(_Orm):
    id: uuid.UUID
    ticker: str
    period_end: dt.date
    period_type: str
    total_debt_interest_bearing: Decimal | None
    cash_and_interest_securities: Decimal | None
    receivables: Decimal | None
    total_revenue: Decimal | None
    non_permissible_income: Decimal | None
    zakatable_assets: Decimal | None
    shares_outstanding: int | None
    source_id: uuid.UUID
    source_page: int | None
    reviewed_at: dt.datetime | None


class FinancialsPublic(FinancialsOut):
    source_name: str | None = None
    source_url: str | None = None


class StatusChangeOut(_Orm):
    from_status: str | None
    to_status: str
    cause: str
    changed_at: dt.datetime


class ClassificationOut(_Orm):
    stage1_pass: bool
    activity: str | None
    reason: str
    method_version: str


class CompanyShariahOut(BaseModel):
    ticker: str
    status: str
    screen_status: str
    method: str
    method_version: str
    screened_at: dt.datetime
    override_status: str | None
    override_reason: str | None
    board_note: str | None
    non_permissible_income_ratio: Decimal | None
    classification: ClassificationOut | None
    # Newest period's result for every method (FR1.2: both methods shown).
    results: list[ShariahResultOut]
    financials: FinancialsPublic | None
    history: list[StatusChangeOut]
    config_approved: bool


class ShariahListItem(BaseModel):
    ticker: str
    name: str
    sector: str | None
    status: str
    method_version: str
    screened_at: dt.datetime
    market_cap: Decimal | None
    overridden: bool


class BasketOut(BaseModel):
    years: int
    start: dt.date | None
    members: list[str]
    series: dict[str, list[SeriesPoint]]


# --- F3 scores ------------------------------------------------------------------------


class ScoreOut(_Orm):
    subject_type: str
    subject: str
    score_type: str
    value: Decimal | None
    std_error: Decimal | None
    t_stat: Decimal | None
    confidence: str
    n_obs: int
    sample_start: dt.date | None
    sample_end: dt.date | None
    computed_at: dt.datetime


class AuctionOut(BaseModel):
    code: str
    date: dt.date
    value: Decimal


class RatesOverviewOut(BaseModel):
    latest_auctions: list[AuctionOut]
    yield_trend: list[SeriesPoint]
    sectors: list[ScoreOut]


# --- F5 events ------------------------------------------------------------------------


class SourceLink(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=8, max_length=500)


class EventOut(_Orm):
    id: uuid.UUID
    slug: str
    type: str
    t0: dt.date
    title_en: str
    title_bn: str
    description_en: str
    description_bn: str
    source_links: list[dict[str, str]]
    published: bool


class EventMetricOut(_Orm):
    subject_type: str
    subject: str
    ret_1: Decimal | None
    ret_5: Decimal | None
    ret_20: Decimal | None
    max_dd_60: Decimal | None
    sessions_to_recover: int | None
    computed_at: dt.datetime


class EventDetailOut(BaseModel):
    event: EventOut
    metrics: list[EventMetricOut]
    similar: list[EventOut]


class CompanyEventOut(BaseModel):
    event: EventOut
    metric: EventMetricOut


class EventIn(BaseModel):
    type: EventType
    t0: dt.date
    title_en: str = Field(min_length=1, max_length=200)
    title_bn: str = Field(min_length=1, max_length=200)
    description_en: str = Field(min_length=1, max_length=5000)
    description_bn: str = Field(min_length=1, max_length=5000)
    source_links: list[SourceLink] = Field(default_factory=list, max_length=10)


class EventCreateIn(EventIn):
    slug: str = Field(min_length=3, max_length=80)


class PublishIn(BaseModel):
    published: bool


# --- F4 macro notes -------------------------------------------------------------------


class MacroNoteOut(_Orm):
    id: uuid.UUID
    week_start: dt.date
    locale: str
    status: str
    title: str
    body: str
    figures: list[dict[str, Any]]
    published_at: dt.datetime | None


class MacroNoteSummary(_Orm):
    id: uuid.UUID
    week_start: dt.date
    locale: str
    status: str
    title: str
    published_at: dt.datetime | None


class NoteEditIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20000)


class NoteGenerateIn(BaseModel):
    week_start: dt.date
    replace_draft: bool = False


# --- F8 regime ------------------------------------------------------------------------


class RegimeMonthOut(_Orm):
    month: dt.date
    label: str
    components: dict[str, Any]
    config_version: str


class RegimeSectorOut(_Orm):
    sector: str
    avg_monthly_return: Decimal
    hit_rate: Decimal
    n_months: int


class RegimeOut(BaseModel):
    current: RegimeMonthOut | None
    history: list[RegimeMonthOut]
    sectors: list[RegimeSectorOut]
    min_months: int


# --- watchlist ------------------------------------------------------------------------


class WatchItem(BaseModel):
    ticker: str
    name: str
    status: str | None


# --- admin ----------------------------------------------------------------------------


class DataIssueOut(_Orm):
    id: uuid.UUID
    check_name: str
    dataset: str
    entity: str | None
    date: dt.date | None
    detail: str
    status: str
    resolved_by: str | None
    resolved_at: dt.datetime | None
    created_at: dt.datetime


class DataIssuesOut(BaseModel):
    items: list[DataIssueOut]
    total: int
    limit: int
    offset: int
    open_by_dataset: dict[str, int]


class IssueStatusIn(BaseModel):
    status: Literal["OPEN", "RESOLVED", "IGNORED"]
    note: str | None = Field(default=None, max_length=500)


class AuditOut(_Orm):
    id: uuid.UUID
    actor: str
    action: str
    entity: str
    entity_id: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    at: dt.datetime


class JobRunOut(_Orm):
    id: uuid.UUID
    job: str
    started_at: dt.datetime
    finished_at: dt.datetime | None
    status: str
    detail: dict[str, Any] | None


class MetalPriceIn(BaseModel):
    code: str = Field(max_length=40)
    date: dt.date
    value: Decimal = Field(gt=0, max_digits=14, decimal_places=4)
    note: str | None = Field(default=None, max_length=300)


class SeriesCsvIn(BaseModel):
    kind: Literal["index", "macro"]
    content: str = Field(min_length=1, max_length=5_000_000)
    source_name: str = Field(min_length=1, max_length=200)
    source_url: str | None = Field(default=None, max_length=500)


class CsvLoadOut(BaseModel):
    inserted: int
    updated: int
    errors: list[str]


class CorporateActionIn(BaseModel):
    ticker: str = Field(max_length=20)
    ex_date: dt.date
    type: CorporateActionType
    ratio: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=8)
    amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    source_name: str = Field(min_length=1, max_length=200)
    source_url: str | None = Field(default=None, max_length=500)


class CorporateActionOut(_Orm):
    id: uuid.UUID
    ticker: str
    ex_date: dt.date
    type: str
    ratio: Decimal | None
    amount: Decimal | None


class FinancialsIn(BaseModel):
    ticker: str = Field(max_length=20)
    period_end: dt.date
    period_type: PeriodType
    total_debt_interest_bearing: Decimal | None = Field(
        default=None, ge=0, max_digits=20, decimal_places=2
    )
    cash_and_interest_securities: Decimal | None = Field(
        default=None, ge=0, max_digits=20, decimal_places=2
    )
    receivables: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    total_revenue: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    non_permissible_income: Decimal | None = Field(
        default=None, ge=0, max_digits=20, decimal_places=2
    )
    zakatable_assets: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    shares_outstanding: int | None = Field(default=None, gt=0)
    source_name: str = Field(min_length=1, max_length=200)
    source_url: str | None = Field(default=None, max_length=500)
    source_page: int | None = Field(default=None, ge=1, le=10000)


class FinancialsPage(BaseModel):
    items: list[FinancialsPublic]
    total: int
    limit: int
    offset: int


class ClassificationIn(BaseModel):
    stage1_pass: bool
    activity: str | None = Field(default=None, max_length=60)
    reason: str = Field(min_length=1, max_length=2000)


class OverrideIn(BaseModel):
    status: ShariahStatus | None
    reason: str = Field(min_length=1, max_length=2000)


class BoardNoteIn(BaseModel):
    note: str | None = Field(default=None, max_length=5000)


class ShariahAdminItem(BaseModel):
    ticker: str
    name: str
    sector: str | None
    status: str | None
    screen_status: str | None
    override_status: str | None
    override_reason: str | None
    board_note: str | None
    classification: ClassificationOut | None
    unreviewed_financials: int
