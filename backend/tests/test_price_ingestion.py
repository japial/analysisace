"""CSV end-of-day adapter and the price ingestion service (PRD section 8)."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.adapters.csv_eod import CsvEodPriceAdapter, CsvFormatError
from app.models import Company, DataIssue, PriceDaily, Source
from app.services.price_ingestion import ingest_eod_batch

DAY = date(2026, 11, 12)


def _write(directory: Path, body: str, day: date = DAY) -> CsvEodPriceAdapter:
    (directory / f"{day.isoformat()}.csv").write_text(body, encoding="utf-8")
    return CsvEodPriceAdapter(directory)


def _prices(session: Session) -> dict[str, PriceDaily]:
    return {p.ticker: p for p in session.scalars(select(PriceDaily))}


def test_adapter_parses_rows_and_records_a_checksum(tmp_path: Path) -> None:
    adapter = _write(
        tmp_path, "Ticker,Open,High,Low,Close,Volume\ngp,301,305.5,300.1,304.2,152340\n"
    )
    batch = adapter.fetch(DAY)
    assert batch is not None
    bar = batch.bars[0]
    assert (bar.ticker, bar.close, bar.volume) == ("GP", Decimal("304.2"), 152340)
    assert batch.source.checksum is not None and len(batch.source.checksum) == 64


def test_adapter_returns_none_when_the_day_has_no_file(tmp_path: Path) -> None:
    assert CsvEodPriceAdapter(tmp_path).fetch(DAY) is None


def test_adapter_rejects_a_file_without_required_columns(tmp_path: Path) -> None:
    with pytest.raises(CsvFormatError, match="ticker"):
        _write(tmp_path, "symbol,last\nGP,1\n").fetch(DAY)


def test_ingest_stores_prices_with_their_source(session: Session, tmp_path: Path) -> None:
    session.add(Company(ticker="GP", name="Grameenphone"))
    batch = _write(tmp_path, "ticker,close,volume\nGP,304.2,100\n").fetch(DAY)
    assert batch is not None
    result = ingest_eod_batch(session, batch)

    assert (result.inserted, result.updated, result.issues) == (1, 0, [])
    price = _prices(session)["GP"]
    assert price.close == Decimal("304.2")
    stored_source = session.get(Source, price.source_id)
    assert stored_source is not None and stored_source.checksum == batch.source.checksum


def test_reloading_a_day_updates_rows_without_duplicates(session: Session, tmp_path: Path) -> None:
    session.add(Company(ticker="GP", name="Grameenphone"))
    first = _write(tmp_path, "ticker,close\nGP,304.2\n").fetch(DAY)
    assert first is not None
    ingest_eod_batch(session, first)
    _prices(session)["GP"].adj_close = Decimal("304.2")

    corrected = _write(tmp_path, "ticker,close\nGP,305.0\n").fetch(DAY)
    assert corrected is not None
    result = ingest_eod_batch(session, corrected)

    assert (result.inserted, result.updated) == (0, 1)
    prices = session.scalars(select(PriceDaily)).all()
    assert len(prices) == 1
    assert prices[0].close == Decimal("305.0")
    assert prices[0].adj_close is None  # must be recomputed after the raw close changed


def test_bad_rows_are_skipped_and_become_admin_issues(session: Session, tmp_path: Path) -> None:
    session.add_all([Company(ticker="GP", name="Grameenphone"), Company(ticker="BATBC", name="B")])
    body = "ticker,close\nGP,304.2\nGP,304.9\nBATBC,\nNEWCO,12\n"
    batch = _write(tmp_path, body).fetch(DAY)
    assert batch is not None
    result = ingest_eod_batch(session, batch)

    assert result.inserted == 0
    assert result.unknown_tickers == ["NEWCO"]
    checks = sorted(i.check_name for i in session.scalars(select(DataIssue)))
    assert checks == ["DUPLICATE_ROW", "NULL_REQUIRED_FIELD", "UNKNOWN_TICKER"]
    assert _prices(session) == {}


def test_backfill_can_create_placeholder_companies(session: Session, tmp_path: Path) -> None:
    batch = _write(tmp_path, "ticker,close\nNEWCO,12\n").fetch(DAY)
    assert batch is not None
    result = ingest_eod_batch(session, batch, create_missing_companies=True)

    assert (result.inserted, result.companies_created) == (1, 1)
    company = session.scalar(select(Company).where(Company.ticker == "NEWCO"))
    assert company is not None and company.source_id is not None
