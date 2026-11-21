"""Data quality checks (PRD section 8). A failed check blocks publishing and becomes an
admin task (`data_issue` row). These are pure functions; callers store the results.

Limits such as the 10% move and the 3-session staleness window come from
config/schedules.yaml (`quality`), passed in by the caller.
"""

from collections import Counter
from collections.abc import Collection, Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from itertools import pairwise
from typing import Any

from app.core.trading_calendar import TradingCalendar

MISSING_TRADING_DAY = "MISSING_TRADING_DAY"
DUPLICATE_ROW = "DUPLICATE_ROW"
UNEXPLAINED_MOVE = "UNEXPLAINED_MOVE"
NULL_REQUIRED_FIELD = "NULL_REQUIRED_FIELD"
STALE_SOURCE = "STALE_SOURCE"


@dataclass(frozen=True)
class Issue:
    check_name: str
    dataset: str
    detail: str
    entity: str | None = None
    day: date | None = None


def check_missing_trading_days(
    calendar: TradingCalendar, start: date, end: date, present: Collection[date], dataset: str
) -> list[Issue]:
    have = set(present)
    return [
        Issue(MISSING_TRADING_DAY, dataset, f"No rows for trading day {day}", day=day)
        for day in calendar.trading_days(start, end)
        if day not in have
    ]


def check_duplicates(keys: Iterable[Hashable], dataset: str) -> list[Issue]:
    counts = Counter(keys)
    return [
        Issue(DUPLICATE_ROW, dataset, f"Key {key!r} appears {n} times")
        for key, n in counts.items()
        if n > 1
    ]


def check_required_fields(
    rows: Iterable[Mapping[str, Any]], required: Sequence[str], dataset: str
) -> list[Issue]:
    issues: list[Issue] = []
    for number, row in enumerate(rows, start=1):
        missing = [name for name in required if row.get(name) is None]
        if missing:
            issues.append(
                Issue(NULL_REQUIRED_FIELD, dataset, f"Row {number} is missing {', '.join(missing)}")
            )
    return issues


def check_unexplained_moves(
    ticker: str,
    closes: Sequence[tuple[date, Decimal]],
    action_ex_dates: Collection[date],
    max_move_pct: Decimal,
    dataset: str = "price_daily",
) -> list[Issue]:
    """Flag a close-to-close move above the limit with no corporate action on that day."""
    ordered = sorted(closes)
    ex_dates = set(action_ex_dates)
    issues: list[Issue] = []
    for (_, prev_close), (day, close) in pairwise(ordered):
        if prev_close <= 0 or day in ex_dates:
            continue
        move_pct = (close - prev_close) / prev_close * 100
        if abs(move_pct) > max_move_pct:
            issues.append(
                Issue(
                    UNEXPLAINED_MOVE,
                    dataset,
                    f"{ticker} moved {move_pct:.2f}% with no corporate action",
                    entity=ticker,
                    day=day,
                )
            )
    return issues


def check_stale(
    calendar: TradingCalendar,
    last_data_day: date | None,
    today: date,
    max_sessions: int,
    dataset: str,
) -> list[Issue]:
    """Flag a dataset whose newest row is more than `max_sessions` trading days old."""
    if last_data_day is None:
        return [Issue(STALE_SOURCE, dataset, "No data has been loaded")]
    behind = calendar.sessions_between(last_data_day, today)
    if behind > max_sessions:
        return [
            Issue(
                STALE_SOURCE,
                dataset,
                f"Newest data is {last_data_day}, {behind} trading days behind",
                day=last_data_day,
            )
        ]
    return []
