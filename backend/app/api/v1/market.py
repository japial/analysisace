"""Public market endpoints (PRD section 10): Shariah screen and list (F1, F2), scores (F3),
index and macro series, weekly notes (F4), events (F5) and the regime (F8).

Routes only read stored rows. Computed results carry `as_of` = their computation time and
`sources` = the newest source rows behind their inputs.
"""

import datetime as dt
import uuid
from collections.abc import Iterable
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.analytics.basket import rebase
from app.api.deps import Db
from app.api.envelopes import envelope, source_refs
from app.core.app_config import get_config
from app.core.security import as_utc
from app.models import (
    BusinessClassification,
    Company,
    CompanyShariahStatus,
    EventMetric,
    Financials,
    IndexDaily,
    MacroSeries,
    PriceDaily,
    RegimeMonth,
    RegimeSectorStat,
    Score,
    ShariahResult,
    ShariahStatusChange,
    Source,
)
from app.models.enums import ScoreType, SubjectType
from app.schemas.common import Envelope, Page
from app.schemas.market import (
    AuctionOut,
    BasketOut,
    ClassificationOut,
    CompanyEventOut,
    CompanyShariahOut,
    EventDetailOut,
    EventMetricOut,
    EventOut,
    FinancialsPublic,
    MacroNoteOut,
    MacroNoteSummary,
    RatesOverviewOut,
    RegimeMonthOut,
    RegimeOut,
    RegimeSectorOut,
    ScoreOut,
    SeriesCodesOut,
    SeriesOut,
    SeriesPoint,
    ShariahListItem,
    ShariahResultOut,
    StatusChangeOut,
)
from app.services import events as event_service
from app.services import macro_notes, market_data, screening
from app.services.market_analytics import basket_members

router = APIRouter(tags=["market"])


def derived[T](
    db: Session, data: T, computed_at: dt.datetime | None, source_ids: Iterable[uuid.UUID | None]
) -> Envelope[T]:
    """Envelope for a computed result: `as_of` is when it was computed."""
    refs = [
        r.model_copy(update={"fetched_at": as_utc(r.fetched_at)})
        for r in source_refs(db, source_ids)
    ]
    return Envelope(data=data, as_of=as_utc(computed_at) if computed_at else None, sources=refs)


def _latest_source(
    db: Session,
    model: type[PriceDaily] | type[IndexDaily] | type[MacroSeries],
    *where: ColumnElement[bool],
) -> uuid.UUID | None:
    return db.scalar(select(model.source_id).where(*where).order_by(model.date.desc()).limit(1))


def _company(db: Session, ticker: str) -> Company:
    company = db.scalar(select(Company).where(Company.ticker == ticker.upper()))
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


# --- series ---------------------------------------------------------------------------


@router.get("/indices/{code}/series")
def index_series(
    code: str,
    db: Db,
    start: dt.date | None = None,
    end: dt.date | None = None,
) -> Envelope[SeriesOut]:
    rows = market_data.index_series(db, code.upper(), start, end)
    if not rows:
        raise HTTPException(status_code=404, detail="No data for this index")
    data = SeriesOut(
        code=code.upper(), points=[SeriesPoint(date=r.date, value=r.close) for r in rows]
    )
    return envelope(data, source_refs(db, {r.source_id for r in rows}))


@router.get("/macro/series")
def macro_codes(db: Db) -> SeriesCodesOut:
    return SeriesCodesOut(**market_data.series_codes(db))


@router.get("/macro/series/{code}")
def macro_series(
    code: str, db: Db, start: dt.date | None = None, end: dt.date | None = None
) -> Envelope[SeriesOut]:
    rows = market_data.macro_series(db, code.upper(), start, end)
    if not rows:
        raise HTTPException(status_code=404, detail="No data for this series")
    data = SeriesOut(
        code=code.upper(), points=[SeriesPoint(date=r.date, value=r.value) for r in rows]
    )
    return envelope(data, source_refs(db, {r.source_id for r in rows}))


# --- F1 Shariah screen ----------------------------------------------------------------


