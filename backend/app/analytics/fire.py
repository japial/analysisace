"""FIRE projection and what-if scenarios (F17, F18).

Everything is in today's taka ("real terms"): the yearly spending and the FIRE number do
not grow with inflation, and the return used is the return above inflation (FR17.2).
Pure functions. These are projections of the person's own inputs, never a forecast.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any

Q2 = Decimal("0.01")
HUNDRED = Decimal(100)
TWELVE = Decimal(12)


@dataclass(frozen=True)
class FireInputs:
    net_worth: Decimal  # investable base today
    monthly_savings: Decimal
    yearly_expenses: Decimal
    nominal_return_pct: Decimal
    inflation_pct: Decimal
    withdrawal_rate_pct: Decimal
    current_age: Decimal
    max_age: int = 100

    def as_dict(self) -> dict[str, str]:
        return {
            "net_worth": str(self.net_worth),
            "monthly_savings": str(self.monthly_savings),
            "yearly_expenses": str(self.yearly_expenses),
            "nominal_return_pct": str(self.nominal_return_pct),
            "inflation_pct": str(self.inflation_pct),
            "withdrawal_rate_pct": str(self.withdrawal_rate_pct),
            "current_age": str(self.current_age),
        }


@dataclass(frozen=True)
class YearPoint:
    year: int  # 0 is today
    age: Decimal
    net_worth: Decimal

    def as_dict(self) -> dict[str, Any]:
        return {"year": self.year, "age": str(self.age), "net_worth": str(self.net_worth)}


@dataclass(frozen=True)
class FireResult:
    fire_number: Decimal
    real_return_pct: Decimal
    fire_age: Decimal | None  # None: not reached before `max_age`
    path: list[YearPoint]
    # Lowest net worth on the yearly path, for scenario comparison (FR18.2).
    worst_year_net_worth: Decimal
    # Set only when the path includes years of living off the money.
    depleted_age: Decimal | None = None


def fire_number(yearly_expenses: Decimal, withdrawal_rate_pct: Decimal) -> Decimal:
    """Yearly spending divided by the withdrawal rate (FR17.2)."""
    if withdrawal_rate_pct <= 0:
        raise ValueError("Withdrawal rate must be above zero")
    return (yearly_expenses * HUNDRED / withdrawal_rate_pct).quantize(Q2)


def real_return(nominal_pct: Decimal, inflation_pct: Decimal) -> Decimal:
    """(1 + nominal) / (1 + inflation) - 1, as a ratio (FR17.2)."""
    return (1 + nominal_pct / HUNDRED) / (1 + inflation_pct / HUNDRED) - 1


def _monthly_rate(yearly: Decimal) -> Decimal:
    if yearly <= -1:
        return Decimal(-1)
    return Decimal(str(float(1 + yearly) ** (1 / 12))) - 1


def project(
    inputs: FireInputs,
    *,
    first_year_shock_pct: Decimal = Decimal(0),
    retire_at_age: Decimal | None = None,
) -> FireResult:
    """Month-by-month projection in real terms (FR17.2, FR17.3).

    `first_year_shock_pct` removes that share of net worth once, at the end of month 12.
    `retire_at_age` stops the saving at that age and takes the yearly spending out from
    then on, to show whether the money lasts.
    """
    target = fire_number(inputs.yearly_expenses, inputs.withdrawal_rate_pct)
    yearly = real_return(inputs.nominal_return_pct, inputs.inflation_pct)
    monthly = _monthly_rate(yearly)
    months = max(int((Decimal(inputs.max_age) - inputs.current_age) * 12), 0)
    monthly_spend = inputs.yearly_expenses / TWELVE

    worth = inputs.net_worth
    path = [YearPoint(0, inputs.current_age, worth.quantize(Q2))]
    fire_age: Decimal | None = inputs.current_age if worth >= target else None
    depleted_age: Decimal | None = None

    for month in range(1, months + 1):
        age = inputs.current_age + Decimal(month) / TWELVE
        retired = retire_at_age is not None and age > retire_at_age
        worth = worth * (1 + monthly) + (-monthly_spend if retired else inputs.monthly_savings)
        if month == 12 and first_year_shock_pct:
            worth *= 1 - first_year_shock_pct / HUNDRED
        if worth <= 0 and retired:
            worth = Decimal(0)
            if depleted_age is None:
                depleted_age = age.quantize(Q2)
        if fire_age is None and worth >= target:
            fire_age = age.quantize(Q2)
        if month % 12 == 0:
            path.append(YearPoint(month // 12, age.quantize(Q2), worth.quantize(Q2)))

    return FireResult(
        fire_number=target,
        real_return_pct=(yearly * HUNDRED).quantize(Decimal("0.0001")),
        fire_age=fire_age,
        path=path,
        worst_year_net_worth=min(point.net_worth for point in path),
        depleted_age=depleted_age,
    )


PRESETS = frozenset(
    {"MARKET_CRASH", "EVENT_REPLAY", "EXPENSES_UP", "RETIRE_EARLIER", "INFLATION_SHOCK"}
)


def run_scenario(
    inputs: FireInputs, preset: str, params: Mapping[str, Decimal], base: FireResult
) -> FireResult:
    """One preset from FR18.1 applied to the plan's inputs.

    MARKET_CRASH and EVENT_REPLAY: `fall_pct` of the `market_share_pct` of net worth is lost
    at the end of year 1. EXPENSES_UP: spending rises by `pct`. INFLATION_SHOCK: inflation
    is higher by `points`. RETIRE_EARLIER: saving stops `years` before the base FIRE age.
    """
    if preset in ("MARKET_CRASH", "EVENT_REPLAY"):
        shock = params["fall_pct"] * params.get("market_share_pct", HUNDRED) / HUNDRED
        return project(inputs, first_year_shock_pct=shock)
    if preset == "EXPENSES_UP":
        raised = inputs.yearly_expenses * (1 + params["pct"] / HUNDRED)
        return project(replace(inputs, yearly_expenses=raised.quantize(Q2)))
    if preset == "INFLATION_SHOCK":
        return project(replace(inputs, inflation_pct=inputs.inflation_pct + params["points"]))
    if preset == "RETIRE_EARLIER":
        if base.fire_age is None:
            raise ValueError("The base plan never reaches its FIRE number")
        age = max(base.fire_age - params["years"], inputs.current_age)
        result = project(inputs, retire_at_age=age)
        return replace(result, fire_age=age)
    raise ValueError(f"Unknown scenario preset: {preset}")
