"""Adapter interfaces for data sources (PRD section 0, rule 7).

Each source sits behind one of these protocols so it can be replaced by a licensed feed
without touching the ingestion services. An adapter only fetches and parses; it never
writes to the database.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class SourceInfo:
    """Where a batch came from. Stored as a `source` row for traceability."""

    name: str
    url: str | None
    fetched_at: datetime
    checksum: str | None = None


@dataclass(frozen=True)
class PriceBar:
    ticker: str
    date: date
    close: Decimal | None
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    volume: int | None = None


@dataclass(frozen=True)
class EodPriceBatch:
    source: SourceInfo
    day: date
    bars: list[PriceBar]


class EodPriceAdapter(Protocol):
    name: str

    def fetch(self, day: date) -> EodPriceBatch | None:
        """Return the day's prices, or None if the source has nothing for that day yet."""
        ...
