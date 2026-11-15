"""Stores one day of end-of-day prices from any `EodPriceAdapter`.

Rows that fail a quality check are not stored; each failure becomes a `data_issue` row for
the admin review queue (PRD section 8). Loading the same day again updates the rows in
place, so a retry never creates duplicates.
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.adapters.base import EodPriceBatch, PriceBar
from app.models import Company, DataIssue, PriceDaily, Source
from app.services import quality
from app.services.quality import Issue

DATASET = "price_daily"


@dataclass
class IngestResult:
    inserted: int = 0
    updated: int = 0
    companies_created: int = 0
    unknown_tickers: list[str] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)


def _split_valid(bars: list[PriceBar]) -> tuple[list[PriceBar], list[Issue]]:
    issues = quality.check_duplicates((b.ticker for b in bars), DATASET)
    seen: dict[str, int] = {}
    for bar in bars:
        seen[bar.ticker] = seen.get(bar.ticker, 0) + 1
    valid: list[PriceBar] = []
    for bar in bars:
        if seen[bar.ticker] > 1:
            continue
        if bar.close is None or bar.close <= 0:
            issues.append(
                Issue(
                    quality.NULL_REQUIRED_FIELD,
                    DATASET,
                    f"{bar.ticker} has no positive close",
                    entity=bar.ticker,
                    day=bar.date,
                )
            )
            continue
        valid.append(bar)
    return valid, issues


def ingest_eod_batch(
    session: Session, batch: EodPriceBatch, *, create_missing_companies: bool = False
) -> IngestResult:
    """Upsert a batch. The caller commits.

    `create_missing_companies` is for the first backfill, before the company master job has
    run: an unknown ticker gets a placeholder company named after the ticker. Otherwise
    unknown tickers are skipped and reported.
    """
    result = IngestResult()
    valid, result.issues = _split_valid(batch.bars)

    source = Source(
        name=batch.source.name,
        url=batch.source.url,
        fetched_at=batch.source.fetched_at,
        checksum=batch.source.checksum,
    )
    session.add(source)
    session.flush()

    tickers = [b.ticker for b in valid]
    known = set(session.scalars(select(Company.ticker).where(Company.ticker.in_(tickers))))
    existing = {
        row.ticker: row
        for row in session.scalars(
            select(PriceDaily).where(PriceDaily.date == batch.day, PriceDaily.ticker.in_(tickers))
        )
    }

    for bar in valid:
        if bar.ticker not in known:
            if not create_missing_companies:
                result.unknown_tickers.append(bar.ticker)
                continue
            session.add(Company(ticker=bar.ticker, name=bar.ticker, source_id=source.id))
            session.flush()
            known.add(bar.ticker)
            result.companies_created += 1

        assert bar.close is not None  # guaranteed by _split_valid
        row = existing.get(bar.ticker)
        if row is None:
            session.add(
                PriceDaily(
                    ticker=bar.ticker,
                    date=batch.day,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                    source_id=source.id,
                )
            )
            result.inserted += 1
        else:
            row.open, row.high, row.low = bar.open, bar.high, bar.low
            row.volume = bar.volume
            if row.close != bar.close:
                # The raw close changed, so the stored adjusted close is no longer valid.
                row.close = bar.close
                row.adj_close = None
            row.source_id = source.id
            result.updated += 1

    if result.unknown_tickers:
        result.issues.append(
            Issue(
                "UNKNOWN_TICKER",
                DATASET,
                "Tickers not in company master: " + ", ".join(sorted(result.unknown_tickers)),
                day=batch.day,
            )
        )
    for issue in result.issues:
        session.add(
            DataIssue(
                check_name=issue.check_name,
                dataset=issue.dataset,
                entity=issue.entity,
                date=issue.day or batch.day,
                detail=issue.detail,
            )
        )
    session.flush()
    return result
