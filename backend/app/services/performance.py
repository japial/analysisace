"""Performance (F15) and allocation with drift (F16).

Returns describe what happened to the household's own holdings. Nothing here suggests what
to hold: targets are the person's own, and drift is reported as a distance (FR16.2).

Performance is worked out on request from stored prices and transactions. That is light
for a household's handful of holdings; if it ever is not, store the result per day the
way net worth is stored.
"""

import datetime as dt
import itertools
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.analytics import allocation as allocation_formulas
from app.analytics import returns
from app.core.trading_calendar import get_trading_calendar
from app.models import IndexDaily, MacroSeries, PriceDaily, TargetAllocation, Transaction
from app.services.auth import AuthError
from app.services.valuation import Portfolio, Position, load_portfolio, personal_config

Q2 = Decimal("0.01")
HUNDRED = Decimal(100)
PERIODS = {"1Y": 365, "3Y": 365 * 3, "5Y": 365 * 5}


def _pct(value: float | None) -> Decimal | None:
    return None if value is None else Decimal(str(value * 100)).quantize(Q2)


# --- daily return series --------------------------------------------------------------


@dataclass
class Series:
    days: list[dt.date] = field(default_factory=list)
    daily: list[float] = field(default_factory=list)  # one return per day in `days`


def _units_by_day(
    transactions: list[Transaction], position: Position
) -> list[tuple[dt.date, Decimal]]:
    """(date, change in units) from the transaction record, oldest first.

    A holding with no unit transactions is taken as held in full since its start date.
    """
    changes = [
        (t.date, (t.units or Decimal(0)) * (-1 if t.type == "SELL" else 1))
        for t in sorted(transactions, key=lambda t: t.date)
        if t.type in ("BUY", "SELL", "BONUS")
    ]
    holding = position.holding
    assert holding is not None
    if not changes:
        changes = [(holding.start_date or dt.date.min, holding.quantity)]
    return changes


def market_series(
    db: Session, positions: list[Position], since: dt.date | None, until: dt.date
) -> Series:
    """Daily time-weighted returns of the listed holdings among `positions` (FR15.1).

    Each day's return is the holdings' own returns weighted by their value at the previous
    close. Adjusted prices are used for the returns, so a bonus issue or split is not read
    as a loss; cash dividends recorded on a holding are added on the day received.
    """
    listed = [p for p in positions if p.method == "MARKET_PRICE" and p.holding and p.ticker]
    if not listed:
        return Series()
    tickers = {p.ticker for p in listed if p.ticker}
    prices: dict[str, dict[dt.date, tuple[Decimal, Decimal]]] = defaultdict(dict)
    for row in db.execute(
        select(PriceDaily.ticker, PriceDaily.date, PriceDaily.close, PriceDaily.adj_close).where(
            PriceDaily.ticker.in_(tickers), PriceDaily.date <= until
        )
    ):
        prices[row.ticker][row.date] = (row.close, row.adj_close or row.close)

    by_holding: dict[uuid.UUID, list[Transaction]] = defaultdict(list)
    for txn in db.scalars(
        select(Transaction).where(Transaction.holding_id.in_([p.id for p in listed]))
    ):
        by_holding[txn.holding_id].append(txn)

    changes = {p.id: _units_by_day(by_holding[p.id], p) for p in listed}
    dividends: dict[dt.date, Decimal] = defaultdict(Decimal)
    for txns in by_holding.values():
        for txn in txns:
            if txn.type == "DIVIDEND":
                dividends[txn.date] += txn.amount

    first_held = min(day for moves in changes.values() for day, _ in moves)
    days = sorted({d for series in prices.values() for d in series if d >= first_held})
    series = Series()
    units = dict.fromkeys(changes, Decimal(0))
    cursor = dict.fromkeys(changes, 0)
    previous: dt.date | None = None
    for day in days:
        if previous is not None:
            weighted: list[tuple[Decimal, float]] = []
            for position in listed:
                assert position.ticker is not None
                then = prices[position.ticker].get(previous)
                now = prices[position.ticker].get(day)
                held = units[position.id]
                if then is None or now is None or held <= 0 or then[1] <= 0:
                    continue
                weighted.append((held * then[0], float(now[1] / then[1]) - 1))
            if weighted and (since is None or day >= since):
                series.days.append(day)
                series.daily.append(
                    returns.weighted_return(weighted, dividends.get(day, Decimal(0)))
                )
        # Purchases and sales take effect at the close of their day.
        for holding_id, moves in changes.items():
            while cursor[holding_id] < len(moves) and moves[cursor[holding_id]][0] <= day:
                units[holding_id] += moves[cursor[holding_id]][1]
                cursor[holding_id] += 1
        previous = day
    return series


def _weekly(series: Series) -> tuple[list[dt.date], list[float]]:
    """Growth level at the last traded day of each DSE week (PRD 7.2)."""
    levels = dict(zip(series.days, returns.growth_index(series.daily), strict=True))
    ends = get_trading_calendar().week_ends(series.days)
    return ends, [levels[day] for day in ends]


