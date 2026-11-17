"""Allocation weights, drift from a target, and fixed-income sums (F16, F26).

Pure functions. Drift is described, never prescribed: the output says how far each group
is from the target the person set, in points and in taka (FR16.2).
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

Q2 = Decimal("0.01")
HUNDRED = Decimal(100)


def weights(values: Iterable[tuple[str, Decimal]]) -> dict[str, tuple[Decimal, Decimal]]:
    """Group -> (value, percent of the total). Negative totals are not expected."""
    grouped: dict[str, Decimal] = defaultdict(Decimal)
    for key, value in values:
        grouped[key] += value
    total = sum(grouped.values(), Decimal(0))
    return {
        key: (value.quantize(Q2), (value / total * 100).quantize(Q2) if total > 0 else Decimal(0))
        for key, value in sorted(grouped.items(), key=lambda item: -item[1])
    }


@dataclass(frozen=True)
class Drift:
    asset_class: str
    value: Decimal
    actual_pct: Decimal
    target_pct: Decimal
    band_pct: Decimal
    drift_pts: Decimal  # actual minus target
    outside_band: bool
    # Taka by which the group is above (+) or below (-) its target share of the total.
    difference: Decimal


def drift(
    actual: Mapping[str, Decimal], targets: Mapping[str, tuple[Decimal, Decimal]]
) -> list[Drift]:
    """Drift per asset class. `targets` maps class -> (target percent, band percent)."""
    total = sum(actual.values(), Decimal(0))
    out: list[Drift] = []
    for asset_class in sorted(set(actual) | set(targets)):
        value = actual.get(asset_class, Decimal(0))
        target, band = targets.get(asset_class, (Decimal(0), Decimal(0)))
        share = (value / total * 100).quantize(Q2) if total > 0 else Decimal(0)
        points = share - target
        out.append(
            Drift(
                asset_class=asset_class,
                value=value.quantize(Q2),
                actual_pct=share,
                target_pct=target,
                band_pct=band,
                drift_pts=points,
                outside_band=asset_class in targets and abs(points) > band,
                difference=(value - total * target / HUNDRED).quantize(Q2),
            )
        )
    return out


# --- Fixed income (F26) ---------------------------------------------------------------


def expected_profit(amount: Decimal, rate_pct: Decimal, start: date, end: date) -> Decimal:
    """Simple profit at a yearly rate between two dates: amount x rate x days / 365."""
    days = max((end - start).days, 0)
    return (amount * rate_pct / HUNDRED * days / 365).quantize(Q2)


def real_rate_pct(rate_pct: Decimal, inflation_pct: Decimal) -> Decimal:
    """Return above inflation, in percent: (1 + rate) / (1 + inflation) - 1 (FR26.4)."""
    real = (1 + rate_pct / HUNDRED) / (1 + inflation_pct / HUNDRED) - 1
    return (real * HUNDRED).quantize(Q2)


def metal_value(
    weight_grams: Decimal, price_per_gram: Decimal, karat: int | None, price_karat: int | None
) -> Decimal:
    """Gold by weight and purity (FR25.2). `price_karat` is the purity the price is for.

    Silver passes no karat and is valued by weight alone.
    """
    value = weight_grams * price_per_gram
    if karat and price_karat:
        value = value * karat / price_karat
    return value.quantize(Q2)