@router.get("/companies/{ticker}/shariah")
def company_shariah(ticker: str, db: Db) -> Envelope[CompanyShariahOut]:
    company = _company(db, ticker)
    status = db.scalar(
        select(CompanyShariahStatus).where(CompanyShariahStatus.ticker == company.ticker)
    )
    if status is None:
        raise HTTPException(status_code=404, detail="Not screened yet")
    results: list[ShariahResult] = []
    fin: Financials | None = None
    if status.result_id is not None:
        current = db.get(ShariahResult, status.result_id)
        if current is not None:
            results = list(
                db.scalars(
                    select(ShariahResult)
                    .where(
                        ShariahResult.ticker == company.ticker,
                        ShariahResult.period_end == current.period_end,
                        ShariahResult.method_version == current.method_version,
                    )
                    .order_by(ShariahResult.method)
                )
            )
            fin = db.get(Financials, current.financials_id) if current.financials_id else None
    classification = db.scalar(
        select(BusinessClassification).where(BusinessClassification.ticker == company.ticker)
    )
    history = db.scalars(
        select(ShariahStatusChange)
        .where(ShariahStatusChange.ticker == company.ticker)
        .order_by(ShariahStatusChange.changed_at.desc())
        .limit(50)
    )
    fin_out = None
    if fin is not None:
        source = db.get(Source, fin.source_id)
        fin_out = FinancialsPublic.model_validate(fin).model_copy(
            update={
                "source_name": source.name if source else None,
                "source_url": source.url if source else None,
            }
        )
    data = CompanyShariahOut(
        ticker=company.ticker,
        status=screening.effective_status(status),
        screen_status=status.status,
        method=status.method,
        method_version=status.method_version,
        screened_at=status.screened_at,
        override_status=status.override_status,
        override_reason=status.override_reason,
        board_note=status.board_note,
        non_permissible_income_ratio=status.non_permissible_income_ratio,
        classification=ClassificationOut.model_validate(classification) if classification else None,
        results=[ShariahResultOut.model_validate(r) for r in results],
        financials=fin_out,
        history=[StatusChangeOut.model_validate(h) for h in history],
        config_approved=get_config("shariah").data.get("approved_by") is not None,
    )
    price_source = _latest_source(db, PriceDaily, PriceDaily.ticker == company.ticker)
    return derived(db, data, status.screened_at, {fin.source_id if fin else None, price_source})


