"""Worked examples and properties for the market formulas (F1, F2, F3, F5, F8)."""

import math
import random
from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.analytics import regime
from app.analytics.basket import equal_weight_basket, rebase
from app.analytics.events import equal_weight_index, event_outcome
from app.analytics.regression import (
    WeeklyObs,
    confidence_for,
    default_lags,
    ols_newey_west,
    rate_sensitivity,
    weekly_sample,
)
from app.analytics.shariah import ScreenInput, average_market_cap, screen
from app.core.app_config import get_config
from app.core.trading_calendar import TradingCalendar
from app.models.enums import Confidence, ShariahStatus
from app.services.market_check import _weights

D = Decimal
SHARIAH = get_config("shariah").data
AAOIFI = SHARIAH["methods"]["aaoifi"]
SP = SHARIAH["methods"]["sp"]
MARGIN = D("2.0")


def _input(**overrides: object) -> ScreenInput:
    """Market cap 1,000: debt 100 (10%), cash 50 (5%), receivables 200 (20%),
    non-permissible income 1 of revenue 100 (1%)."""
    values: dict[str, object] = {
        "stage1_pass": True,
        "stage1_reason": "Makes cement.",
        "market_cap": D(1000),
        "total_debt_interest_bearing": D(100),
        "cash_and_interest_securities": D(50),
        "receivables": D(200),
        "total_revenue": D(100),
        "non_permissible_income": D(1),
    }
    values.update(overrides)
    return ScreenInput(**values)  # type: ignore[arg-type]


# --- F1 Shariah screen ----------------------------------------------------------------


def test_screen_all_rules_pass_fr1_2() -> None:
    result = screen(_input(), AAOIFI, MARGIN)
    assert result.status is ShariahStatus.COMPLIANT
    by_rule = {r.rule: r for r in result.ratios}
    assert by_rule["debt_to_market_cap"].value_pct == D("10.00")
    assert by_rule["debt_to_market_cap"].threshold_pct == D("30.0")
    assert by_rule["non_permissible_income_to_revenue"].value_pct == D("1.00")
    assert all(r.passed for r in result.ratios)
    # AAOIFI-style does not test receivables (PRD 7.1); S&P-style does.
    assert "receivables_to_market_cap" not in by_rule
    assert "receivables_to_market_cap" in {r.rule for r in screen(_input(), SP, MARGIN).ratios}


def test_screen_debt_above_threshold_fails() -> None:
    result = screen(_input(total_debt_interest_bearing=D(400)), AAOIFI, MARGIN)
    assert result.status is ShariahStatus.NON_COMPLIANT
    assert "FAIL:debt_to_market_cap" in result.reasons


def test_missing_input_gives_under_review_fr1_ac() -> None:
    result = screen(_input(non_permissible_income=None), AAOIFI, MARGIN)
    assert result.status is ShariahStatus.UNDER_REVIEW
    missing = next(r for r in result.ratios if r.rule == "non_permissible_income_to_revenue")
    assert missing.value_pct is None and missing.passed is None
    assert screen(_input(market_cap=None), AAOIFI, MARGIN).status is ShariahStatus.UNDER_REVIEW


@pytest.mark.parametrize("debt", [D(281), D(300), D(319)])
def test_ratio_within_review_margin_gives_under_review_fr1_ac(debt: Decimal) -> None:
    """28.1%, 30% and 31.9% are all within 2 points of the 30% threshold."""
    result = screen(_input(total_debt_interest_bearing=debt), AAOIFI, MARGIN)
    assert result.status is ShariahStatus.UNDER_REVIEW
    assert "BORDERLINE:debt_to_market_cap" in result.reasons


def test_ratio_just_outside_margin_decides() -> None:
    assert (
        screen(_input(total_debt_interest_bearing=D(279)), AAOIFI, MARGIN).status
        is ShariahStatus.COMPLIANT
    )
    assert (
        screen(_input(total_debt_interest_bearing=D(321)), AAOIFI, MARGIN).status
        is ShariahStatus.NON_COMPLIANT
    )


def test_methods_can_disagree() -> None:
    """Receivables of 55% fail S&P-style (< 49%) but AAOIFI-style does not test them."""
    data = _input(receivables=D(550))
    assert screen(data, AAOIFI, MARGIN).status is ShariahStatus.COMPLIANT
    assert screen(data, SP, MARGIN).status is ShariahStatus.NON_COMPLIANT


