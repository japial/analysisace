"""Rate sensitivity regression (FR3.1 to FR3.3). Pure functions, no database.

The model for one stock or sector, on weekly data:

    r_t = a + b * dy_t + c * m_t + e_t

`r` is the weekly log return of the adjusted close, `dy` the weekly change in the 91-day
T-bill yield in percentage points and `m` the weekly log return of the DSEX. The reported
score is `b` as a percent: the typical percent move in a week when the yield rises one point.
A second fit leaves out the market term.

Standard errors are Newey-West (Bartlett kernel), so serial correlation in weekly returns does
not overstate confidence. Statistics are floats; they are not money.
"""

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from app.models.enums import Confidence

_WEEK = timedelta(days=7)


@dataclass(frozen=True)
class WeeklyObs:
    week_start: date
    r: float  # log return of the subject
    dy: float  # change in yield, percentage points
    m: float  # log return of the market index


@dataclass(frozen=True)
class OlsFit:
    coefficients: list[float]
    std_errors: list[float]
    t_stats: list[float]
    n_obs: int
    lags: int


def _last_by_week(
    series: Mapping[date, float], week_start: Callable[[date], date]
) -> dict[date, float]:
    last_day: dict[date, date] = {}
    for day in series:
        key = week_start(day)
        if key not in last_day or day > last_day[key]:
            last_day[key] = day
    return {key: series[day] for key, day in last_day.items()}


def _value_on_or_before(points: Sequence[tuple[date, float]], day: date) -> float | None:
    """Latest value at or before `day`. `points` is sorted by date."""
    lo, hi = 0, len(points)
    while lo < hi:
        mid = (lo + hi) // 2
        if points[mid][0] <= day:
            lo = mid + 1
        else:
            hi = mid
    return points[lo - 1][1] if lo else None


def overlaps(first: date, last: date, ranges: Sequence[tuple[date, date]]) -> bool:
    """True when the days from `first` to `last` share any day with one of `ranges`."""
    return any(start <= last and first <= end for start, end in ranges)


def weekly_sample(
    subject: Mapping[date, float],
    market: Mapping[date, float],
    yields: Sequence[tuple[date, float]],
    week_start: Callable[[date], date],
    excluded: Sequence[tuple[date, date]],
    start: date,
    end: date,
) -> list[WeeklyObs]:
    """Build the weekly observations from daily data (FR3.2).

    A week counts only when the subject and the market traded in it and in the week before,
    a yield is known at both week ends, and neither week touches an excluded period (floor
    prices). Weeks are DSE weeks (Sunday to Thursday) keyed by their Sunday.
    """
    stock_w = _last_by_week(subject, week_start)
    market_w = _last_by_week(market, week_start)
    ordered_yields = sorted(yields)
    out: list[WeeklyObs] = []
    for key in sorted(stock_w):
        prev = key - _WEEK
        week_end = key + timedelta(days=6)
        if not start <= key <= end:
            continue
        if prev not in stock_w or key not in market_w or prev not in market_w:
            continue
        if overlaps(prev, week_end, excluded):
            continue
        y_now = _value_on_or_before(ordered_yields, week_end)
        y_prev = _value_on_or_before(ordered_yields, prev + timedelta(days=6))
        if y_now is None or y_prev is None:
            continue
        p0, p1 = stock_w[prev], stock_w[key]
        m0, m1 = market_w[prev], market_w[key]
        if min(p0, p1, m0, m1) <= 0:
            continue
        out.append(WeeklyObs(key, math.log(p1 / p0), y_now - y_prev, math.log(m1 / m0)))
    return out


def _invert(matrix: list[list[float]]) -> list[list[float]]:
    """Gauss-Jordan inverse of a small square matrix."""
    n = len(matrix)
    aug = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-14:
            raise ValueError("Regressors are collinear")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        p = aug[col][col]
        aug[col] = [v / p for v in aug[col]]
        for r in range(n):
            if r != col and aug[r][col] != 0.0:
                f = aug[r][col]
                aug[r] = [a - f * b for a, b in zip(aug[r], aug[col], strict=True)]
    return [row[n:] for row in aug]


