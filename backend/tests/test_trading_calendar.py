"""DSE trading calendar: Sunday to Thursday plus holidays in config (PRD sections 7.2, 12)."""

from datetime import date, timedelta

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


def test_differences_list_quiet_sessions_and_closed_days_that_traded_d37(
    calendar: TradingCalendar,
) -> None:
    # MON has no trades (a holiday to add, or missing data); SAT traded (a special day).
    tue, wed = SUN + timedelta(days=2), SUN + timedelta(days=3)
    traded = [SUN, tue, wed, THU, SAT]
    quiet, extra = calendar.differences(traded, SUN, SAT)
    assert quiet == [MON]
    assert extra == [SAT]


def test_configured_calendar_closes_the_2020_covid_break_and_2026_holidays_d37() -> None:
    from app.core.app_config import load_config_file
    from app.core.config import get_settings

    data = load_config_file("trading_calendar", get_settings().config_dir).data
    cal = TradingCalendar.from_config(data)
    assert cal.next_trading_day(date(2020, 3, 25)) == date(2020, 5, 31)  # 66-day closure
    assert not cal.is_trading_day(date(2026, 3, 22))  # Eid-ul-Fitr
    assert not cal.is_trading_day(date(2026, 12, 16))  # Victory Day
    assert cal.is_trading_day(date(2026, 12, 17))
    # Only trading weekdays are listed; a Friday or Saturday entry would do nothing.
    assert all(d.weekday() in cal.trading_weekdays for d in cal.holidays)


def test_a_stock_that_kept_its_floor_has_its_own_excluded_period_d37() -> None:
    from app.services.market_analytics import excluded_periods

    market = excluded_periods()
    assert (date(2020, 3, 19), date(2021, 6, 17)) in market
    beximco = excluded_periods("BEXIMCO")
    assert (date(2024, 1, 19), date(2026, 6, 8)) in beximco
    assert len(beximco) == len(market) + 1
    assert excluded_periods("SQURPHARMA") == market