def test_stage1_fail_and_unclassified() -> None:
    assert screen(_input(stage1_pass=False), AAOIFI, MARGIN).status is ShariahStatus.NON_COMPLIANT
    unclassified = screen(_input(stage1_pass=None), AAOIFI, MARGIN)
    assert unclassified.status is ShariahStatus.UNDER_REVIEW
    assert unclassified.reasons[0] == "STAGE1_UNCLASSIFIED"


def test_failure_outweighs_missing_input() -> None:
    data = _input(total_debt_interest_bearing=D(500), non_permissible_income=None)
    assert screen(data, AAOIFI, MARGIN).status is ShariahStatus.NON_COMPLIANT


def test_average_market_cap() -> None:
    # Closes 10, 20, 30 average 20; 1,000 shares -> 20,000.
    assert average_market_cap([D(10), D(20), D(30)], 1000) == D("20000.00")
    assert average_market_cap([], 1000) is None
    assert average_market_cap([D(10)], None) is None


# --- F3 regression --------------------------------------------------------------------


def test_ols_exact_fit_worked_example() -> None:
    """y = 1 + 2x exactly: intercept 1, slope 2, zero standard error."""
    x = [[1.0, float(v)] for v in range(10)]
    y = [1 + 2 * float(v) for v in range(10)]
    fit = ols_newey_west(y, x, lags=0)
    assert fit.coefficients[0] == pytest.approx(1.0)
    assert fit.coefficients[1] == pytest.approx(2.0)
    assert fit.std_errors[1] == pytest.approx(0.0, abs=1e-9)


def test_ols_rejects_collinear_regressors() -> None:
    x = [[1.0, 2.0, 4.0] for _ in range(5)]
    with pytest.raises(ValueError):
        ols_newey_west([1.0] * 5, x, lags=0)


def test_default_lags_rule_of_thumb() -> None:
    assert default_lags(100) == 4
    assert default_lags(260) == 4  # 4 * 2.6^(2/9) = 4.95 -> 4


def test_confidence_thresholds_fr3_3() -> None:
    assert confidence_for(2.5, 2.5, 1.5) is Confidence.HIGH
    assert confidence_for(-2.49, 2.5, 1.5) is Confidence.MEDIUM
    assert confidence_for(1.5, 2.5, 1.5) is Confidence.MEDIUM
    assert confidence_for(1.49, 2.5, 1.5) is Confidence.LOW


def _synthetic(n: int, b: float, c: float, seed: int = 7) -> list[WeeklyObs]:
    rng = random.Random(seed)
    start = date(2020, 1, 5)
    out = []
    for i in range(n):
        dy = rng.gauss(0, 0.3)
        m = rng.gauss(0.001, 0.02)
        r = 0.0005 + b * dy + c * m + rng.gauss(0, 0.004)
        out.append(WeeklyObs(start + timedelta(weeks=i), r, dy, m))
    return out


def test_regression_recovers_known_b_fr3_ac() -> None:
    """b = -0.03 per point means -3% a week per one-point yield rise."""
    sample = _synthetic(260, b=-0.03, c=0.9)
    fit = rate_sensitivity(
        sample, with_market=True, min_weeks=104, lags=None, high_min_t=2.5, medium_min_t=1.5
    )
    assert fit.value_pct == pytest.approx(-3.0, abs=0.15)
    assert fit.confidence is Confidence.HIGH
    assert fit.n_obs == 260
    no_market = rate_sensitivity(
        sample, with_market=False, min_weeks=104, lags=None, high_min_t=2.5, medium_min_t=1.5
    )
    assert no_market.value_pct == pytest.approx(-3.0, abs=0.6)


def test_short_sample_is_insufficient_fr3_2() -> None:
    fit = rate_sensitivity(
        _synthetic(103, -0.03, 0.9),
        with_market=True,
        min_weeks=104,
        lags=None,
        high_min_t=2.5,
        medium_min_t=1.5,
    )
    assert fit.value_pct is None
    assert fit.confidence is Confidence.INSUFFICIENT
    assert fit.n_obs == 103


def _daily_series(start: date, weeks: int, calendar: TradingCalendar) -> dict[date, float]:
    days = calendar.trading_days(start, start + timedelta(weeks=weeks))
    return {d: 100.0 * math.exp(0.001 * i) for i, d in enumerate(days)}


