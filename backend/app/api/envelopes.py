"""Builds the `data`, `as_of`, `sources` envelope for data-derived responses."""

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import as_utc, utcnow
from app.models import Source
from app.schemas.common import Envelope, SourceRef


def source_refs(db: Session, source_ids: Iterable[uuid.UUID | None]) -> list[SourceRef]:
    ids = {i for i in source_ids if i is not None}
    if not ids:
        return []
    rows = db.scalars(select(Source).where(Source.id.in_(ids)).order_by(Source.fetched_at.desc()))
    return [SourceRef.model_validate(row) for row in rows]


def envelope[T](data: T, sources: list[SourceRef]) -> Envelope[T]:
    """For public market data: `as_of` is the fetch time of the newest source."""
    as_of = max((s.fetched_at for s in sources), default=None)
    return Envelope(data=data, as_of=as_of, sources=sources)


def computed[T](db: Session, data: T, source_ids: Iterable[uuid.UUID | None] = ()) -> Envelope[T]:
    """For figures worked out from a household's own entries.

    `sources` lists the market data used (prices, gold price, CPI). `as_of` is the time of
    the computation, because the person's own entries have no fetch time.
    """
    refs = [
        ref.model_copy(update={"fetched_at": as_utc(ref.fetched_at)})
        for ref in source_refs(db, source_ids)
    ]
    return Envelope(data=data, as_of=utcnow(), sources=refs)
