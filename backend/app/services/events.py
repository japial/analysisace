"""Shock event library (FR5.1) and similar events (FR5.3).

Admins curate events. Publishing an event computes its metrics straight away and sends the
FR7.2 alert; unpublished events never appear in public reads.
"""

import datetime as dt
import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event, EventMetric, User
from app.models.enums import EventType
from app.services import market_alerts
from app.services.auth import AuthError, audit
from app.services.email import EmailSender
from app.services.market_analytics import compute_event_metrics, load_market_data

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
EDITABLE = (
    "type",
    "t0",
    "title_en",
    "title_bn",
    "description_en",
    "description_bn",
    "source_links",
)


def list_events(db: Session, *, published_only: bool, type: str | None = None) -> list[Event]:
    statement = select(Event)
    if published_only:
        statement = statement.where(Event.published.is_(True))
    if type:
        statement = statement.where(Event.type == type)
    return list(db.scalars(statement.order_by(Event.t0.desc())))


def get_event(db: Session, key: str, *, published_only: bool) -> Event:
    """Find by slug or id."""
    statement = select(Event)
    try:
        statement = statement.where(Event.id == uuid.UUID(key))
    except ValueError:
        statement = statement.where(Event.slug == key)
    event = db.scalar(statement)
    if event is None or (published_only and not event.published):
        raise AuthError("NOT_FOUND", 404)
    return event


def metrics(db: Session, event_id: uuid.UUID) -> list[EventMetric]:
    return list(
        db.scalars(
            select(EventMetric)
            .where(EventMetric.event_id == event_id)
            .order_by(EventMetric.subject_type, EventMetric.subject)
        )
    )


def similar_events(db: Session, event: Event, limit: int) -> list[Event]:
    """FR5.3: other published events of the same type, newest first."""
    return list(
        db.scalars(
            select(Event)
            .where(Event.type == event.type, Event.published.is_(True), Event.id != event.id)
            .order_by(Event.t0.desc())
            .limit(limit)
        )
    )


def _check(fields: dict[str, Any]) -> None:
    if "type" in fields and fields["type"] not in set(EventType):
        raise AuthError("VALIDATION", 422)
    for link in fields.get("source_links") or []:
        url = str(link.get("url", ""))
        if not url.startswith(("https://", "http://")):
            raise AuthError("VALIDATION", 422)


def create_event(db: Session, actor: User, slug: str, fields: dict[str, Any]) -> Event:
    if not _SLUG.match(slug) or len(slug) > 80:
        raise AuthError("VALIDATION", 422)
    if db.scalar(select(Event.id).where(Event.slug == slug)) is not None:
        raise AuthError("DUPLICATE", 409)
    _check(fields)
    event = Event(slug=slug, published=False, **{k: fields[k] for k in EDITABLE})
    db.add(event)
    db.flush()
    audit(db, str(actor.id), "event.create", "event", str(event.id), after={"slug": slug})
    return event


def update_event(db: Session, actor: User, event: Event, fields: dict[str, Any]) -> Event:
    _check(fields)
    before = {k: str(getattr(event, k)) for k in fields if k in EDITABLE}
    for key, value in fields.items():
        if key in EDITABLE:
            setattr(event, key, value)
    db.flush()
    if event.published and ("t0" in fields):
        compute_event_metrics(db, load_market_data(db), event_ids=[event.id])
    audit(
        db,
        str(actor.id),
        "event.update",
        "event",
        str(event.id),
        before=before,
        after={k: str(v) for k, v in fields.items()},
    )
    return event


def set_published(
    db: Session, actor: User, event: Event, published: bool, sender: EmailSender
) -> Event:
    was = event.published
    event.published = published
    db.flush()
    if published and not was:
        compute_event_metrics(db, load_market_data(db), event_ids=[event.id])
        market_alerts.event_published(db, sender, event)
    audit(
        db,
        str(actor.id),
        "event.publish" if published else "event.unpublish",
        "event",
        str(event.id),
    )
    return event


def delete_event(db: Session, actor: User, event: Event) -> None:
    audit(db, str(actor.id), "event.delete", "event", str(event.id), before={"slug": event.slug})
    db.delete(event)
    db.flush()


def events_on_or_before(db: Session, day: dt.date) -> list[Event]:
    return list(
        db.scalars(
            select(Event)
            .where(Event.published.is_(True), Event.t0 <= day)
            .order_by(Event.t0.desc())
        )
    )
