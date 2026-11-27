"""Compare the trading calendar with the stored price history (D37).

    .venv/Scripts/python scripts/check_calendar.py [first year] [last year]

A weekday on which no DSE index level and no share price was stored, and which
`config/trading_calendar.yaml` does not list as a holiday, is printed as "no trades": either
a holiday to add, or missing data. A day with trades that the calendar treats as closed is
printed as "traded": a special trading day to add, or a holiday listed by mistake. Years in
`confirmed_years` are marked, since their holidays come from an official DSE list.
"""

import datetime as dt
import sys

from sqlalchemy import select

from app.core.app_config import get_config
from app.core.db import get_sessionmaker
from app.core.trading_calendar import get_trading_calendar
from app.models import IndexDaily, PriceDaily
from app.services.valuation import today_dhaka


def main() -> None:
    today = today_dhaka()
    first = int(sys.argv[1]) if len(sys.argv) > 1 else 2020
    last = int(sys.argv[2]) if len(sys.argv) > 2 else today.year
    calendar = get_trading_calendar()
    confirmed = set(get_config("trading_calendar").data.get("confirmed_years") or [])
    with get_sessionmaker()() as db:
        traded = set(db.scalars(select(IndexDaily.date).distinct()))
        traded |= set(db.scalars(select(PriceDaily.date).distinct()))
    if not traded:
        print("No prices stored yet; load the DSE history first.")
        return
    history_start, history_end = min(traded), max(traded)
    for year in range(first, last + 1):
        start = max(dt.date(year, 1, 1), history_start)
        end = min(dt.date(year, 12, 31), history_end, today)
        if start > end:
            print(f"{year}: no price history")
            continue
        quiet, extra = calendar.differences(traded, start, end)
        label = " (confirmed from the DSE list)" if year in confirmed else ""
        print(f"{year}{label}: {len(quiet)} without trades, {len(extra)} traded while closed")
        for day in quiet:
            print(f"  no trades  {day.isoformat()} {day:%a}")
        for day in extra:
            print(f"  traded     {day.isoformat()} {day:%a}")


if __name__ == "__main__":
    main()