def default_lags(n: int) -> int:
    """Newey-West rule of thumb: floor(4 * (n / 100) ^ (2 / 9))."""
    return int(4 * (n / 100) ** (2 / 9))


def ols_newey_west(y: Sequence[float], x: Sequence[Sequence[float]], lags: int | None) -> OlsFit:
    """OLS of `y` on `x` (each row already holds the constant 1) with Newey-West errors.

    A small-sample factor n / (n - k) is applied to the covariance.
    """
    n, k = len(y), len(x[0])
    if n <= k:
        raise ValueError("Too few observations")
    lags = default_lags(n) if lags is None else lags
    xtx = [[sum(row[i] * row[j] for row in x) for j in range(k)] for i in range(k)]
    xty = [sum(row[i] * yi for row, yi in zip(x, y, strict=True)) for i in range(k)]
    inv = _invert(xtx)
    beta = [sum(inv[i][j] * xty[j] for j in range(k)) for i in range(k)]
    resid = [
        yi - sum(b * v for b, v in zip(beta, row, strict=True))
        for row, yi in zip(x, y, strict=True)
    ]

    # Meat of the sandwich: sum of score outer products plus weighted autocovariances.
    scores = [[v * e for v in row] for row, e in zip(x, resid, strict=True)]
    meat = [[sum(s[i] * s[j] for s in scores) for j in range(k)] for i in range(k)]
    for lag in range(1, lags + 1):
        weight = 1 - lag / (lags + 1)
        for i in range(k):
            for j in range(k):
                acc = sum(scores[t][i] * scores[t - lag][j] for t in range(lag, n))
                acc_t = sum(scores[t - lag][i] * scores[t][j] for t in range(lag, n))
                meat[i][j] += weight * (acc + acc_t)
    correction = n / (n - k)
    cov = [
        [
            correction * sum(inv[i][a] * meat[a][b] * inv[b][j] for a in range(k) for b in range(k))
            for j in range(k)
        ]
        for i in range(k)
    ]
    se = [math.sqrt(max(cov[i][i], 0.0)) for i in range(k)]
    t = [b / s if s > 0 else 0.0 for b, s in zip(beta, se, strict=True)]
    return OlsFit(beta, se, t, n, lags)


@dataclass(frozen=True)
class Sensitivity:
    """The score for one subject. `value_pct` is None when the sample is too short."""

    value_pct: float | None
    std_error_pct: float | None
    t_stat: float | None
    confidence: Confidence
    n_obs: int
    sample_start: date | None
    sample_end: date | None


def confidence_for(t_stat: float, high_min: float, medium_min: float) -> Confidence:
    """FR3.3: HIGH when |t| >= 2.5, MEDIUM when 1.5 <= |t| < 2.5, else LOW (from config)."""
    if abs(t_stat) >= high_min:
        return Confidence.HIGH
    if abs(t_stat) >= medium_min:
        return Confidence.MEDIUM
    return Confidence.LOW


def rate_sensitivity(
    sample: Sequence[WeeklyObs],
    *,
    with_market: bool,
    min_weeks: int,
    lags: int | None,
    high_min_t: float,
    medium_min_t: float,
) -> Sensitivity:
    """Fit FR3.1 on a weekly sample and report `b` as percent per one-point yield rise."""
    n = len(sample)
    first = sample[0].week_start if sample else None
    last = sample[-1].week_start + timedelta(days=6) if sample else None
    if n < min_weeks:
        return Sensitivity(None, None, None, Confidence.INSUFFICIENT, n, first, last)
    y = [o.r for o in sample]
    x = [[1.0, o.dy, o.m] if with_market else [1.0, o.dy] for o in sample]
    try:
        fit = ols_newey_west(y, x, lags)
    except ValueError:
        return Sensitivity(None, None, None, Confidence.INSUFFICIENT, n, first, last)
    # Log return x 100 is close to a percent move for weekly sizes.
    b, se, t = fit.coefficients[1] * 100, fit.std_errors[1] * 100, fit.t_stats[1]
    return Sensitivity(b, se, t, confidence_for(t, high_min_t, medium_min_t), n, first, last)