def test_weekly_sample_uses_week_ends_and_skips_excluded_periods_fr3_ac(
    calendar: TradingCalendar,
) -> None:
    start = date(2023, 1, 1)  # a Sunday
    stock = _daily_series(start, 20, calendar)
    market = _daily_series(start, 20, calendar)
    yields = [(start + timedelta(weeks=i), 5.0 + 0.1 * i) for i in range(21)]
    full = weekly_sample(
        stock, market, yields, TradingCalendar.week_start, [], start, start + timedelta(weeks=20)
    )
    # 21 weeks of prices give 20 week-on-week returns.
    assert len(full) == 20
    assert all(o.dy == pytest.approx(0.1) for o in full)
    # Week return = 5 sessions of 0.1% each.
    assert full[0].r == pytest.approx(0.005)

    excluded = [(date(2023, 2, 5), date(2023, 2, 25))]
    cut = weekly_sample(
        stock,
        market,
        yields,
        TradingCalendar.week_start,
        excluded,
        start,
        start + timedelta(weeks=20),
    )
    # A return spans its own week and the week before, so weeks keyed 5 to 26 February touch it.
    assert not any(date(2023, 2, 5) <= o.week_start <= date(2023, 2, 26) for o in cut)
    assert len(cut) == len(full) - 4

    midweek = [(date(2023, 2, 7), date(2023, 2, 8))]
    cut = weekly_sample(
        stock,
        market,
        yields,
        TradingCalendar.week_start,
        midweek,
        start,
        start + timedelta(weeks=20),
    )
    assert {o.week_start for o in full} - {o.week_start for o in cut} == {
        date(2023, 2, 5),
        date(2023, 2, 12),
    }


def test_weekly_sample_skips_weeks_without_trading(calendar: TradingCalendar) -> None:
    start = date(2023, 1, 1)
    stock = _daily_series(start, 10, calendar)
    market = _daily_series(start, 10, calendar)
    gap_week = TradingCalendar.week_start(date(2023, 1, 22))
    stock = {d: v for d, v in stock.items() if TradingCalendar.week_start(d) != gap_week}
    yields = [(start, 5.0)]
    sample = weekly_sample(
        stock, market, yields, TradingCalendar.week_start, [], start, start + timedelta(weeks=10)
    )
    weeks = {o.week_start for o in sample}
    assert gap_week not in weeks
    assert gap_week + timedelta(weeks=1) not in weeks  # its previous week is missing


# --- F5 event metrics -----------------------------------------------------------------


def test_event_outcome_worked_example_fr5_2() -> None:
    """Base 100 on the last session before t0, then 95, 90, 98, 101, 103."""
    t0 = date(2026, 3, 1)
    closes = [
        (date(2026, 2, 25), D(99)),
        (date(2026, 2, 26), D(100)),
        (date(2026, 3, 1), D(95)),
        (date(2026, 3, 2), D(90)),
        (date(2026, 3, 3), D(98)),
        (date(2026, 3, 4), D(101)),
        (date(2026, 3, 5), D(103)),
    ]
    out = event_outcome(closes, t0, [1, 5, 20], window=60, recovery_window=250)
    assert out is not None
    assert out.returns[1] == D("-5.000000")
    assert out.returns[5] == D("3.000000")
    assert out.returns[20] is None  # data ends first
    assert out.max_drawdown == D("-10.000000")  # 100 -> 90
    assert out.sessions_to_recover == 4  # back above 100 on the 4th session


def test_event_outcome_never_fell_and_not_recovered() -> None:
    t0 = date(2026, 3, 1)
    rising = [(date(2026, 2, 26), D(100)), (date(2026, 3, 1), D(101)), (date(2026, 3, 2), D(102))]
    out = event_outcome(rising, t0, [1], 60, 250)
    assert out is not None and out.sessions_to_recover == 0 and out.max_drawdown == D(0)
    falling = [(date(2026, 2, 26), D(100)), (date(2026, 3, 1), D(90)), (date(2026, 3, 2), D(91))]
    out = event_outcome(falling, t0, [1], 60, 250)
    assert out is not None and out.sessions_to_recover is None
    assert event_outcome(falling[1:], t0, [1], 60, 250) is None  # no close before t0


def test_equal_weight_index_worked_example() -> None:
    d1, d2, d3 = date(2026, 1, 4), date(2026, 1, 5), date(2026, 1, 6)
    a = {d1: D(10), d2: D(11), d3: D(11)}  # +10%, 0%
    b = {d1: D(20), d3: D(18)}  # no trade on d2, then -10% from its last close
    out = dict(equal_weight_index([a, b], [d1, d2, d3]))
    assert out[d1] == D(100)
    assert out[d2] == D("110.0000")  # only a traded: +10%
    assert out[d3] == D("104.5000")  # mean of 0% and -10% = -5%


