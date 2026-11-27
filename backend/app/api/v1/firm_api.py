"""Read-only data API for firms (FR9.2, D30), authenticated with an `X-API-Key` header.

Each key has its own per-minute limit and every call is counted per key, endpoint and day.
Answers carry `as_of` and `sources` like the rest of the API. Off (404) while
FIRM_FEATURES_ENABLED is off (TODO(owner): Q4). History only: nothing here is a signal.
"""

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select

from app.api.deps import Db
from app.api.v1.market import derived
from app.core.config import Settings, get_settings
from app.models import ApiKey, Firm, MacroNote, MacroSeries, Source
from app.schemas.common import Envelope
from app.services import firms
from app.services.auth import AuthError


def _enabled(settings: Annotated[Settings, Depends(get_settings)]) -> None:
    firms.require_enabled(settings)


router = APIRouter(prefix="/firm-api", tags=["firm API"], dependencies=[Depends(_enabled)])


def _caller(
    db: Db, x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None
) -> tuple[ApiKey, Firm]:
    return firms.authenticate_key(db, x_api_key)


Caller = Annotated[tuple[ApiKey, Firm], Depends(_caller)]


def _count(db: Db, caller: tuple[ApiKey, Firm], endpoint: str) -> None:
    firms.record_call(db, caller[0], endpoint)
    db.commit()


@router.get("/shariah")
def shariah(caller: Caller, db: Db) -> Envelope[list[dict[str, Any]]]:
    """analysisACE's own Shariah screen for every listed company (FR2.1). Never the DSE's
    licensed constituent list."""
    _count(db, caller, "shariah")
    rows, newest, sources = firms.shariah_rows(db)
    return derived(db, rows, newest, sources)


@router.get("/scores")
def scores(caller: Caller, db: Db) -> Envelope[list[dict[str, Any]]]:
    """Rate sensitivity per stock (FR3): the typical weekly move per 1-point rise in the
    91-day T-bill yield, with its confidence. History, not a forecast."""
    _count(db, caller, "scores")
    rows, computed = firms.score_rows(db)
    source = db.scalar(
        select(MacroSeries.source_id)
        .where(MacroSeries.series_code == "TBILL_91D")
        .order_by(MacroSeries.date.desc())
        .limit(1)
    )
    return derived(db, rows, computed, {source})


@router.get("/macro-notes/latest")
def latest_note(
    caller: Caller, db: Db, locale: Literal["en", "bn"] = "en"
) -> Envelope[dict[str, Any]]:
    """The newest published weekly macro note (FR4) with its figures."""
    _count(db, caller, "macro-notes")
    note = db.scalar(
        select(MacroNote)
        .where(MacroNote.status == "PUBLISHED", MacroNote.locale == locale)
        .order_by(MacroNote.week_start.desc())
        .limit(1)
    )
    if note is None:
        raise AuthError("NOTE_NOT_PUBLISHED", 404)
    ids: set[uuid.UUID] = set()
    for fig in note.figures:
        try:
            ids.add(uuid.UUID(str(fig.get("source_id"))))
        except ValueError:
            continue
    known = set(db.scalars(select(Source.id).where(Source.id.in_(ids)))) if ids else set()
    data = {
        "week_start": note.week_start,
        "locale": note.locale,
        "title": note.title,
        "body": note.body,
        "figures": note.figures,
    }
    return derived(db, data, note.published_at, known)
