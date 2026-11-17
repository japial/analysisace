"""Daily cost calculations (F12): recurring dates, totals, inflation adjustment.

Pure functions: no database, no clock. Money is Decimal throughout.
"""

import calendar
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from decimal import Decimal

Q2 = Decimal("0.01")
_MONTH_STEP = {"MONTHLY": 1, "QUARTERLY": 3, "HALF_YEARLY": 6, "YEARLY": 12}
RECURRING_FREQUENCIES = frozenset({"WEEKLY", *_MONTH_STEP})


def month_start(day: date) -> date:
    return day.replace(day=1)


def add_months(day: date, months: int, anchor_day: int | None = None) -> date:
    """`day` moved by whole months. A 31st becomes the last day of a shorter month."""
    index = day.year * 12 + (day.month - 1) + months
    year, month = divmod(index, 12)
    wanted = anchor_day or day.day
    return date(year, month + 1, min(wanted, calendar.monthrange(year, month + 1)[1]))


def occurrences(
    start: date, frequency: str, until: date, end: date | None = None, since: date | None = None
) -> list[date]:
    """Dates a recurring cost falls due, from `start` up to `until` (FR12.2).

    `end` is the rule's own last date. `since` drops earlier dates without changing the
    rhythm, so rent due on the 31st stays on month ends.
    """
    if frequency not in RECURRING_FREQUENCIES:
        raise ValueError(f"Not a recurring frequency: {frequency}")
    last = min(until, end) if end else until
    out: list[date] = []
    step = 0
    while True:
        if frequency == "WEEKLY":
            due = start + timedelta(weeks=step)
        else:
            due = add_months(start, step * _MONTH_STEP[frequency], anchor_day=start.day)
        if due > last:
            return out
        if since is None or due >= since:
            out.append(due)
        step += 1


def monthly_totals(entries: Iterable[tuple[date, Decimal]]) -> dict[date, Decimal]:
    """Sum of amounts per calendar month, keyed by the first of the month (FR12.3)."""
    totals: dict[date, Decimal] = defaultdict(Decimal)
    for day, amount in entries:
        totals[month_start(day)] += amount
    return dict(sorted(totals.items()))


def trailing_total(
    entries: Iterable[tuple[date, Decimal]], as_of: date, months: int = 12
) -> Decimal:
    """Spending in the `months` up to and including `as_of` (FR12.4)."""
    first = add_months(as_of, -months) + timedelta(days=1)
    return sum((amount for day, amount in entries if first <= day <= as_of), Decimal(0))


def price_index(yoy_pct_by_month: Mapping[date, Decimal]) -> dict[date, Decimal]:
    """A price index (first month = 100) built from year-on-year inflation.

    BBS publishes the yearly rate each month. A month's own price rise is taken as the
    twelfth root of that rate, which is an approximation: it is exact only when inflation
    is steady. Good enough to restate past spending in today's prices (FR12.3).
    """
    index: dict[date, Decimal] = {}
    level = Decimal(100)
    for position, month in enumerate(sorted(yoy_pct_by_month)):
        if position:
            yearly = 1 + float(yoy_pct_by_month[month]) / 100
            level *= Decimal(str(yearly ** (1 / 12)))
        index[month] = level
    return index


def in_prices_of(
    totals: Mapping[date, Decimal], index: Mapping[date, Decimal], base_month: date
) -> dict[date, Decimal]:
    """Each month's total restated in the prices of `base_month`.

    A month with no index value uses the nearest earlier one; before the first, the first.
    """
    months = sorted(index)
    if not months:
        return dict(totals)

    def level(month: date) -> Decimal:
        known = [m for m in months if m <= month]
        return index[known[-1] if known else months[0]]

    base = level(base_month)
    return {month: (amount * base / level(month)).quantize(Q2) for month, amount in totals.items()}
