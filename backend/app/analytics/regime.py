"""Rules-based macro regime (FR8.1) and sector records by regime (FR8.2). Pure functions.

The label is a stable code joined with "|", for example "EASING|HIGH|CALM": rate trend,
inflation band key (from config), oil flag. The UI translates each part. A part whose
input is missing reads "UNKNOWN".
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

_HUNDRED = Decimal(100)


def add_months(day: date, months: int) -> date:
    """First of the month `months` after the month of `day`."""
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def month_end_values(points: Sequence[tuple[date, Decimal]]) -> dict[date, Decimal]:
    """Last value in each calendar month, keyed by the first of that month."""
    out: dict[date, tuple[date, Decimal]] = {}
    for day, value in points:
        key = date(day.year, day.month, 1)
        if key not in out or day > out[key][0]:
            out[key] = (day, value)
    return {k: v for k, (_, v) in out.items()}


def rate_trend(change_pts: Decimal | None, cfg: Mapping[str, Any]) -> str:
    if change_pts is None:
        return "UNKNOWN"
    if change_pts <= Decimal(str(cfg["easing_max_change_pts"])):
        return "EASING"
    if change_pts >= Decimal(str(cfg["tightening_min_change_pts"])):
        return "TIGHTENING"
    return "FLAT"


def inflation_band(value: Decimal | None, bands: Sequence[Mapping[str, Any]]) -> str:
    if value is None or not bands:
        return "UNKNOWN"
    for band in bands:
        limit = band.get("max")
        if limit is None or value < Decimal(str(limit)):
            return str(band["key"]).upper()
    return "UNKNOWN"


def oil_flag(change_pct: Decimal | None, cfg: Mapping[str, Any]) -> str:
    if change_pct is None:
        return "UNKNOWN"
    return "SHOCK" if change_pct >= Decimal(str(cfg["min_change_pct"])) else "CALM"


@dataclass(frozen=True)
class Regime:
    month: date
    label: str
    components: dict[str, Any]


def classify_month(
    month: date,
    yields: Mapping[date, Decimal],
    cpi: Mapping[date, Decimal],
    oil: Mapping[date, Decimal],
    cfg: Mapping[str, Any],
) -> Regime:
    """Regime for `month` from month-end values (inputs keyed by first of month)."""
    rate_cfg, oil_cfg = cfg["rate_trend"], cfg["oil_shock"]
    y_now = yields.get(month)
    y_then = yields.get(add_months(month, -int(rate_cfg["lookback_months"])))
    change = None if y_now is None or y_then is None else y_now - y_then
    o_now = oil.get(month)
    o_then = oil.get(add_months(month, -int(oil_cfg["lookback_months"])))
    oil_change = (
        None if o_now is None or o_then is None or o_then <= 0 else (o_now / o_then - 1) * _HUNDRED
    )
    inflation = cpi.get(month)
    bands = (cfg.get("inflation") or {}).get("bands") or []

    parts = [
        rate_trend(change, rate_cfg),
        inflation_band(inflation, bands),
        oil_flag(oil_change, oil_cfg),
    ]
    components = {
        "rate_trend": parts[0],
        "yield_now": None if y_now is None else str(y_now),
        "yield_change_pts": None if change is None else str(change.quantize(Decimal("0.01"))),
        "inflation_band": parts[1],
        "cpi_yoy": None if inflation is None else str(inflation),
        "oil": parts[2],
        "oil_change_pct": None if oil_change is None else str(oil_change.quantize(Decimal("0.01"))),
    }
    return Regime(month, "|".join(parts), components)


@dataclass(frozen=True)
class SectorStat:
    sector: str
    avg_monthly_return: Decimal
    hit_rate: Decimal
    n_months: int


def monthly_returns(month_ends: Mapping[date, Decimal]) -> dict[date, Decimal]:
    """Percent return of each month, from the previous month-end to this one."""
    out: dict[date, Decimal] = {}
    for month, value in month_ends.items():
        prev = month_ends.get(add_months(month, -1))
        if prev is not None and prev > 0:
            out[month] = (value / prev - 1) * _HUNDRED
    return out


def sector_stats_for_label(
    label: str,
    labels: Mapping[date, str],
    sector_returns: Mapping[str, Mapping[date, Decimal]],
) -> list[SectorStat]:
    """FR8.2: each sector's average monthly return and share of positive months in the
    months that carried `label`."""
    months = {m for m, lab in labels.items() if lab == label}
    out: list[SectorStat] = []
    for sector, returns in sorted(sector_returns.items()):
        values = [returns[m] for m in months if m in returns]
        if not values:
            continue
        avg = sum(values, Decimal(0)) / len(values)
        hits = Decimal(sum(1 for v in values if v > 0)) / len(values) * _HUNDRED
        out.append(
            SectorStat(
                sector,
                avg.quantize(Decimal("0.000001")),
                hits.quantize(Decimal("0.000001")),
                len(values),
            )
        )
    return out
