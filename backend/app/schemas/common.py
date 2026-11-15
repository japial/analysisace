"""Response envelope shared by every data-derived endpoint.

PRD section 10: all data-derived responses include `as_of` and `sources`, so any number
shown to a user can be traced to a source record and a time.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SourceRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    url: str | None
    fetched_at: datetime


class Envelope[T](BaseModel):
    data: T
    # Time of the newest source behind `data`. None when there is no data yet.
    as_of: datetime | None
    sources: list[SourceRef]


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int
