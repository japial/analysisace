"""Admin screens for the market layer (PRD section 10, "Admin (role)").

Each route checks a permission from app/core/permissions.py and every change is audited by
its service.
"""

import datetime as dt
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, select

from app.api.deps import Db, require_permission
from app.core.permissions import Permission
from app.core.trading_calendar import get_trading_calendar
from app.models import (
    BusinessClassification,
    Company,
    CompanyShariahStatus,
    CorporateAction,
    Financials,
    Source,
    User,
)
from app.schemas.common import Page
from app.schemas.market import (
    AuditOut,
    BoardNoteIn,
    ClassificationIn,
    ClassificationOut,
    CorporateActionIn,
    CorporateActionOut,
    CsvLoadOut,
    DataIssueOut,
    DataIssuesOut,
    EventCreateIn,
    EventIn,
    EventOut,
    FinancialsIn,
    FinancialsPage,
    FinancialsPublic,
    IssueStatusIn,
    JobRunOut,
    MacroNoteOut,
    MetalPriceIn,
    NoteEditIn,
    NoteGenerateIn,
    OverrideIn,
    PublishIn,
    SeriesCsvIn,
    ShariahAdminItem,
)
from app.services import admin_review, events, macro_notes, market_alerts, market_data, screening
from app.services.email import get_email_sender
from app.services.market_pipeline import run_market_analytics
from app.services.valuation import today_dhaka

router = APIRouter(prefix="/admin", tags=["admin-market"])

Reviewer = Annotated[User, Depends(require_permission(Permission.DATA_REVIEW))]
Publisher = Annotated[User, Depends(require_permission(Permission.CONTENT_PUBLISH))]
ShariahAdmin = Annotated[User, Depends(require_permission(Permission.SHARIAH_OVERRIDE))]
Auditor = Annotated[User, Depends(require_permission(Permission.AUDIT_VIEW))]
ConfigManager = Annotated[User, Depends(require_permission(Permission.CONFIG_MANAGE))]


# --- data review queue ----------------------------------------------------------------


