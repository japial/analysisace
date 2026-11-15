"""End-of-day prices from local CSV files, one file per trading day.

Used for the historical backfill (PRD section 8: "backfill from public EOD datasets") and
for tests. Convert a dataset to this layout first:

    <directory>/2026-11-12.csv
    ticker,open,high,low,close,volume
    GP,301.0,305.5,300.1,304.2,152340

Only `ticker` and `close` are required columns. Empty cells become None.
"""

import csv
import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.ingestion.adapters.base import EodPriceBatch, PriceBar, SourceInfo


class CsvFormatError(Exception):
    pass


def _decimal(value: str | None, path: Path, line: int, column: str) -> Decimal | None:
    if value is None or not value.strip():
        return None
    try:
        return Decimal(value.strip().replace(",", ""))
    except InvalidOperation as exc:
        raise CsvFormatError(f"{path.name} line {line}: bad {column} value {value!r}") from exc


class CsvEodPriceAdapter:
    name = "csv_eod"

    def __init__(self, directory: Path, dataset_name: str = "Local EOD CSV") -> None:
        self.directory = directory
        self.dataset_name = dataset_name

    def fetch(self, day: date) -> EodPriceBatch | None:
        path = self.directory / f"{day.isoformat()}.csv"
        if not path.exists():
            return None
        raw = path.read_bytes()
        reader = csv.DictReader(raw.decode("utf-8-sig").splitlines())
        columns = {c.strip().lower() for c in reader.fieldnames or []}
        if not {"ticker", "close"} <= columns:
            raise CsvFormatError(f"{path.name} must have `ticker` and `close` columns")

        bars: list[PriceBar] = []
        for line, raw_row in enumerate(reader, start=2):
            row = {(k or "").strip().lower(): v for k, v in raw_row.items()}
            ticker = (row.get("ticker") or "").strip().upper()
            if not ticker:
                raise CsvFormatError(f"{path.name} line {line}: empty ticker")
            volume = _decimal(row.get("volume"), path, line, "volume")
            bars.append(
                PriceBar(
                    ticker=ticker,
                    date=day,
                    open=_decimal(row.get("open"), path, line, "open"),
                    high=_decimal(row.get("high"), path, line, "high"),
                    low=_decimal(row.get("low"), path, line, "low"),
                    close=_decimal(row.get("close"), path, line, "close"),
                    volume=int(volume) if volume is not None else None,
                )
            )
        source = SourceInfo(
            name=f"{self.dataset_name}: {path.name}",
            url=None,
            fetched_at=datetime.now(UTC),
            checksum=hashlib.sha256(raw).hexdigest(),
        )
        return EodPriceBatch(source=source, day=day, bars=bars)
