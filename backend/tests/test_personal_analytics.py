"""Worked examples for the personal finance formulas (PRD section 15).

Every number here can be checked by hand.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.analytics import allocation, costs, fire, returns, zakat
from app.core.app_config import get_config

D = Decimal


# --- F12 costs ------------------------------------------------------------------------


def test_monthly_rule_on_the_31st_stays_on_month_ends_fr12_2() -> None:
    due = costs.occurrences(date(2026, 1, 31), "MONTHLY", until=date(2026, 4, 30))
    assert due == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]


def test_recurring_frequencies_fr12_2() -> None:
    start = date(2026, 1, 1)
    assert costs.occurrences(start, "WEEKLY", until=date(2026, 1, 20)) == [
        date(2026, 1, 1),
        date(2026, 1, 8),
        date(2026, 1, 15),
    ]
    assert len(costs.occurrences(start, "QUARTERLY", until=date(2026, 12, 31))) == 4
    assert costs.occurrences(start, "HALF_YEARLY", until=date(2026, 12, 31))[-1] == date(2026, 7, 1)
    assert costs.occurrences(start, "YEARLY", until=date(2028, 6, 1))[-1] == date(2028, 1, 1)
    # The rule's own end date and the `since` filter both narrow the list.
    assert costs.occurrences(
        start, "MONTHLY", until=date(2026, 12, 31), end=date(2026, 3, 15), since=date(2026, 2, 1)
    ) == [date(2026, 2, 1), date(2026, 3, 1)]
    with pytest.raises(ValueError, match="recurring"):
        costs.occurrences(start, "AT_MATURITY", until=date(2026, 2, 1))


@given(
    start=st.dates(date(2020, 1, 1), date(2026, 1, 1)),
    span=st.integers(0, 800),
    frequency=st.sampled_from(sorted(costs.RECURRING_FREQUENCIES)),
)
def test_occurrences_are_increasing_and_inside_the_window(
    start: date, span: int, frequency: str
) -> None:
    until = start + timedelta(days=span)
    due = costs.occurrences(start, frequency, until=until)
    assert due[0] == start
    assert due == sorted(set(due))
    assert all(start <= d <= until for d in due)


def test_monthly_and_trailing_totals_fr12_3_fr12_4() -> None:
    entries = [
        (date(2025, 11, 12), D("400")),  # more than 12 months before, left out
        (date(2025, 11, 13), D("100")),
        (date(2026, 10, 1), D("250.50")),
        (date(2026, 10, 31), D("49.50")),
        (date(2026, 11, 12), D("1000")),
    ]
    assert costs.monthly_totals(entries) == {
        date(2025, 11, 1): D("500"),
        date(2026, 10, 1): D("300.00"),
        date(2026, 11, 1): D("1000"),
    }
    assert costs.trailing_total(entries, date(2026, 11, 12)) == D("1400.00")


def test_inflation_adjusted_view_fr12_3() -> None:
    # 12.6825% a year is 1% a month, so the index goes 100, 101, 102.01.
    yearly = D("12.682503")
    months = [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]
    index = costs.price_index(dict.fromkeys(months, yearly))
    assert [round(index[m], 2) for m in months] == [D("100"), D("101.00"), D("102.01")]
    spent = {months[0]: D("1000"), months[2]: D("1000")}
    adjusted = costs.in_prices_of(spent, index, base_month=months[2])
    assert adjusted[months[0]] == D("1020.10")  # January's spending in March prices
    assert adjusted[months[2]] == D("1000.00")


# --- F15 returns ----------------------------------------------------------------------


def test_xirr_of_a_single_year_gain_fr15_1() -> None:
    flows = [(date(2025, 1, 1), D("-1000")), (date(2026, 1, 1), D("1100"))]
    assert returns.xirr(flows) == D("10.000000")


def test_xirr_with_income_along_the_way_fr25_3() -> None:
    # 1,000 in; 100 back after one year; 1,100 back after two: exactly 10% a year.
    flows = [
        (date(2024, 1, 1), D("-1000")),
        (date(2024, 12, 31), D("100")),
        (date(2025, 12, 31), D("1100")),
    ]
    assert abs(returns.xirr(flows) - D("10")) < D("0.001")  # type: ignore[operator]


def test_xirr_has_no_answer_without_both_signs_or_two_dates() -> None:
    assert returns.xirr([(date(2025, 1, 1), D("-1000"))]) is None
    assert returns.xirr([(date(2025, 1, 1), D("-1")), (date(2026, 1, 1), D("-1"))]) is None
    assert returns.xirr([(date(2025, 1, 1), D("-1")), (date(2025, 1, 1), D("2"))]) is None


@given(rate=st.floats(-0.5, 2.0), days=st.integers(30, 3000), amount=st.integers(100, 10**9))
def test_xirr_recovers_a_known_rate(rate: float, days: int, amount: int) -> None:
    start = date(2020, 1, 1)
    final = amount * (1 + rate) ** (days / 365)
    result = returns.xirr([(start, D(-amount)), (start + timedelta(days=days), D(str(final)))])
    assert result is not None
    assert abs(float(result) / 100 - rate) < 1e-4


def test_time_weighted_return_ignores_the_size_of_deposits_fr15_1() -> None:
    # Day 1: 100 grows to 110. Day 2: 110 grows to 121, then 79 is added (end value 200).
    day1 = returns.daily_return(D("100"), D("110"))
    day2 = returns.daily_return(D("110"), D("200"), net_flow=D("79"))
    assert round(day1, 10) == round(day2, 10) == 0.1
    assert round(returns.link_returns([day1, day2]), 10) == 0.21
    assert returns.annualise(0.21, 730) == pytest.approx(0.1)
    assert returns.annualise(0.05, 10) is None  # too short to state as a yearly rate


def test_portfolio_day_return_from_holdings() -> None:
    # 600 of a share that rose 2% and 400 of one that fell 1%, plus a 10 dividend.
    result = returns.weighted_return([(D("600"), 0.02), (D("400"), -0.01)], income=D("10"))
    assert result == pytest.approx((12 - 4 + 10) / 1000)
    assert returns.weighted_return([]) == 0.0


def test_volatility_and_drawdown_prd_7_2() -> None:
    weekly = [0.01, -0.01, 0.01, -0.01]
    # Sample standard deviation is 0.011547; times the square root of 52 is 0.083267.
    assert returns.annualised_volatility(weekly) == pytest.approx(0.083267, abs=1e-6)
    assert returns.annualised_volatility([0.01]) is None
    assert returns.max_drawdown([100, 120, 90, 130]) == pytest.approx(-0.25)
    assert returns.max_drawdown([1, 2, 3]) == 0.0
    assert returns.growth_index([0.1, -0.5]) == pytest.approx([110, 55])


def test_diversification_measures_fr15_3() -> None:
    assert returns.herfindahl([D("50"), D("50")]) == D("0.5000")
    assert returns.herfindahl([D("100")]) == D("1.0000")
    assert returns.top_weight([D("40"), D("30"), D("20"), D("10")], n=2) == D("70.00")
    assert returns.top_weight([]) == D("0")


def test_realised_gain_uses_average_cost_fr13_6() -> None:
    trades = [
        returns.Trade(date(2025, 1, 5), "BUY", D("1000"), D("100")),  # Tk 10 each
        returns.Trade(date(2025, 3, 5), "BUY", D("2000"), D("100")),  # Tk 20 each: average 15
        returns.Trade(date(2025, 6, 1), "SELL", D("1000"), D("50")),  # basis 750
        returns.Trade(date(2025, 7, 1), "BONUS", D("0"), D("150")),  # 300 units, cost 2,250
        returns.Trade(date(2025, 9, 1), "SELL", D("3000"), D("300")),
    ]
    assert returns.realised_gains(trades) == [
        (date(2025, 6, 1), D("250.00")),
        (date(2025, 9, 1), D("750.00")),
    ]


# --- F13 Zakat ------------------------------------------------------------------------

ZAKAT = get_config("zakat").data


def _household() -> list[zakat.ZakatAsset]:
    return [
        zakat.ZakatAsset("Cash", "cash", D("500000")),
        zakat.ZakatAsset("Shares", "dse_share", D("400000"), zakatable_assets_value=D("150000")),
        zakat.ZakatAsset(
            "FDR", "fdr", D("220000"), principal=D("200000"), is_interest_bearing=True
        ),
        zakat.ZakatAsset("Family home", "family_home", D("8500000")),
    ]


def test_zakat_gold_nisab_fr13_2() -> None:
    """Cash 500,000 + shares 400,000 + FDR principal 200,000 - debt 100,000 = 1,000,000."""
    result = zakat.compute_zakat(
        _household(),
        [zakat.ZakatDebt("Loan instalments", D("100000"))],
        config=ZAKAT,
        nisab_basis="GOLD",
        price_per_gram=D("10000"),
    )
    assert result.nisab_value == D("874800.00")  # 87.48 g x 10,000
    assert result.total_zakatable == D("1100000.00")
    assert result.total_deductions == D("100000.00")
    assert result.net_zakatable == D("1000000.00")
    assert result.above_nisab
    assert result.zakat_due == D("25000.00")  # 2.5%
    by_label = {line.label: line for line in result.lines}
    assert by_label["Family home"].zakatable == 0
    assert by_label["FDR"].zakatable == D("200000.00")
    assert by_label["FDR"].flags == (zakat.FLAG_INTEREST_EXCLUDED,)


def test_zakat_silver_nisab_and_below_nisab_fr13_2() -> None:
    small = [zakat.ZakatAsset("Cash", "cash", D("90000"))]
    silver = zakat.compute_zakat(
        small, [], config=ZAKAT, nisab_basis="SILVER", price_per_gram=D("150")
    )
    assert silver.nisab_value == D("91854.00")  # 612.36 g x 150
    assert not silver.above_nisab and silver.zakat_due == 0
    more = [zakat.ZakatAsset("Cash", "cash", D("100000"))]
    due = zakat.compute_zakat(more, [], config=ZAKAT, nisab_basis="SILVER", price_per_gram=D("150"))
    assert due.zakat_due == D("2500.00")
    # The same wealth is under the gold nisab.
    gold = zakat.compute_zakat(
        more, [], config=ZAKAT, nisab_basis="GOLD", price_per_gram=D("10000")
    )
    assert gold.zakat_due == 0


def test_zakat_share_methods_fr13_3() -> None:
    kwargs = {"config": ZAKAT, "nisab_basis": "SILVER", "price_per_gram": D("150")}
    market = zakat.compute_zakat(_household(), [], shares_method="MARKET_VALUE", **kwargs)  # type: ignore[arg-type]
    assets = zakat.compute_zakat(_household(), [], shares_method="ZAKATABLE_ASSETS", **kwargs)  # type: ignore[arg-type]
    assert market.total_zakatable - assets.total_zakatable == D("250000.00")  # 400,000 vs 150,000
    # No company figures: the market value is used and the line says so.
    unknown = [zakat.ZakatAsset("Shares", "dse_share", D("400000"))]
    fallback = zakat.compute_zakat(unknown, [], shares_method="ZAKATABLE_ASSETS", **kwargs)  # type: ignore[arg-type]
    assert fallback.lines[0].zakatable == D("400000.00")
    assert fallback.lines[0].flags == (zakat.FLAG_MARKET_VALUE_FALLBACK,)


def test_zakat_per_asset_rules_and_owner_share_fr13_4_fr13_7() -> None:
    assets = [
        zakat.ZakatAsset("Gold", "gold", D("720000"), owner_pct=D("50")),
        zakat.ZakatAsset("Sukuk", "sukuk", D("100000"), profit_received=D("19200")),
        zakat.ZakatAsset("Loan to cousin", "private_loan_given", D("150000"), is_recoverable=False),
        zakat.ZakatAsset("Rental flat", "rental_property", D("5800000")),
        zakat.ZakatAsset("Farm stake", "business_stake", D("460000")),
        zakat.ZakatAsset("Mystery", "not_a_rule", D("1000")),
    ]
    result = zakat.compute_zakat(
        assets,
        [zakat.ZakatDebt("Home loan", D("240000"), owner_pct=D("50"))],
        config=ZAKAT,
        nisab_basis="SILVER",
        price_per_gram=D("150"),
    )
    zakatable = {line.label: line.zakatable for line in result.lines}
    assert zakatable == {
        "Gold": D("360000.00"),  # half of it is this person's
        "Sukuk": D("119200.00"),  # value plus profit received
        "Loan to cousin": D("0.00"),
        "Rental flat": D("0.00"),
        "Farm stake": D("460000.00"),
        "Mystery": D("1000.00"),
    }
    flags = {line.label: line.flags for line in result.lines}
    assert flags["Loan to cousin"] == (zakat.FLAG_NOT_RECOVERABLE,)
    assert flags["Farm stake"] == (zakat.FLAG_MARKET_VALUE_FALLBACK,)
    assert flags["Mystery"] == (zakat.FLAG_NO_RULE,)
    assert result.total_deductions == D("120000.00")


@given(cash=st.integers(0, 10**10), debt=st.integers(0, 10**10))
def test_zakat_is_never_negative_and_never_above_the_rate(cash: int, debt: int) -> None:
    result = zakat.compute_zakat(
        [zakat.ZakatAsset("Cash", "cash", D(cash))],
        [zakat.ZakatDebt("Debt", D(debt))],
        config=ZAKAT,
        nisab_basis="GOLD",
        price_per_gram=D("10000"),
    )
    assert result.zakat_due >= 0
    assert result.zakat_due <= D(cash) * D("0.025") + D("0.01")
    assert (result.zakat_due > 0) == (result.net_zakatable >= result.nisab_value)


# --- F17 and F18 FIRE -----------------------------------------------------------------


def _inputs(**changes: Decimal) -> fire.FireInputs:
    values = {
        "net_worth": D("1000000"),
        "monthly_savings": D("100000"),
        "yearly_expenses": D("600000"),
        "nominal_return_pct": D("10"),
        "inflation_pct": D("10"),  # real return is zero, so the sums are simple
        "withdrawal_rate_pct": D("4"),
        "current_age": D("30"),
    }
    return fire.FireInputs(**{**values, **changes})


def test_fire_number_and_real_return_fr17_2() -> None:
    assert fire.fire_number(D("600000"), D("4")) == D("15000000.00")
    assert round(fire.real_return(D("10"), D("5")), 6) == D("0.047619")
    with pytest.raises(ValueError, match="above zero"):
        fire.fire_number(D("600000"), D("0"))


def test_fire_age_with_zero_real_return_fr17_3() -> None:
    """14,000,000 more is needed at 100,000 a month: 140 months, so age 41.67."""
    result = fire.project(_inputs())
    assert result.fire_number == D("15000000.00")
    assert result.fire_age == D("41.67")
    assert result.path[0] == fire.YearPoint(0, D("30"), D("1000000.00"))
    assert result.path[1].net_worth == D("2200000.00")
    assert len(result.path) == 71  # one point a year to age 100
    assert result.worst_year_net_worth == D("1000000.00")


def test_fire_with_growth_reaches_the_number_sooner() -> None:
    growing = fire.project(_inputs(inflation_pct=D("5")))
    assert growing.fire_age is not None and growing.fire_age < D("41.67")
    assert growing.real_return_pct == D("4.7619")
    already = fire.project(_inputs(net_worth=D("20000000")))
    assert already.fire_age == D("30")
    never = fire.project(_inputs(monthly_savings=D("0"), net_worth=D("1000")))
    assert never.fire_age is None


def test_scenario_market_crash_fr18() -> None:
    """After 12 months: 2,200,000. A 20% fall leaves 1,760,000; 133 more months are needed."""
    base = fire.project(_inputs())
    crash = fire.run_scenario(_inputs(), "MARKET_CRASH", {"fall_pct": D("20")}, base)
    assert crash.fire_age == D("42.08")  # 145 months
    assert crash.path[1].net_worth == D("1760000.00")
    # Only half the money is in the market: the fall is 10% of net worth.
    half = fire.run_scenario(
        _inputs(), "EVENT_REPLAY", {"fall_pct": D("20"), "market_share_pct": D("50")}, base
    )
    assert half.path[1].net_worth == D("1980000.00")


def test_scenario_expenses_inflation_and_early_retirement_fr18() -> None:
    base = fire.project(_inputs())
    dearer = fire.run_scenario(_inputs(), "EXPENSES_UP", {"pct": D("10")}, base)
    assert dearer.fire_number == D("16500000.00")
    assert dearer.fire_age == D("42.92")  # 155 months
    shock = fire.run_scenario(_inputs(), "INFLATION_SHOCK", {"points": D("3")}, base)
    assert shock.fire_age is not None and shock.fire_age > base.fire_age  # type: ignore[operator]
    early = fire.run_scenario(_inputs(), "RETIRE_EARLIER", {"years": D("5")}, base)
    assert early.fire_age == D("36.67")
    # 80 months of saving gives 9,000,000. Spent at 600,000 a year with no real growth,
    # it lasts 15 years.
    assert early.depleted_age == D("51.67")
    assert early.worst_year_net_worth == 0
    with pytest.raises(ValueError, match="Unknown"):
        fire.run_scenario(_inputs(), "NOPE", {}, base)


# --- F16 allocation and F26 fixed income ----------------------------------------------


def test_weights_sum_to_100_fr16_1() -> None:
    result = allocation.weights([("EQUITY", D("300")), ("CASH", D("100")), ("EQUITY", D("100"))])
    assert result == {"EQUITY": (D("400.00"), D("80.00")), "CASH": (D("100.00"), D("20.00"))}
    assert allocation.weights([]) == {}


def test_drift_from_target_fr16_2() -> None:
    actual = {"EQUITY": D("600000"), "CASH": D("400000")}
    targets = {"EQUITY": (D("50"), D("5")), "CASH": (D("45"), D("10")), "GOLD": (D("5"), D("2"))}
    rows = {row.asset_class: row for row in allocation.drift(actual, targets)}
    assert rows["EQUITY"].drift_pts == D("10.00") and rows["EQUITY"].outside_band
    assert rows["EQUITY"].difference == D("100000.00")  # above its target share
    assert rows["CASH"].drift_pts == D("-5.00") and not rows["CASH"].outside_band
    assert rows["GOLD"].difference == D("-50000.00") and rows["GOLD"].outside_band
    assert sum(row.difference for row in rows.values()) == 0


def test_fixed_income_sums_fr26() -> None:
    year = (date(2026, 1, 1), date(2027, 1, 1))
    assert allocation.expected_profit(D("100000"), D("9.6"), *year) == D("9600.00")
    assert allocation.expected_profit(D("100000"), D("9.6"), year[1], year[0]) == 0
    assert allocation.real_rate_pct(D("9.6"), D("5")) == D("4.38")
    assert allocation.real_rate_pct(D("5"), D("9")) == D("-3.67")


def test_gold_is_valued_by_weight_and_purity_fr25_2() -> None:
    assert allocation.metal_value(D("80"), D("9000"), 22, 22) == D("720000.00")
    assert allocation.metal_value(D("22"), D("9000"), 21, 22) == D("189000.00")
    assert allocation.metal_value(D("100"), D("150"), None, None) == D("15000.00")


def test_annualised_costs_scale_a_partial_year_fr12_4() -> None:
    """One month of 85,000 is 10,20,000 a year; three months totalling 2,40,000 average
    80,000, so 9,60,000; a full year is kept as recorded."""
    assert costs.annualised(D("85000"), 1) == D("1020000.00")
    assert costs.annualised(D("240000"), 3) == D("960000.00")
    assert costs.annualised(D("1000000"), 12) == D("1000000.00")
    assert costs.annualised(D("0"), 0) == D("0")
