"""Back-adjustment for bonus, rights and splits (PRD 7.2), with worked examples."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.analytics.adjustment import Action, adjustment_factor, back_adjust
from app.models import CorporateActionType as T

D = Decimal
D1, D2, D3, D4 = (date(2026, 1, n) for n in (4, 5, 6, 7))


def test_no_actions_leaves_prices_unchanged() -> None:
    closes = [(D2, D("101.5")), (D1, D("100"))]
    assert back_adjust(closes, []) == [(D1, D("100.0000")), (D2, D("101.5000"))]


def test_bonus_10_percent() -> None:
    # 10% stock dividend: 110 before the ex-date is worth 100 in today's shares.
    out = back_adjust([(D1, D("110")), (D2, D("100"))], [Action(D2, T.BONUS, D("0.10"))])
    assert out == [(D1, D("100.0000")), (D2, D("100.0000"))]


def test_split_one_into_ten() -> None:
    out = back_adjust([(D1, D("1000")), (D2, D("102"))], [Action(D2, T.SPLIT, D("10"))])
    assert out == [(D1, D("100.0000")), (D2, D("102.0000"))]


def test_rights_one_for_two_at_par() -> None:
    # Close 40, 1 right per 2 held at Tk 10: TERP = (40 + 0.5 * 10) / 1.5 = 30, factor 0.75.
    action = Action(D2, T.RIGHTS, D("0.5"), D("10"))
    assert adjustment_factor(action, D("40")) == D("0.75")
    out = back_adjust([(D1, D("40")), (D2, D("30"))], [action])
    assert out == [(D1, D("30.0000")), (D2, D("30.0000"))]


def test_actions_compound_backwards() -> None:
    closes = [(D1, D("400")), (D2, D("200")), (D3, D("100")), (D4, D("100"))]
    actions = [Action(D2, T.SPLIT, D("2")), Action(D3, T.BONUS, D("1"))]
    assert [p for _, p in back_adjust(closes, actions)] == [D("100.0000")] * 4


def test_cash_dividend_does_not_adjust() -> None:
    out = back_adjust([(D1, D("50")), (D2, D("48"))], [Action(D2, T.CASH_DIVIDEND, None, D("2"))])
    assert out == [(D1, D("50.0000")), (D2, D("48.0000"))]


def test_action_outside_the_price_range_is_ignored() -> None:
    closes = [(D2, D("50")), (D3, D("51"))]
    before_first = Action(D2, T.SPLIT, D("2"))
    not_yet_happened = Action(D4, T.SPLIT, D("2"))
    assert back_adjust(closes, [before_first, not_yet_happened]) == [
        (D2, D("50.0000")),
        (D3, D("51.0000")),
    ]


def test_invalid_inputs_raise() -> None:
    with pytest.raises(ValueError, match="positive ratio"):
        adjustment_factor(Action(D2, T.BONUS, D("0")), D("10"))
    with pytest.raises(ValueError, match="issue price"):
        adjustment_factor(Action(D2, T.RIGHTS, D("0.5")), D("10"))
    with pytest.raises(ValueError, match="duplicate"):
        back_adjust([(D1, D("1")), (D1, D("2"))], [])


@given(
    prices=st.lists(st.decimals("1", "5000", places=2), min_size=3, max_size=30),
    split_at=st.integers(min_value=1, max_value=29),
    ratio=st.integers(min_value=2, max_value=20),
)
def test_property_split_keeps_latest_price_and_scales_earlier_ones(
    prices: list[Decimal], split_at: int, ratio: int
) -> None:
    """After a split, prices from the ex-date on are untouched and earlier ones divide by r."""
    split_at = min(split_at, len(prices) - 1)
    closes = [(date(2025, 1, 1) + timedelta(days=i), p) for i, p in enumerate(prices)]
    ex_date = closes[split_at][0]
    out = back_adjust(closes, [Action(ex_date, T.SPLIT, D(ratio))])
    for (day, raw), (_, adj) in zip(closes, out, strict=True):
        expected = raw / ratio if day < ex_date else raw
        assert adj == expected.quantize(D("0.0001"))
