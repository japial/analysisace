"""Shariah screening (PRD 7.1, F1). Pure functions: the caller loads figures and config.

Stage 1 is the admin's business classification. Stage 2 compares four ratios with the
thresholds of one methodology from config/shariah.yaml. The status is:

- NON_COMPLIANT when Stage 1 fails, or any ratio is at or above its threshold by more than
  the review margin;
- UNDER_REVIEW when Stage 1 is not classified, any input is missing, or any ratio lies within
  `review_margin_pts` of its threshold (on either side) (FR1 acceptance criteria);
- COMPLIANT otherwise.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.models.enums import ShariahStatus

_HUNDRED = Decimal(100)
_Q = Decimal("0.01")

# rule name -> (numerator field, denominator: "market_cap" or "total_revenue")
RULES: dict[str, tuple[str, str]] = {
    "debt_to_market_cap": ("total_debt_interest_bearing", "market_cap"),
    "cash_and_interest_securities_to_market_cap": ("cash_and_interest_securities", "market_cap"),
    "non_permissible_income_to_revenue": ("non_permissible_income", "total_revenue"),
    "receivables_to_market_cap": ("receivables", "market_cap"),
}


@dataclass(frozen=True)
class ScreenInput:
    """Figures for one company and one reporting period. None means "not stated"."""

    stage1_pass: bool | None  # None: no classification yet
    stage1_reason: str | None
    market_cap: Decimal | None  # trailing average, see `average_market_cap`
    total_debt_interest_bearing: Decimal | None
    cash_and_interest_securities: Decimal | None
    receivables: Decimal | None
    total_revenue: Decimal | None
    non_permissible_income: Decimal | None


@dataclass(frozen=True)
class RuleResult:
    rule: str
    value_pct: Decimal | None
    threshold_pct: Decimal
    passed: bool | None  # None: could not be tested
    note: str | None = None

    def as_json(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "value_pct": None if self.value_pct is None else str(self.value_pct),
            "threshold_pct": str(self.threshold_pct),
            "passed": self.passed,
            "note": self.note,
        }


@dataclass
class ScreenResult:
    status: ShariahStatus
    ratios: list[RuleResult] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    @property
    def ratios_json(self) -> list[dict[str, Any]]:
        return [r.as_json() for r in self.ratios]


def average_market_cap(closes: list[Decimal], shares_outstanding: int | None) -> Decimal | None:
    """Mean of daily close x shares over the window. None when either input is missing."""
    if not closes or not shares_outstanding:
        return None
    return (sum(closes, Decimal(0)) / len(closes) * shares_outstanding).quantize(_Q)


def _ratio(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return (numerator / denominator * _HUNDRED).quantize(_Q)


def screen(data: ScreenInput, method: dict[str, Any], review_margin_pts: Decimal) -> ScreenResult:
    """Screen one company with one methodology (`methods.<name>` from shariah.yaml).

    Reasons are stable codes (rule names and outcomes), so the UI can translate them.
    """
    if data.stage1_pass is False:
        return ScreenResult(
            ShariahStatus.NON_COMPLIANT,
            reasons=["STAGE1_FAIL"],
        )

    results: list[RuleResult] = []
    reasons: list[str] = []
    missing = False
    borderline = False
    failed = False
    figures = {
        "total_debt_interest_bearing": data.total_debt_interest_bearing,
        "cash_and_interest_securities": data.cash_and_interest_securities,
        "receivables": data.receivables,
        "non_permissible_income": data.non_permissible_income,
        "market_cap": data.market_cap,
        "total_revenue": data.total_revenue,
    }
    for rule, spec in method["ratios"].items():
        if rule not in RULES:
            raise ValueError(f"Unknown Shariah rule in config: {rule}")
        threshold = Decimal(str(spec["max_pct"]))
        numerator, denominator = RULES[rule]
        value = _ratio(figures[numerator], figures[denominator])
        if value is None:
            missing = True
            gap = numerator if figures[numerator] is None else denominator
            results.append(RuleResult(rule, None, threshold, None, f"MISSING:{gap}"))
            reasons.append(f"MISSING_INPUT:{rule}")
            continue
        passed = value < threshold
        note = None
        if abs(value - threshold) <= review_margin_pts:
            borderline = True
            note = "WITHIN_REVIEW_MARGIN"
            reasons.append(f"BORDERLINE:{rule}")
        elif not passed:
            failed = True
            reasons.append(f"FAIL:{rule}")
        results.append(RuleResult(rule, value, threshold, passed, note))

    if data.stage1_pass is None:
        reasons.insert(0, "STAGE1_UNCLASSIFIED")

    if failed:
        status = ShariahStatus.NON_COMPLIANT
    elif missing or borderline or data.stage1_pass is None:
        status = ShariahStatus.UNDER_REVIEW
    else:
        status = ShariahStatus.COMPLIANT
        reasons.append("ALL_RULES_PASSED")
    return ScreenResult(status, results, reasons)
