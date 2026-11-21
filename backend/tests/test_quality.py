"""Data quality checks that block publishing (PRD section 8)."""

from datetime import date
from decimal import Decimal

from app.core.trading_calendar import TradingCalendar
from app.services import quality

D = Decimal
SUN, MON, TUE, THU = date(2026, 11, 8), date(2026, 11, 9), date(2026, 11, 10), date(2026, 11, 12)


def test_missing_trading_days(calendar: TradingCalendar) -> None:
    issues = quality.check_missing_trading_days(calendar, SUN, date(2026, 11, 14), [SUN, TUE], "p")
    assert [i.day for i in issues] == [MON, date(2026, 11, 11), THU]
    assert all(i.check_name == quality.MISSING_TRADING_DAY for i in issues)


def test_duplicates() -> None:
    issues = quality.check_duplicates(["GP", "BATBC", "GP"], "p")
    assert len(issues) == 1
    assert "GP" in issues[0].detail


def test_required_fields() -> None:
    rows = [{"ticker": "GP", "close": D("1")}, {"ticker": "GP", "close": None}]
    issues = quality.check_required_fields(rows, ["ticker", "close"], "p")
    assert len(issues) == 1
    assert "Row 2" in issues[0].detail


def test_move_over_limit_is_flagged_unless_corporate_action() -> None:
    closes = [(SUN, D("100")), (MON, D("112")), (TUE, D("99"))]
    issues = quality.check_unexplained_moves("GP", closes, set(), D("10"))
    assert [(i.day, i.entity) for i in issues] == [(MON, "GP"), (TUE, "GP")]

    explained = quality.check_unexplained_moves("GP", closes, {MON, TUE}, D("10"))
    assert explained == []


def test_move_at_the_limit_passes() -> None:
    closes = [(SUN, D("100")), (MON, D("110"))]
    assert quality.check_unexplained_moves("GP", closes, set(), D("10")) == []


def test_stale_after_three_sessions(calendar: TradingCalendar) -> None:
    # Data from Sunday 8 Nov. By Wednesday 11 Nov it is 3 sessions behind; Thursday makes 4.
    assert quality.check_stale(calendar, SUN, date(2026, 11, 11), 3, "p") == []
    stale = quality.check_stale(calendar, SUN, THU, 3, "p")
    assert len(stale) == 1
    assert stale[0].check_name == quality.STALE_SOURCE
    assert len(quality.check_stale(calendar, None, THU, 3, "p")) == 1
