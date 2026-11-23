"""ACE summary: Assets, Capital and Earnings of a household on one screen (D19).

Assets are everything owned less debts (F14). Capital is the part of the assets held in
the instruments listed as `portfolio.invested_types` in `config/personal.yaml` (the same
list the invested-amount goal uses, FR19.1). Earnings are cost figures from the cost
records (F12) and income records (F27), and what is left to save.
"""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.services import income
from app.services.valuation import Portfolio, load_portfolio, personal_config

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
