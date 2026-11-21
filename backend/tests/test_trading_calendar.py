"""DSE trading calendar: Sunday to Thursday plus holidays in config (PRD sections 7.2, 12)."""

from datetime import date

import pytest

from app.core.app_config import ConfigError
from app.core.trading_calendar import TradingCalendar, get_trading_calendar

# November 2026: the 8th is a Sunday, the 12th a Thursday, the 13th a Friday.
SUN, MON, THU, FRI, SAT = (
    date(2026, 11, 8),
    date(2026, 11, 9),
    date(2026, 11, 12),
    date(2026, 11, 13),
    date(2026, 11, 14),
)
NEXT_SUN = date(2026, 11, 15)


def test_sunday_to_thursday_are_sessions(calendar: TradingCalendar) -> None:
    assert calendar.is_trading_day(SUN)
    assert calendar.is_trading_day(THU)
    assert not calendar.is_trading_day(FRI)
    assert not calendar.is_trading_day(SAT)


def test_holiday_and_special_day_override_the_weekday() -> None:
    cal = TradingCalendar.from_config(
        {
            "trading_weekdays": [6, 0, 1, 2, 3],
            "holidays": ["2026-11-09"],
            "special_trading_days": [SAT],
        }
    )
    assert not cal.is_trading_day(MON)
    assert cal.is_trading_day(SAT)
    assert cal.next_trading_day(SUN) == date(2026, 11, 10)


def test_next_and_previous_skip_the_weekend(calendar: TradingCalendar) -> None:
    assert calendar.next_trading_day(THU) == NEXT_SUN
    assert calendar.previous_trading_day(NEXT_SUN) == THU
    assert calendar.previous_trading_day(SAT) == THU


def test_trading_days_and_session_count(calendar: TradingCalendar) -> None:
    assert len(calendar.trading_days(SUN, NEXT_SUN)) == 6
    assert calendar.sessions_between(THU, NEXT_SUN) == 1
    assert calendar.sessions_between(SUN, THU) == 4
    assert calendar.sessions_between(THU, SUN) == 0


def test_week_starts_on_sunday() -> None:
    assert TradingCalendar.week_start(SUN) == SUN
    assert TradingCalendar.week_start(THU) == SUN
    assert TradingCalendar.week_start(SAT) == SUN
    assert TradingCalendar.week_start(NEXT_SUN) == NEXT_SUN


def test_week_ends_use_last_day_with_data(calendar: TradingCalendar) -> None:
    """PRD 7.2: weekly returns use the last trading day of each week."""
    # First week has no Thursday price, so Wednesday closes the week.
    days = [SUN, MON, date(2026, 11, 11), NEXT_SUN, date(2026, 11, 19)]
    assert calendar.week_ends(days) == [date(2026, 11, 11), date(2026, 11, 19)]


def test_empty_weekdays_are_rejected() -> None:
    with pytest.raises(ConfigError):
        TradingCalendar.from_config({"trading_weekdays": []})


def test_repo_calendar_config_loads() -> None:
    cal = get_trading_calendar()
    assert cal.is_trading_day(SUN)
    assert not cal.is_trading_day(FRI)
