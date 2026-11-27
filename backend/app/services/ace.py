"""ACE summary: Assets, Capital and Earnings of a household on one screen (D19).

Assets are everything owned less debts (F14). Capital is the part of the assets held in
the instruments listed as `portfolio.invested_types` in `config/personal.yaml` (the same
list the invested-amount goal uses, FR19.1). Earnings are cost figures from the cost
records (F12) and income records (F27), and what is left to save.
"""

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics import costs as formulas
from app.models import NetWorthSnapshot
from app.services import income
from app.services.valuation import Portfolio, load_portfolio, personal_config, today_dhaka

Q2 = Decimal("0.01")
HUNDRED = Decimal(100)


def capital_at_work(portfolio: Portfolio) -> Decimal:
    """Household value of the holdings that count as invested."""
    invested = set(personal_config()["portfolio"]["invested_types"])  # type: ignore[index]
    return sum(
        (p.household_value for p in portfolio.positions if p.type in invested), Decimal(0)
    ).quantize(Q2)


def ace_summary(db: Session, household_id: uuid.UUID) -> tuple[dict[str, Any], set[uuid.UUID]]:
    portfolio = load_portfolio(db, household_id)
    capital = capital_at_work(portfolio)
    assets = portfolio.assets
    earned = income.summary(db, household_id, months=12)
    data = {
        "assets": {
            "total": assets,
            "liabilities": portfolio.liabilities,
            "net_worth": portfolio.net_worth,
        },
        "capital": {
            "at_work": capital,
            "share_of_assets_pct": (capital / assets * HUNDRED).quantize(Q2)
            if assets > 0
            else None,
        },
        "earnings": {
            "income_trailing_12_months": earned.income_12m,
            "costs_trailing_12_months": earned.costs_12m,
            "savings_trailing_12_months": earned.savings_12m,
            "savings_rate_pct": earned.savings_rate_pct,
            "average_monthly_income": earned.average_monthly_income,
            "average_monthly_cost": (
                (earned.costs_12m / earned.months_counted).quantize(Q2)
                if earned.months_counted
                else None
            ),
            "average_monthly_savings": earned.average_monthly_savings,
            "months_counted": earned.months_counted,
        },
    }
    return data, portfolio.source_ids


def trend(
    db: Session, household_id: uuid.UUID, *, months: int = 12, as_of: dt.date | None = None
) -> dict[str, Any]:
    """Assets, Capital and Earnings month by month (D23).

    Net worth and capital at work come from the last stored snapshot in each month, so a
    month with no snapshot has none (the daily job stores one; older snapshots have no
    capital). Income, costs and savings come from the records. `change` compares the first
    and last months that have a value. Without any income records in the period, income and
    savings are left empty.
    """
    as_of = as_of or today_dhaka()
    first = formulas.month_start(formulas.add_months(as_of, -(months - 1)))
    snapshots = db.scalars(
        select(NetWorthSnapshot)
        .where(
            NetWorthSnapshot.household_id == household_id,
            NetWorthSnapshot.date >= first,
            NetWorthSnapshot.date <= as_of,
        )
        .order_by(NetWorthSnapshot.date)
    )
    last_in_month: dict[dt.date, NetWorthSnapshot] = {}
    for snap in snapshots:
        last_in_month[formulas.month_start(snap.date)] = snap
    earned = {
        m["month"]: m for m in income.summary(db, household_id, months=months, as_of=as_of).months
    }
    # With no income recorded in the whole period, income is unknown, not zero: a month's
    # costs alone would read as a loss. Once any month has income, a month without it is a
    # real shortfall and is shown as one.
    income_known = any(m["income"] > 0 for m in earned.values())

    rows: list[dict[str, Any]] = []
    for index in range(months):
        month = formulas.add_months(first, index)
        found = last_in_month.get(month)
        flows = earned.get(month)
        money_in = flows["income"] if flows and income_known else None
        rows.append(
            {
                "month": month,
                "snapshot_date": found.date if found else None,
                "net_worth": found.net_worth if found else None,
                "assets": found.assets if found else None,
                "capital": found.capital if found else None,
                "capital_share_pct": (found.capital / found.assets * HUNDRED).quantize(Q2)
                if found and found.capital is not None and found.assets > 0
                else None,
                "income": money_in,
                "costs": flows["costs"] if flows else None,
                "savings": flows["savings"] if flows and income_known else None,
                "savings_rate_pct": (flows["savings"] / money_in * HUNDRED).quantize(Q2)
                if flows and money_in and money_in > 0
                else None,
            }
        )

    def change(key: str) -> Decimal | None:
        values = [r[key] for r in rows if r[key] is not None]
        return (values[-1] - values[0]).quantize(Q2) if len(values) >= 2 else None

    saved = [r["savings"] for r in rows if r["savings"] is not None]
    return {
        "months": rows,
        "change": {
            "net_worth": change("net_worth"),
            "capital": change("capital"),
            "savings_total": sum(saved, Decimal(0)).quantize(Q2) if saved else None,
        },
    }
