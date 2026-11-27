"""DSE trading calendar: Sunday to Thursday, minus holidays (PRD sections 7.2 and 12).

All weekday and holiday rules come from config/trading_calendar.yaml. Other code must ask
this module whether a date is a session instead of checking weekdays itself.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache
from typing import Any

from app.core.app_config import ConfigError, get_config

_ONE_DAY = timedelta(days=1)
# Upper bound for searches, so a calendar with no trading weekdays cannot loop forever.
_MAX_SEARCH_DAYS = 366


def _as_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


@dataclass(frozen=True)
class TradingCalendar:
    trading_weekdays: frozenset[int]
    holidays: frozenset[date] = field(default_factory=frozenset)
    special_trading_days: frozenset[date] = field(default_factory=frozenset)

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> "TradingCalendar":
        weekdays = frozenset(int(d) for d in data.get("trading_weekdays", []))
        if not weekdays or not weekdays <= set(range(7)):
            raise ConfigError("trading_weekdays must be a non-empty list of numbers 0-6")
        return cls(
            trading_weekdays=weekdays,
            holidays=frozenset(_as_date(d) for d in data.get("holidays") or []),
            special_trading_days=frozenset(
                _as_date(d) for d in data.get("special_trading_days") or []
            ),
        )

    def is_trading_day(self, day: date) -> bool:
        if day in self.special_trading_days:
            return True
        return day.weekday() in self.trading_weekdays and day not in self.holidays

    def next_trading_day(self, day: date) -> date:
        """First session strictly after `day`."""
        return self._step(day, _ONE_DAY)

    def previous_trading_day(self, day: date) -> date:
        """Last session strictly before `day`."""
        return self._step(day, -_ONE_DAY)

    def _step(self, day: date, delta: timedelta) -> date:
        current = day
        for _ in range(_MAX_SEARCH_DAYS):
            current += delta
            if self.is_trading_day(current):
                return current
        raise ConfigError("No trading day found within a year; check trading_calendar.yaml")

    def trading_days(self, start: date, end: date) -> list[date]:
        """Sessions from `start` to `end`, both inclusive."""
        days: list[date] = []
        current = start
        while current <= end:
            if self.is_trading_day(current):
                days.append(current)
            current += _ONE_DAY
        return days

    def sessions_between(self, start: date, end: date) -> int:
        """Number of sessions after `start` up to and including `end`."""
        if end <= start:
            return 0
        return len(self.trading_days(start + _ONE_DAY, end))

    def differences(
        self, traded: Iterable[date], start: date, end: date
    ) -> tuple[list[date], list[date]]:
        """Where the calendar and the price history disagree (D37), from `start` to `end`.

        Returns the sessions with no trades (likely holidays missing from the config, or
        missing data) and the days with trades that the calendar treats as closed (likely
        special trading days, or a holiday listed by mistake).
        """
        seen = {day for day in traded if start <= day <= end}
        quiet = [day for day in self.trading_days(start, end) if day not in seen]
        extra = sorted(day for day in seen if not self.is_trading_day(day))
        return quiet, extra

    @staticmethod
    def week_start(day: date) -> date:
        """The Sunday that opens the DSE week containing `day`."""
        return day - timedelta(days=(day.weekday() + 1) % 7)

    def week_ends(self, days: Iterable[date]) -> list[date]:
        """Last date of each DSE week among `days` (PRD 7.2: weekly returns).

        Pass the dates that actually have prices, so a week cut short by a halt still
        gets its last traded day.
        """
        last_by_week: dict[date, date] = {}
        for day in days:
            key = self.week_start(day)
            if key not in last_by_week or day > last_by_week[key]:
                last_by_week[key] = day
        return sorted(last_by_week.values())


@lru_cache
def get_trading_calendar() -> TradingCalendar:
    return TradingCalendar.from_config(get_config("trading_calendar").data)