def _money_weighted(db: Session, positions: list[Position], today: dt.date) -> Decimal | None:
    """XIRR over the holdings: money in is negative, money out and today's value positive."""
    holdings = [p for p in positions if p.holding is not None]
    if not holdings:
        return None
    flows: list[tuple[dt.date, Decimal]] = []
    recorded: dict[uuid.UUID, list[Transaction]] = defaultdict(list)
    for txn in db.scalars(
        select(Transaction).where(Transaction.holding_id.in_([p.id for p in holdings]))
    ):
        recorded[txn.holding_id].append(txn)
    for position in holdings:
        holding = position.holding
        assert holding is not None
        txns = recorded.get(holding.id, [])
        for txn in txns:
            sign = -1 if txn.type in ("BUY", "DEPOSIT", "FEE", "TAX") else 1
            if txn.type != "BONUS":
                flows.append((txn.date, txn.amount * sign))
        if not txns:
            # Entered as a balance: one payment in, and what it has paid out so far.
            flows.append((holding.start_date or today, -holding.cost))
            flows.append((today, holding.profit_received - holding.tax_deducted))
        flows.append((today, position.value))
    return returns.xirr(flows)


def _index_return(
    db: Session, code: str, start: dt.date, end: dt.date
) -> tuple[Decimal | None, Decimal | None, set[uuid.UUID], list[tuple[dt.date, Decimal]]]:
    rows = db.execute(
        select(IndexDaily.date, IndexDaily.close, IndexDaily.source_id)
        .where(IndexDaily.index_code == code, IndexDaily.date >= start, IndexDaily.date <= end)
        .order_by(IndexDaily.date)
    ).all()
    if len(rows) < 2 or rows[0].close <= 0:
        return None, None, set(), []
    total = float(rows[-1].close / rows[0].close) - 1
    yearly = returns.annualise(total, (rows[-1].date - rows[0].date).days)
    levels = [(row.date, row.close) for row in rows]
    return _pct(total), _pct(yearly), {rows[0].source_id, rows[-1].source_id}, levels


def _measure(
    db: Session, positions: list[Position], since: dt.date | None, today: dt.date
) -> tuple[dict[str, Any], Series]:
    series = market_series(db, positions, since, today)
    stats: dict[str, Any] = {
        "start": series.days[0] if series.days else None,
        "end": series.days[-1] if series.days else None,
        "twr_pct": None,
        "twr_annualised_pct": None,
        "volatility_pct": None,
        "max_drawdown_pct": None,
        "xirr_pct": _money_weighted(db, positions, today),
        "value": sum((p.household_value for p in positions if p.holding), Decimal(0)),
    }
    if series.days:
        total = returns.link_returns(series.daily)
        span = (series.days[-1] - series.days[0]).days
        _, levels = _weekly(series)
        weekly = [b / a - 1 for a, b in itertools.pairwise(levels)]
        stats["twr_pct"] = _pct(total)
        stats["twr_annualised_pct"] = _pct(returns.annualise(total, span))
        stats["volatility_pct"] = _pct(returns.annualised_volatility(weekly))
        stats["max_drawdown_pct"] = _pct(returns.max_drawdown(returns.growth_index(series.daily)))
    return stats, series


def performance(
    db: Session,
    household_id: uuid.UUID,
    *,
    period: str = "ALL",
    account_id: uuid.UUID | None = None,
) -> tuple[dict[str, Any], set[uuid.UUID]]:
    """Returns, risk, benchmarks and diversification for the portfolio or one account."""
    if period != "ALL" and period not in PERIODS:
        raise AuthError("VALIDATION", 422)
    config = personal_config()["performance"]
    assert isinstance(config, dict)
    portfolio = load_portfolio(db, household_id)
    today = portfolio.day
    since = today - dt.timedelta(days=PERIODS[period]) if period in PERIODS else None
    holdings = [p for p in portfolio.positions if p.holding is not None]
    scoped = [p for p in holdings if account_id is None or p.account_id == account_id]
    if account_id is not None and not scoped:
        raise AuthError("NOT_FOUND", 404)
    sources = set(portfolio.source_ids)

    overall, series = _measure(db, scoped, since, today)
    chart: list[dict[str, Any]] = []
    benchmarks: list[dict[str, Any]] = []
    risk_free: Decimal | None = None
    if series.days:
        start, end = series.days[0], series.days[-1]
        week_days, week_levels = _weekly(series)
        chart = [
            {"date": day, "portfolio": Decimal(str(level)).quantize(Q2)}
            for day, level in zip(week_days, week_levels, strict=True)
        ]
        by_day = {point["date"]: point for point in chart}
        for code in [*config["benchmarks"], *config["optional_benchmarks"]]:
            total, yearly, used, levels = _index_return(db, code, start, end)
            if total is None:
                continue
            sources |= used
            benchmarks.append({"code": code, "return_pct": total, "annualised_pct": yearly})
            base = levels[0][1]
            for day, close in levels:
                if day in by_day:
                    by_day[day][code] = (close / base * 100).quantize(Q2)
        rows = db.execute(
            select(MacroSeries.value, MacroSeries.source_id).where(
                MacroSeries.series_code == config["risk_free_series"],
                MacroSeries.date >= start,
                MacroSeries.date <= end,
            )
        ).all()
        if rows:
            risk_free = (sum((r.value for r in rows), Decimal(0)) / len(rows)).quantize(Q2)
            sources.add(rows[-1].source_id)

    accounts: list[dict[str, Any]] = []
    if account_id is None:
        for acct in sorted({p.account_id for p in holdings if p.account_id}, key=str):
            members = [p for p in holdings if p.account_id == acct]
            stats, _ = _measure(db, members, since, today)
            accounts.append({"account_id": acct, "institution": members[0].institution, **stats})

    by_sector: dict[str, Decimal] = defaultdict(Decimal)
    for position in scoped:
        if position.ticker:
            by_sector[position.sector or "UNKNOWN"] += position.household_value
    values = [p.household_value for p in scoped]
    data = {
        "period": period,
        "account_id": account_id,
        **overall,
        "benchmarks": benchmarks,
        "risk_free_pct": risk_free,
        "risk_free_series": config["risk_free_series"],
        "diversification": {
            "holdings": len(scoped),
            "top_n": int(config["top_n"]),
            "top_weight_pct": returns.top_weight(values, int(config["top_n"])),
            "sector_herfindahl": returns.herfindahl(list(by_sector.values()))
            if by_sector
            else None,
            "sectors": len(by_sector),
        },
        "accounts": accounts,
        "chart": chart,
    }
    return data, sources