@router.get("/data-issues")
def list_data_issues(
    _: Reviewer,
    db: Db,
    status: str | None = "OPEN",
    dataset: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DataIssuesOut:
    rows, total, open_counts = admin_review.list_issues(
        db, status=status or None, dataset=dataset, limit=limit, offset=offset
    )
    return DataIssuesOut(
        items=[DataIssueOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
        open_by_dataset=open_counts,
    )


@router.patch("/data-issues/{issue_id}")
def set_data_issue(
    issue_id: uuid.UUID, body: IssueStatusIn, actor: Reviewer, db: Db
) -> DataIssueOut:
    issue = admin_review.set_issue_status(db, actor, issue_id, body.status, body.note)
    db.commit()
    return DataIssueOut.model_validate(issue)


@router.post("/jobs/data-quality/run")
def run_data_quality(_: Reviewer, db: Db) -> dict[str, int]:
    result = market_data.run_quality_checks(db, get_trading_calendar(), today_dhaka())
    db.commit()
    return result


# --- audit log and jobs ---------------------------------------------------------------


@router.get("/audit")
def list_audit(
    _: Auditor,
    db: Db,
    action: Annotated[str | None, Query(max_length=60)] = None,
    entity: Annotated[str | None, Query(max_length=60)] = None,
    actor: Annotated[str | None, Query(max_length=200)] = None,
    since: dt.date | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AuditOut]:
    rows, total = admin_review.list_audit(
        db, action=action, entity=entity, actor=actor, since=since, limit=limit, offset=offset
    )
    return Page[AuditOut](
        items=[AuditOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset
    )


@router.get("/jobs")
def list_jobs(
    _: Auditor, db: Db, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> list[JobRunOut]:
    return [JobRunOut.model_validate(r) for r in admin_review.recent_jobs(db, limit)]


@router.post("/jobs/market-analytics/run")
def run_analytics(_: ConfigManager, db: Db) -> dict[str, Any]:
    """Run the market analytics now instead of waiting for the nightly job."""
    detail = run_market_analytics(db, get_email_sender())
    db.commit()
    return detail


# --- market data entry ----------------------------------------------------------------


@router.post("/metal-prices", status_code=status.HTTP_201_CREATED)
def add_metal_price(body: MetalPriceIn, actor: Reviewer, db: Db) -> dict[str, str]:
    """Q9 default: gold and silver prices per gram are entered by hand each day."""
    row = market_data.add_metal_price(
        db, actor, code=body.code, day=body.date, value=body.value, note=body.note
    )
    db.commit()
    return {"code": row.series_code, "date": row.date.isoformat(), "value": str(row.value)}


@router.post("/series/import")
def import_series(body: SeriesCsvIn, actor: Reviewer, db: Db) -> CsvLoadOut:
    result = market_data.import_series_csv(
        db,
        actor,
        kind=body.kind,
        content=body.content.encode("utf-8"),
        source_name=body.source_name,
        source_url=body.source_url,
    )
    if result.errors:
        db.rollback()
    else:
        db.commit()
    return CsvLoadOut(inserted=result.inserted, updated=result.updated, errors=result.errors[:50])


@router.get("/corporate-actions")
def list_corporate_actions(
    _: Reviewer, db: Db, ticker: Annotated[str | None, Query(max_length=20)] = None
) -> list[CorporateActionOut]:
    statement = select(CorporateAction)
    if ticker:
        statement = statement.where(CorporateAction.ticker == ticker.upper())
    rows = db.scalars(statement.order_by(CorporateAction.ex_date.desc()).limit(200))
    return [CorporateActionOut.model_validate(r) for r in rows]


@router.post("/corporate-actions", status_code=status.HTTP_201_CREATED)
def add_corporate_action(body: CorporateActionIn, actor: Reviewer, db: Db) -> CorporateActionOut:
    row = market_data.add_corporate_action(
        db,
        actor,
        ticker=body.ticker.upper(),
        ex_date=body.ex_date,
        type=body.type,
        ratio=body.ratio,
        amount=body.amount,
        source_name=body.source_name,
        source_url=body.source_url,
    )
    db.commit()
    return CorporateActionOut.model_validate(row)


# --- financials and Shariah administration (F1) ---------------------------------------


def _financials_out(db: Db, rows: list[Financials]) -> list[FinancialsPublic]:
    sources = {
        s.id: s
        for s in db.scalars(select(Source).where(Source.id.in_({r.source_id for r in rows})))
    }
    return [
        FinancialsPublic.model_validate(r).model_copy(
            update={
                "source_name": sources[r.source_id].name if r.source_id in sources else None,
                "source_url": sources[r.source_id].url if r.source_id in sources else None,
            }
        )
        for r in rows
    ]


@router.get("/financials")
def list_financials(
    _: Reviewer,
    db: Db,
    ticker: Annotated[str | None, Query(max_length=20)] = None,
    reviewed: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> FinancialsPage:
    rows, total = screening.list_financials(
        db, ticker=ticker.upper() if ticker else None, reviewed=reviewed, limit=limit, offset=offset
    )
    return FinancialsPage(items=_financials_out(db, rows), total=total, limit=limit, offset=offset)


@router.put("/financials")
def save_financials(body: FinancialsIn, actor: Reviewer, db: Db) -> FinancialsPublic:
    figures = {name: getattr(body, name) for name in screening.FIGURES}
    row = screening.save_financials(
        db,
        actor,
        ticker=body.ticker.upper(),
        period_end=body.period_end,
        period_type=body.period_type,
        figures=figures,
        shares_outstanding=body.shares_outstanding,
        source_name=body.source_name,
        source_url=body.source_url,
        source_page=body.source_page,
    )
    db.commit()
    return _financials_out(db, [row])[0]


@router.post("/financials/{financials_id}/review")
def review_financials(financials_id: uuid.UUID, actor: Reviewer, db: Db) -> FinancialsPublic:
    row = screening.review_financials(db, actor, financials_id)
    # FR1.4: screen as soon as reviewed figures arrive.
    change = screening.screen_company(db, row.ticker, row.reviewed_at or dt.datetime.now(dt.UTC))
    if change is not None and change.from_status:
        market_alerts.status_changed(db, get_email_sender(), change, dt.datetime.now(dt.UTC))
    db.commit()
    return _financials_out(db, [row])[0]


@router.get("/shariah")
def shariah_admin_list(_: ShariahAdmin, db: Db) -> list[ShariahAdminItem]:
    companies = list(
        db.scalars(select(Company).where(Company.is_active.is_(True)).order_by(Company.ticker))
    )
    statuses = {s.ticker: s for s in db.scalars(select(CompanyShariahStatus))}
    classes = {c.ticker: c for c in db.scalars(select(BusinessClassification))}
    pending = dict(
        db.execute(
            select(Financials.ticker, func.count())
            .where(Financials.reviewed_at.is_(None))
            .group_by(Financials.ticker)
        ).all()
    )
    out = []
    for c in companies:
        s = statuses.get(c.ticker)
        cl = classes.get(c.ticker)
        out.append(
            ShariahAdminItem(
                ticker=c.ticker,
                name=c.name,
                sector=c.sector,
                status=screening.effective_status(s) if s else None,
                screen_status=s.status if s else None,
                override_status=s.override_status if s else None,
                override_reason=s.override_reason if s else None,
                board_note=s.board_note if s else None,
                classification=ClassificationOut.model_validate(cl) if cl else None,
                unreviewed_financials=int(pending.get(c.ticker, 0)),
            )
        )
    return out


@router.put("/shariah/{ticker}/classification")
def set_classification(
    ticker: str, body: ClassificationIn, actor: ShariahAdmin, db: Db
) -> ClassificationOut:
    row = screening.set_classification(
        db,
        actor,
        ticker.upper(),
        stage1_pass=body.stage1_pass,
        activity=body.activity,
        reason=body.reason,
    )
    now = dt.datetime.now(dt.UTC)
    change = screening.screen_company(db, row.ticker, now)
    if change is not None and change.from_status:
        market_alerts.status_changed(db, get_email_sender(), change, now)
    db.commit()
    return ClassificationOut.model_validate(row)


@router.put("/shariah/{ticker}/override")
def set_override(
    ticker: str, body: OverrideIn, actor: ShariahAdmin, db: Db
) -> dict[str, str | None]:
    row, change = screening.set_override(db, actor, ticker.upper(), body.status, body.reason)
    if change is not None:
        market_alerts.status_changed(db, get_email_sender(), change, dt.datetime.now(dt.UTC))
    db.commit()
    return {"status": screening.effective_status(row), "override_status": row.override_status}


@router.put("/shariah/{ticker}/board-note")
def set_board_note(
    ticker: str, body: BoardNoteIn, actor: ShariahAdmin, db: Db
) -> dict[str, str | None]:
    row = screening.set_board_note(db, actor, ticker.upper(), body.note)
    db.commit()
    return {"board_note": row.board_note}


# --- events (FR5.1) -------------------------------------------------------------------


def _event_fields(body: EventIn) -> dict[str, Any]:
    data = body.model_dump()
    data["source_links"] = [link.model_dump() for link in body.source_links]
    data["type"] = body.type.value
    return data


@router.get("/events")
def admin_events(_: Publisher, db: Db) -> list[EventOut]:
    return [EventOut.model_validate(e) for e in events.list_events(db, published_only=False)]


@router.post("/events", status_code=status.HTTP_201_CREATED)
def create_event(body: EventCreateIn, actor: Publisher, db: Db) -> EventOut:
    fields = _event_fields(body)
    slug = fields.pop("slug")
    event = events.create_event(db, actor, slug, fields)
    db.commit()
    return EventOut.model_validate(event)


@router.patch("/events/{event_id}")
def update_event(event_id: uuid.UUID, body: EventIn, actor: Publisher, db: Db) -> EventOut:
    event = events.get_event(db, str(event_id), published_only=False)
    events.update_event(db, actor, event, _event_fields(body))
    db.commit()
    return EventOut.model_validate(event)


@router.post("/events/{event_id}/publish")
def publish_event(event_id: uuid.UUID, body: PublishIn, actor: Publisher, db: Db) -> EventOut:
    event = events.get_event(db, str(event_id), published_only=False)
    events.set_published(db, actor, event, body.published, get_email_sender())
    db.commit()
    return EventOut.model_validate(event)


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: uuid.UUID, actor: Publisher, db: Db) -> Response:
    event = events.get_event(db, str(event_id), published_only=False)
    events.delete_event(db, actor, event)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- macro notes (FR4) ----------------------------------------------------------------


@router.get("/notes")
def admin_notes(_: Publisher, db: Db) -> list[MacroNoteOut]:
    return [
        MacroNoteOut.model_validate(n)
        for n in macro_notes.list_notes(db, published_only=False)[:60]
    ]


@router.post("/notes/generate")
def generate_notes(body: NoteGenerateIn, _: Publisher, db: Db) -> list[MacroNoteOut]:
    notes = macro_notes.generate_draft(db, body.week_start, replace_draft=body.replace_draft)
    db.commit()
    return [MacroNoteOut.model_validate(n) for n in notes]


@router.patch("/notes/{note_id}")
def edit_note(note_id: uuid.UUID, body: NoteEditIn, actor: Publisher, db: Db) -> MacroNoteOut:
    note = macro_notes.get_note_by_id(db, note_id)
    macro_notes.edit_note(db, actor, note, title=body.title, body=body.body)
    db.commit()
    return MacroNoteOut.model_validate(note)


@router.post("/notes/{note_id}/publish")
def publish_note(note_id: uuid.UUID, body: PublishIn, actor: Publisher, db: Db) -> MacroNoteOut:
    note = macro_notes.get_note_by_id(db, note_id)
    macro_notes.set_published(db, actor, note, body.published)
    db.commit()
    return MacroNoteOut.model_validate(note)
