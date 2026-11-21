"""Shock playbook metrics (FR5.2). Pure functions on adjusted closes.

For one subject and one event starting on `t0`:

- base: the close of the last session before `t0`;
- ret_h: percent change from base to the close of the h-th session on or after `t0`
  (session 1 is the first session on or after `t0`);
- max_dd: the deepest fall from the running peak (starting at base) within the first
  `window` sessions, as a negative percent (0 when the price never fell);
- sessions_to_recover: the first session at which the close is back at or above base after
  having been below it; 0 when it never fell below base; None when it had not recovered
  within `recovery_window` sessions or the data ends first.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

_HUNDRED = Decimal(100)
_Q = Decimal("0.000001")


@dataclass(frozen=True)
class EventOutcome:
    returns: dict[int, Decimal | None]
    max_drawdown: Decimal | None
    sessions_to_recover: int | None


def event_outcome(
    closes: Sequence[tuple[date, Decimal]],
    t0: date,
    horizons: Sequence[int],
    window: int,
    recovery_window: int,
) -> EventOutcome | None:
    """None when there is no close before `t0` or no session on or after it."""
    ordered = sorted(closes)
    before = [c for d, c in ordered if d < t0]
    after = [c for d, c in ordered if d >= t0]
    if not before or not after or before[-1] <= 0:
        return None
    base = before[-1]

    returns: dict[int, Decimal | None] = {}
    for h in horizons:
        returns[h] = (
            ((after[h - 1] / base - 1) * _HUNDRED).quantize(_Q) if len(after) >= h else None
        )

    peak, worst = base, Decimal(0)
    for close in after[:window]:
        peak = max(peak, close)
        worst = min(worst, close / peak - 1)
    max_dd = (worst * _HUNDRED).quantize(_Q)

    recovered: int | None = None
    fell = False
    for session, close in enumerate(after[:recovery_window], start=1):
        if close < base:
            fell = True
        elif fell:
            recovered = session
            break
    if not fell:
        recovered = 0
    return EventOutcome(returns, max_dd, recovered)


def equal_weight_index(
    series: Sequence[dict[date, Decimal]], days: Sequence[date]
) -> list[tuple[date, Decimal]]:
    """An equal-weight index of several price series, rebased to 100 on its first day.

    Each day's index return is the mean return of the members that traded that day, each
    measured from its own last traded close. The index starts on the first day any member
    trades. Used for sector-level event metrics and scores.
    """
    out: list[tuple[date, Decimal]] = []
    level = Decimal(100)
    last: list[Decimal | None] = [None] * len(series)
    started = False
    for day in days:
        moves: list[Decimal] = []
        for i, s in enumerate(series):
            price = s.get(day)
            if price is None or price <= 0:
                continue
            previous = last[i]
            if previous is not None:
                moves.append(price / previous - 1)
            last[i] = price
            started = True
        if moves:
            level *= 1 + sum(moves, Decimal(0)) / len(moves)
        if started:
            out.append((day, level.quantize(Decimal("0.0001"))))
    return out
