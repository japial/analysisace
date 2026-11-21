"""Return and risk formulas (PRD 7.2): XIRR, time-weighted return, volatility, drawdown.

Pure functions. Rates are worked out in floating point, because roots and powers have no
exact decimal form, and handed back as Decimal percentages. Money stays Decimal.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

PCT = Decimal("0.000001")
Q2 = Decimal("0.01")
_DAYS_IN_YEAR = 365.0


def pct(value: float) -> Decimal:
    """A ratio (0.0825) as a percentage Decimal (8.250000)."""
    return Decimal(str(value * 100)).quantize(PCT)


# --- XIRR -----------------------------------------------------------------------------


def _npv(rate: float, flows: Sequence[tuple[float, float]]) -> float:
    return float(sum(amount / (1 + rate) ** years for years, amount in flows))


def xirr(cash_flows: Sequence[tuple[date, Decimal]]) -> Decimal | None:
    """Annualised money-weighted return, in percent (FR15.1, FR25.3).

    Money paid in is negative, money received is positive; the last flow is usually today's
    value. Newton-Raphson first, bisection if it wanders (PRD 7.2). Returns None when there
    is no answer: fewer than two dates, or flows that are all one sign.
    """
    flows = [(d, float(a)) for d, a in cash_flows if a != 0]
    if len({d for d, _ in flows}) < 2:
        return None
    if not (any(a < 0 for _, a in flows) and any(a > 0 for _, a in flows)):
        return None
    first = min(d for d, _ in flows)
    timed = [((d - first).days / _DAYS_IN_YEAR, a) for d, a in flows]

    rate = 0.1
    for _ in range(50):
        value = _npv(rate, timed)
        slope = sum(-years * amount / (1 + rate) ** (years + 1) for years, amount in timed)
        if slope == 0:
            break
        step = value / slope
        rate -= step
        if rate <= -0.999999 or not math.isfinite(rate):
            break
        if abs(step) < 1e-10:
            return pct(rate)

    low, high = -0.999999, 100.0
    f_low, f_high = _npv(low, timed), _npv(high, timed)
    if f_low * f_high > 0:
        return None
    for _ in range(200):
        mid = (low + high) / 2
        f_mid = _npv(mid, timed)
        if abs(f_mid) < 1e-7 or (high - low) < 1e-10:
            return pct(mid)
        if f_low * f_mid < 0:
            high = mid
        else:
            low, f_low = mid, f_mid
    return pct((low + high) / 2)


# --- Time-weighted return -------------------------------------------------------------


def daily_return(start_value: Decimal, end_value: Decimal, net_flow: Decimal = Decimal(0)) -> float:
    """One day's return when money moved at the end of the day.

    `end_value` includes the flow; `net_flow` is positive for money added.
    """
    if start_value <= 0:
        return 0.0
    return float((end_value - net_flow) / start_value) - 1


def link_returns(returns: Sequence[float]) -> float:
    """Daily returns chained into one period return (PRD 7.2: linked sub-periods)."""
    growth = 1.0
    for r in returns:
        growth *= 1 + r
    return growth - 1


def annualise(period_return: float, days: int) -> float | None:
    """Yearly rate for a return earned over `days` calendar days. None under a month."""
    if days < 30 or period_return <= -1:
        return None
    return float((1 + period_return) ** (_DAYS_IN_YEAR / days) - 1)


def weighted_return(
    positions: Sequence[tuple[Decimal, float]], income: Decimal = Decimal(0)
) -> float:
    """A portfolio's return for one day from its holdings.

    `positions` is (value at the previous close, the holding's own return today).
    `income` is cash dividends received today. Using each holding's adjusted-price return
    keeps bonus issues and splits from showing up as losses.
    """
    total = sum((value for value, _ in positions), Decimal(0))
    if total <= 0:
        return 0.0
    gain = sum(float(value) * r for value, r in positions) + float(income)
    return gain / float(total)


# --- Risk -----------------------------------------------------------------------------


def annualised_volatility(weekly_returns: Sequence[float]) -> float | None:
    """Standard deviation of weekly returns times the square root of 52 (PRD 7.2)."""
    if len(weekly_returns) < 2:
        return None
    return float(statistics_stdev(weekly_returns) * math.sqrt(52))


def statistics_stdev(values: Sequence[float]) -> float:
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))


def max_drawdown(levels: Sequence[float]) -> float:
    """Largest fall from a peak, as a negative ratio. Zero when the series never falls."""
    worst, peak = 0.0, -math.inf
    for level in levels:
        peak = max(peak, level)
        if peak > 0:
            worst = min(worst, level / peak - 1)
    return worst


def growth_index(returns: Sequence[float], base: float = 100.0) -> list[float]:
    """Level after each return, starting from `base`."""
    out, level = [], base
    for r in returns:
        level *= 1 + r
        out.append(level)
    return out


# --- Diversification (FR15.3) ---------------------------------------------------------


def top_weight(values: Sequence[Decimal], n: int = 5) -> Decimal:
    """Share of the total held in the `n` largest positions, in percent."""
    total = sum(values, Decimal(0))
    if total <= 0:
        return Decimal(0)
    largest = sum(sorted(values, reverse=True)[:n], Decimal(0))
    return (largest / total * 100).quantize(Q2)


def herfindahl(values: Sequence[Decimal]) -> Decimal:
    """Herfindahl index of the group weights: 1 for one group, 1/n for n equal groups."""
    total = sum(values, Decimal(0))
    if total <= 0:
        return Decimal(0)
    return sum(((v / total) ** 2 for v in values), Decimal(0)).quantize(Decimal("0.0001"))


# --- Realised gains (FR13.6) ----------------------------------------------------------


@dataclass(frozen=True)
class Trade:
    day: date
    type: str  # BUY, SELL, BONUS or FEE
    amount: Decimal
    units: Decimal


def realised_gains(trades: Sequence[Trade]) -> list[tuple[date, Decimal]]:
    """Gain or loss on each sale, by the average-cost method.

    A sale of more units than are held uses what is held; the rest has no cost basis and
    counts wholly as gain, so a missing purchase record overstates rather than hides it.
    """
    units, cost = Decimal(0), Decimal(0)
    gains: list[tuple[date, Decimal]] = []
    for trade in sorted(trades, key=lambda t: t.day):
        if trade.type == "BUY":
            units += trade.units
            cost += trade.amount
        elif trade.type == "FEE":
            cost += trade.amount
        elif trade.type == "BONUS":
            units += trade.units
        elif trade.type == "SELL":
            sold = min(trade.units, units)
            basis = (cost * sold / units).quantize(Q2) if units > 0 else Decimal(0)
            gains.append((trade.day, trade.amount - basis))
            units -= sold
            cost -= basis
    return gains