def volatility_pct(db: Session, portfolio: Portfolio) -> Decimal | None:
    """Annualised volatility of the listed holdings over the past year, for alerts (FR20.1)."""
    since = portfolio.day - dt.timedelta(days=365)
    series = market_series(db, portfolio.positions, since, portfolio.day)
    if not series.days:
        return None
    _, levels = _weekly(series)
    weekly = [b / a - 1 for a, b in itertools.pairwise(levels)]
    return _pct(returns.annualised_volatility(weekly))


# --- allocation and drift (F16) -------------------------------------------------------


def asset_classes() -> list[str]:
    config = personal_config()["portfolio"]
    assert isinstance(config, dict)
    names = {*config["asset_classes"].values(), *config["alt_asset_classes"].values()}
    return sorted(names)


def list_targets(db: Session, household_id: uuid.UUID) -> list[TargetAllocation]:
    return list(
        db.scalars(
            select(TargetAllocation)
            .where(TargetAllocation.household_id == household_id)
            .order_by(TargetAllocation.asset_class)
        )
    )


def set_targets(
    db: Session, household_id: uuid.UUID, targets: list[tuple[str, Decimal, Decimal]]
) -> list[TargetAllocation]:
    """Replace the household's target allocation. Targets must add up to 100%, or be empty
    to clear them. analysisACE never proposes a target (FR16.2)."""
    known = set(asset_classes())
    names = [name for name, _, _ in targets]
    if len(set(names)) != len(names) or not set(names) <= known:
        raise AuthError("VALIDATION", 422)
    if targets and sum((pct for _, pct, _ in targets), Decimal(0)) != HUNDRED:
        raise AuthError("TARGETS_MUST_TOTAL_100", 422)
    db.execute(delete(TargetAllocation).where(TargetAllocation.household_id == household_id))
    db.flush()
    for name, pct, band in targets:
        db.add(
            TargetAllocation(
                household_id=household_id, asset_class=name, target_pct=pct, band_pct=band
            )
        )
    db.flush()
    return list_targets(db, household_id)


def drift_rows(
    db: Session, portfolio: Portfolio, household_id: uuid.UUID
) -> list[allocation_formulas.Drift]:
    targets = {t.asset_class: (t.target_pct, t.band_pct) for t in list_targets(db, household_id)}
    if not targets:
        return []
    return allocation_formulas.drift(portfolio.by_class(), targets)


def _weights(pairs: list[tuple[str, Decimal]]) -> list[dict[str, Any]]:
    return [
        {"key": key, "value": value, "pct": pct}
        for key, (value, pct) in allocation_formulas.weights(pairs).items()
    ]


def allocation(db: Session, household_id: uuid.UUID) -> tuple[dict[str, Any], set[uuid.UUID]]:
    """Allocation by asset class, sector, holding and Shariah status, with drift (FR16.1)."""
    portfolio = load_portfolio(db, household_id)
    positions = portfolio.positions
    names = {str(p.id): p.name for p in positions}
    data = {
        "total": portfolio.assets,
        "by_class": _weights([(p.asset_class, p.household_value) for p in positions]),
        "by_sector": _weights(
            [(p.sector or "UNKNOWN", p.household_value) for p in positions if p.ticker]
        ),
        "by_holding": [
            {**row, "name": names[row["key"]]}
            for row in _weights([(str(p.id), p.household_value) for p in positions])
        ],
        "by_shariah": _weights([(p.shariah, p.household_value) for p in positions]),
        "drift": drift_rows(db, portfolio, household_id),
        "asset_classes": asset_classes(),
    }
    return data, portfolio.source_ids