# --- F2 basket ------------------------------------------------------------------------


def test_basket_rebalances_monthly_worked_example() -> None:
    """Two stocks, 50 each at the start. A doubles in January; February rebalances to equal
    halves of 150, so February's +10% in B adds 7.5."""
    j1, j2, f1, f2 = date(2026, 1, 4), date(2026, 1, 25), date(2026, 2, 1), date(2026, 2, 2)
    prices = {
        "A": {j1: D(10), j2: D(20), f1: D(20), f2: D(20)},
        "B": {j1: D(5), j2: D(5), f1: D(5), f2: D("5.5")},
    }
    out = dict(equal_weight_basket(prices, [j1, j2, f1, f2]))
    assert out[j1] == D(100)
    assert out[j2] == D(150)
    assert out[f1] == D(150)
    assert out[f2] == D("157.5000")


def test_rebase_starts_at_100() -> None:
    series = [(date(2026, 1, i), D(v)) for i, v in ((1, 50), (2, 55), (3, 60))]
    assert rebase(series, date(2026, 1, 2)) == [
        (date(2026, 1, 2), D("100.00")),
        (date(2026, 1, 3), D("109.09")),
    ]


@given(st.lists(st.decimals(min_value=1, max_value=1000, places=2), min_size=2, max_size=40))
def test_single_member_basket_tracks_its_price(values: list[Decimal]) -> None:
    days = [date(2024, 1, 1) + timedelta(days=i * 3) for i in range(len(values))]
    out = equal_weight_basket({"A": dict(zip(days, values, strict=True))}, days)
    for (_, level), price in zip(out, values, strict=True):
        assert abs(level - price / values[0] * 100) < D("0.01")


# --- F6 weights -----------------------------------------------------------------------


@given(
    st.lists(st.decimals(min_value=D("0.01"), max_value=10**9, places=2), min_size=1, max_size=30)
)
def test_market_check_weights_sum_to_100_fr6_ac(values: list[Decimal]) -> None:
    assert sum(_weights(values)) == 100


# --- F8 regime ------------------------------------------------------------------------

REGIME = get_config("regime").data


def test_regime_label_worked_example_fr8_1() -> None:
    """Yield 10.0 -> 9.4 over 3 months (-0.6, easing); CPI 9.5 (high); Brent 80 -> 93
    in a month (+16.25%, shock)."""
    m = date(2026, 6, 1)
    yields = {date(2026, 3, 1): D("10.0"), m: D("9.4")}
    oil = {date(2026, 5, 1): D(80), m: D(93)}
    cpi = {m: D("9.5")}
    result = regime.classify_month(m, yields, cpi, oil, REGIME)
    assert result.label == "EASING|HIGH|SHOCK"
    assert result.components["yield_change_pts"] == "-0.60"
    assert result.components["oil_change_pct"] == "16.25"


def test_regime_flat_and_unknown_parts() -> None:
    m = date(2026, 6, 1)
    result = regime.classify_month(m, {date(2026, 3, 1): D(9), m: D("9.4")}, {}, {}, REGIME)
    assert result.label == "FLAT|UNKNOWN|UNKNOWN"
    assert regime.rate_trend(D("0.5"), REGIME["rate_trend"]) == "TIGHTENING"
    assert regime.inflation_band(D("5.99"), REGIME["inflation"]["bands"]) == "LOW"
    assert regime.inflation_band(D("6.0"), REGIME["inflation"]["bands"]) == "MODERATE"


def test_sector_stats_for_label_fr8_2() -> None:
    labels = {date(2026, 1, 1): "A", date(2026, 2, 1): "B", date(2026, 3, 1): "A"}
    returns = {"Cement": {date(2026, 1, 1): D(2), date(2026, 2, 1): D(5), date(2026, 3, 1): D(-1)}}
    [stat] = regime.sector_stats_for_label("A", labels, returns)
    assert stat.avg_monthly_return == D("0.500000")
    assert stat.hit_rate == D("50.000000")
    assert stat.n_months == 2


def test_month_end_values_and_monthly_returns() -> None:
    points = [(date(2026, 1, 5), D(10)), (date(2026, 1, 28), D(11)), (date(2026, 2, 26), D("12.1"))]
    ends = regime.month_end_values(points)
    assert ends == {date(2026, 1, 1): D(11), date(2026, 2, 1): D("12.1")}
    assert regime.monthly_returns(ends)[date(2026, 2, 1)] == D(10)