@router.get("/shariah/list")
def shariah_list(
    db: Db,
    status: str | None = None,
    sector: str | None = None,
    q: Annotated[str | None, Query(max_length=50)] = None,
    sort: Literal["ticker", "status", "sector", "market_cap", "screened_at"] = "ticker",
    order: Literal["asc", "desc"] = "asc",
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Envelope[Page[ShariahListItem]]:
    """FR2.1: screened companies with filters and sorting. Sorting is done here because the
    list is small (hundreds of companies) and market cap is derived."""
    rows = db.execute(
        select(Company, CompanyShariahStatus)
        .join(CompanyShariahStatus, CompanyShariahStatus.ticker == Company.ticker)
        .where(Company.is_active.is_(True))
    ).all()
    caps = screening.latest_market_caps(db, [c.ticker for c, _ in rows])
    items = [
        ShariahListItem(
            ticker=c.ticker,
            name=c.name,
            sector=c.sector,
            status=screening.effective_status(s),
            method_version=s.method_version,
            screened_at=s.screened_at,
            market_cap=caps[c.ticker][0] if c.ticker in caps else None,
            overridden=s.override_status is not None,
        )
        for c, s in rows
    ]
    if status:
        items = [i for i in items if i.status == status]
    if sector:
        items = [i for i in items if i.sector == sector]
    if q:
        needle = q.strip().lower()
        items = [i for i in items if needle in i.ticker.lower() or needle in i.name.lower()]

    def key(item: ShariahListItem) -> tuple[bool, object]:
        value = getattr(item, sort)
        return (value is None, value if value is not None else "")

    items.sort(key=lambda i: i.ticker)
    items.sort(key=key, reverse=order == "desc")
    page = Page[ShariahListItem](
        items=items[offset : offset + limit], total=len(items), limit=limit, offset=offset
    )
    newest = max((s.screened_at for _, s in rows), default=None)
    return derived(db, page, newest, {sid for _, sid in caps.values()})


@router.get("/shariah/basket")
def shariah_basket(db: Db, years: Annotated[int, Query(ge=1, le=10)] = 1) -> Envelope[BasketOut]:
    """FR2.2: the equal-weight basket against DSES and DSEX, rebased to 100."""
    cfg = get_config("market").data["basket"]
    codes = [cfg["code"], *cfg["compare_indices"]]
    newest = db.scalar(
        select(func.max(IndexDaily.date)).where(IndexDaily.index_code == cfg["code"])
    )
    series: dict[str, list[SeriesPoint]] = {}
    source_ids: set[uuid.UUID] = set()
    start = None
    if newest is not None:
        start = dt.date(newest.year - years, newest.month, min(newest.day, 28))
        for code in codes:
            rows = market_data.index_series(db, code, start - dt.timedelta(days=10))
            source_ids |= {r.source_id for r in rows[-1:]}
            first = next((r.date for r in rows if r.date >= start), None)
            if first is None:
                continue
            series[code] = [
                SeriesPoint(date=d, value=v)
                for d, v in rebase([(r.date, r.close) for r in rows], first)
            ]
    computed = db.scalar(
        select(Source.fetched_at)
        .join(IndexDaily, IndexDaily.source_id == Source.id)
        .where(IndexDaily.index_code == cfg["code"])
        .limit(1)
    )
    data = BasketOut(years=years, start=start, members=basket_members(db), series=series)
    return derived(db, data, computed, source_ids)


# --- F3 scores ------------------------------------------------------------------------


@router.get("/companies/{ticker}/scores")
def company_scores(ticker: str, db: Db) -> Envelope[list[ScoreOut]]:
    company = _company(db, ticker)
    rows = list(
        db.scalars(
            select(Score)
            .where(
                (
                    (Score.subject_type == SubjectType.TICKER.value)
                    & (Score.subject == company.ticker)
                )
                | (
                    (Score.subject_type == SubjectType.SECTOR.value)
                    & (Score.subject == (company.sector or ""))
                )
            )
            .order_by(Score.subject_type.desc(), Score.score_type)
        )
    )
    cfg = get_config("market").data["rate_sensitivity"]
    sources = {
        _latest_source(db, PriceDaily, PriceDaily.ticker == company.ticker),
        _latest_source(db, MacroSeries, MacroSeries.series_code == cfg["yield_series"]),
        _latest_source(db, IndexDaily, IndexDaily.index_code == cfg["market_index"]),
    }
    computed = max((r.computed_at for r in rows), default=None)
    return derived(db, [ScoreOut.model_validate(r) for r in rows], computed, sources)


@router.get("/rates/overview")
def rates_overview(db: Db) -> Envelope[RatesOverviewOut]:
    """FR3.5: latest auction yields, the 12-month 91-day yield trend and sector scores."""
    cfg = get_config("market").data["rate_sensitivity"]
    auctions: list[AuctionOut] = []
    source_ids: set[uuid.UUID | None] = set()
    for code in ("TBILL_91D", "TBILL_182D", "TBILL_364D"):
        row = db.scalar(
            select(MacroSeries)
            .where(MacroSeries.series_code == code)
            .order_by(MacroSeries.date.desc())
            .limit(1)
        )
        if row is not None:
            auctions.append(AuctionOut(code=code, date=row.date, value=row.value))
            source_ids.add(row.source_id)
    trend: list[SeriesPoint] = []
    if auctions:
        newest = auctions[0].date
        rows = market_data.macro_series(db, cfg["yield_series"], newest - dt.timedelta(days=365))
        trend = [SeriesPoint(date=r.date, value=r.value) for r in rows]
    sectors = list(
        db.scalars(
            select(Score)
            .where(Score.subject_type == SubjectType.SECTOR.value)
            .order_by(Score.score_type, Score.value)
        )
    )
    computed = max((s.computed_at for s in sectors), default=None)
    data = RatesOverviewOut(
        latest_auctions=auctions,
        yield_trend=trend,
        sectors=[ScoreOut.model_validate(s) for s in sectors],
    )
    return derived(db, data, computed, source_ids)


@router.get("/scores")
def list_scores(
    db: Db,
    subject_type: SubjectType = SubjectType.TICKER,
    score_type: ScoreType = ScoreType.RATE_SENSITIVITY,
) -> Envelope[list[ScoreOut]]:
    rows = list(
        db.scalars(
            select(Score)
            .where(Score.subject_type == subject_type.value, Score.score_type == score_type.value)
            .order_by(Score.subject)
        )
    )
    computed = max((r.computed_at for r in rows), default=None)
    source = _latest_source(db, MacroSeries, MacroSeries.series_code == "TBILL_91D")
    return derived(db, [ScoreOut.model_validate(r) for r in rows], computed, {source})


# --- F4 notes -------------------------------------------------------------------------


@router.get("/macro/notes")
def list_notes(db: Db, locale: Literal["en", "bn"] = "en") -> list[MacroNoteSummary]:
    return [
        MacroNoteSummary.model_validate(n)
        for n in macro_notes.list_notes(db, published_only=True, locale=locale)
    ]


@router.get("/macro/notes/{week}")
def get_note(week: dt.date, db: Db, locale: Literal["en", "bn"] = "en") -> Envelope[MacroNoteOut]:
    note = macro_notes.get_note(db, week, locale, published_only=True)
    ids = set()
    for fig in note.figures:
        try:
            ids.add(uuid.UUID(str(fig.get("source_id"))))
        except ValueError:
            continue
    return derived(db, MacroNoteOut.model_validate(note), note.published_at, ids)


# --- F5 events ------------------------------------------------------------------------


@router.get("/events")
def list_events(db: Db, type: str | None = None) -> list[EventOut]:
    return [
        EventOut.model_validate(e)
        for e in event_service.list_events(db, published_only=True, type=type)
    ]


@router.get("/events/{key}")
def get_event(key: str, db: Db) -> Envelope[EventDetailOut]:
    event = event_service.get_event(db, key, published_only=True)
    metrics = event_service.metrics(db, event.id)
    limit = int(get_config("market").data["events"]["similar_events_limit"])
    data = EventDetailOut(
        event=EventOut.model_validate(event),
        metrics=[EventMetricOut.model_validate(m) for m in metrics],
        similar=[
            EventOut.model_validate(e) for e in event_service.similar_events(db, event, limit)
        ],
    )
    computed = max((m.computed_at for m in metrics), default=None)
    source = _latest_source(db, IndexDaily, IndexDaily.index_code == "DSEX")
    return derived(db, data, computed, {source})


@router.get("/companies/{ticker}/events")
def company_events(ticker: str, db: Db) -> Envelope[list[CompanyEventOut]]:
    """How this stock behaved around each published event (FR5.2, per stock)."""
    company = _company(db, ticker)
    rows = db.execute(
        select(EventMetric).where(
            EventMetric.subject_type == SubjectType.TICKER.value,
            EventMetric.subject == company.ticker,
        )
    ).scalars()
    by_event = {m.event_id: m for m in rows}
    out = [
        CompanyEventOut(
            event=EventOut.model_validate(e), metric=EventMetricOut.model_validate(by_event[e.id])
        )
        for e in event_service.list_events(db, published_only=True)
        if e.id in by_event
    ]
    computed = max((m.computed_at for m in by_event.values()), default=None)
    source = _latest_source(db, PriceDaily, PriceDaily.ticker == company.ticker)
    return derived(db, out, computed, {source})


# --- F8 regime ------------------------------------------------------------------------


@router.get("/regime")
def regime(db: Db, months: Annotated[int, Query(ge=1, le=120)] = 24) -> Envelope[RegimeOut]:
    history = list(db.scalars(select(RegimeMonth).order_by(RegimeMonth.month.desc()).limit(months)))
    current = history[0] if history else None
    sectors: list[RegimeSectorStat] = []
    if current is not None:
        sectors = list(
            db.scalars(
                select(RegimeSectorStat)
                .where(RegimeSectorStat.label == current.label)
                .order_by(RegimeSectorStat.avg_monthly_return.desc())
            )
        )
    cfg = get_config("regime").data
    data = RegimeOut(
        current=RegimeMonthOut.model_validate(current) if current else None,
        history=[RegimeMonthOut.model_validate(h) for h in history],
        sectors=[RegimeSectorOut.model_validate(s) for s in sectors],
        min_months=int(cfg.get("min_months_for_sector_stats", 3)),
    )
    computed = max((s.computed_at for s in sectors), default=None) or (
        current.updated_at if current else None
    )
    source_ids = {
        _latest_source(db, MacroSeries, MacroSeries.series_code == cfg["rate_trend"]["series"]),
        _latest_source(db, MacroSeries, MacroSeries.series_code == cfg["oil_shock"]["series"]),
    }
    return derived(db, data, computed, source_ids)
