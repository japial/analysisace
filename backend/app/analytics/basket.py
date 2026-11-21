"""Equal-weight Shariah basket (FR2.2). Pure functions on adjusted closes.

On the first session of each month the basket's value is split equally across the members
that have a price that day. Between rebalances each member's share moves with its price;
a member with no price on a day keeps its last price. The basket starts at `base_value`.

FR2.2 AC: the basket uses the current COMPLIANT set at every rebalance, so its history shows
how today's list would have moved. It is not a record of a fund that existed.
"""

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal

_Q = Decimal("0.0001")


def equal_weight_basket(
    prices: Mapping[str, Mapping[date, Decimal]],
    days: Sequence[date],
    base_value: Decimal = Decimal(100),
) -> list[tuple[date, Decimal]]:
    """(date, level) for each day from the first day any member has a price."""
    units: dict[str, Decimal] = {}
    last: dict[str, Decimal] = {}
    value = base_value
    month: tuple[int, int] | None = None
    out: list[tuple[date, Decimal]] = []
    for day in days:
        for ticker, series in prices.items():
            price = series.get(day)
            if price is not None and price > 0:
                last[ticker] = price
        if units:
            value = sum((units[t] * last[t] for t in units), Decimal(0))
        key = (day.year, day.month)
        if key != month:
            trading = [t for t, s in prices.items() if day in s and s[day] > 0]
            if trading:
                share = value / len(trading)
                units = {t: share / last[t] for t in trading}
                month = key
        if units:
            out.append((day, value.quantize(_Q)))
    return out


def rebase(series: Sequence[tuple[date, Decimal]], start: date) -> list[tuple[date, Decimal]]:
    """The part of `series` from `start` on, scaled so its first value is 100."""
    part = [(d, v) for d, v in series if d >= start]
    if not part or part[0][1] <= 0:
        return []
    first = part[0][1]
    return [(d, (v / first * 100).quantize(Decimal("0.01"))) for d, v in part]
