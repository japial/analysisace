"""Analytics jobs over stored market data: F3 scores, F5 event metrics, F2 basket, F8 regime.

Every result is written to its table with a computation time, so the API only reads rows
(backend rule: no heavy computation on request). Inputs are adjusted closes, index levels and
macro series already in the database; nothing here calls an outside service.
"""

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.analytics import regime as regime_rules
from app.analytics.basket import equal_weight_basket
from app.analytics.events import equal_weight_index, event_outcome
from app.analytics.regression import rate_sensitivity, weekly_sample
from app.core.app_config import get_config
from app.core.security import utcnow
from app.core.trading_calendar import TradingCalendar
from app.models import (
    Company,
    CompanyShariahStatus,
    Event,
    EventMetric,
    IndexDaily,
    MacroSeries,
    PriceDaily,
    RegimeMonth,
    RegimeSectorStat,
    Score,
    Source,
)
from app.models.enums import ScoreType, ShariahStatus, SubjectType

_D6 = Decimal("0.000001")


def market_config() -> dict[str, Any]:
    return get_config("market").data


def excluded_periods() -> list[tuple[dt.date, dt.date]]:
    data = get_config("excluded_periods").data
    out = []
    for row in data.get("floor_price_periods") or []:
        start, end = row["start"], row["end"]
        out.append(
            (
                start if isinstance(start, dt.date) else dt.date.fromisoformat(str(start)),
                end if isinstance(end, dt.date) else dt.date.fromisoformat(str(end)),
            )
        )
    return out


# --- shared loaders -------------------------------------------------------------------


@dataclass
class MarketData:
    adj: dict[str, dict[dt.date, Decimal]]
    sectors: dict[str, list[str]]  # sector -> tickers
    days: list[dt.date]  # every date with at least one price

    def sector_index(self, sector: str) -> dict[dt.date, Decimal]:
        members = [self.adj[t] for t in self.sectors[sector] if t in self.adj]
        return dict(equal_weight_index(members, self.days))


def load_market_data(db: Session) -> MarketData:
    adj: dict[str, dict[dt.date, Decimal]] = defaultdict(dict)
    for ticker, day, close in db.execute(
        select(PriceDaily.ticker, PriceDaily.date, PriceDaily.adj_close)
        .join(Company, Company.ticker == PriceDaily.ticker)
        .where(Company.is_active.is_(True), PriceDaily.adj_close.is_not(None))
    ):
        if close is not None:
            adj[ticker][day] = close
    sectors: dict[str, list[str]] = defaultdict(list)
    for ticker, sector in db.execute(
        select(Company.ticker, Company.sector)
        .where(Company.is_active.is_(True))
        .order_by(Company.ticker)
    ):
        if sector and ticker in adj:
            sectors[sector].append(ticker)
    days = sorted({d for series in adj.values() for d in series})
    return MarketData(dict(adj), dict(sectors), days)


def _index_closes(db: Session, code: str) -> dict[dt.date, Decimal]:
    return dict(
        db.execute(
            select(IndexDaily.date, IndexDaily.close).where(IndexDaily.index_code == code)
        ).all()
    )


def _macro_points(db: Session, code: str) -> list[tuple[dt.date, Decimal]]:
    return [
        (d, v)
        for d, v in db.execute(
            select(MacroSeries.date, MacroSeries.value)
            .where(MacroSeries.series_code == code)
            .order_by(MacroSeries.date)
        )
    ]


def _dec(value: float | None) -> Decimal | None:
    return None if value is None else Decimal(str(round(value, 6))).quantize(_D6)


# --- F3 rate sensitivity --------------------------------------------------------------


def compute_rate_scores(
    db: Session, data: MarketData, now: dt.datetime | None = None
) -> dict[str, int]:
    """FR3.1 to FR3.3 for every stock and sector, with and without the market term."""
    now = now or utcnow()
    cfg = market_config()["rate_sensitivity"]
    if not data.days:
        return {"scores": 0}
    end = data.days[-1]
    start = dt.date(end.year - int(cfg["max_years"]), end.month, min(end.day, 28))
    market = {d: float(v) for d, v in _index_closes(db, cfg["market_index"]).items()}
    yields = [(d, float(v)) for d, v in _macro_points(db, cfg["yield_series"])]
    excluded = excluded_periods()

    subjects: list[tuple[str, str, dict[dt.date, Decimal]]] = [
        (SubjectType.TICKER.value, t, series) for t, series in sorted(data.adj.items())
    ]
    subjects += [(SubjectType.SECTOR.value, s, data.sector_index(s)) for s in sorted(data.sectors)]
    existing = {(r.subject_type, r.subject, r.score_type): r for r in db.scalars(select(Score))}
    written = 0
    for subject_type, subject, series in subjects:
        sample = weekly_sample(
            {d: float(v) for d, v in series.items()},
            market,
            yields,
            TradingCalendar.week_start,
            excluded,
            start,
            end,
        )
        for score_type, with_market in (
            (ScoreType.RATE_SENSITIVITY, True),
            (ScoreType.RATE_SENSITIVITY_NO_MARKET, False),
        ):
            fit = rate_sensitivity(
                sample,
                with_market=with_market,
                min_weeks=int(cfg["min_valid_weeks"]),
                lags=cfg.get("newey_west_lags"),
                high_min_t=float(cfg["high_min_abs_t"]),
                medium_min_t=float(cfg["medium_min_abs_t"]),
            )
            key = (subject_type, subject, score_type.value)
            row = existing.get(key)
            if row is None:
                row = Score(subject_type=subject_type, subject=subject, score_type=score_type.value)
                db.add(row)
            row.value, row.std_error, row.t_stat = (
                _dec(fit.value_pct),
                _dec(fit.std_error_pct),
                _dec(fit.t_stat),
            )
            row.confidence, row.n_obs = fit.confidence.value, fit.n_obs
            row.sample_start, row.sample_end = fit.sample_start, fit.sample_end
            row.computed_at = now
            written += 1
    db.flush()
    return {"scores": written}


# --- F5 event metrics -----------------------------------------------------------------


def compute_event_metrics(
    db: Session,
    data: MarketData,
    now: dt.datetime | None = None,
    event_ids: list[Any] | None = None,
) -> dict[str, int]:
    """FR5.2 for every published event x stock, sector and the DSEX."""
    now = now or utcnow()
    cfg = market_config()["events"]
    horizons = [int(h) for h in cfg["return_horizons"]]
    statement = select(Event).where(Event.published.is_(True))
    if event_ids is not None:
        statement = statement.where(Event.id.in_(event_ids))
    events = list(db.scalars(statement))
    subjects: list[tuple[str, str, dict[dt.date, Decimal]]] = [
        (SubjectType.TICKER.value, t, s) for t, s in data.adj.items()
    ]
    subjects += [(SubjectType.SECTOR.value, s, data.sector_index(s)) for s in data.sectors]
    subjects.append((SubjectType.INDEX.value, "DSEX", _index_closes(db, "DSEX")))

    written = 0
    for event in events:
        existing = {
            (m.subject_type, m.subject): m
            for m in db.scalars(select(EventMetric).where(EventMetric.event_id == event.id))
        }
        for subject_type, subject, series in subjects:
            outcome = event_outcome(
                list(series.items()),
                event.t0,
                horizons,
                int(cfg["drawdown_window"]),
                int(cfg["recovery_window"]),
            )
            row = existing.pop((subject_type, subject), None)
            if outcome is None:
                if row is not None:
                    db.delete(row)
                continue
            if row is None:
                row = EventMetric(event_id=event.id, subject_type=subject_type, subject=subject)
                db.add(row)
            row.ret_1 = outcome.returns.get(1)
            row.ret_5 = outcome.returns.get(5)
            row.ret_20 = outcome.returns.get(20)
            row.max_dd_60 = outcome.max_drawdown
            row.sessions_to_recover = outcome.sessions_to_recover
            row.computed_at = now
            written += 1
        for stale in existing.values():
            db.delete(stale)
    db.flush()
    return {"event_metrics": written}


# --- F2 Shariah basket ----------------------------------------------------------------


def compliant_tickers(db: Session) -> list[str]:
    rows = db.scalars(select(CompanyShariahStatus))
    return sorted(
        r.ticker for r in rows if (r.override_status or r.status) == ShariahStatus.COMPLIANT.value
    )


def compute_basket(db: Session, data: MarketData, now: dt.datetime | None = None) -> dict[str, int]:
    """FR2.2: rewrite the basket's levels from the current COMPLIANT set."""
    now = now or utcnow()
    cfg = market_config()["basket"]
    code = cfg["code"]
    members = [t for t in compliant_tickers(db) if t in data.adj]
    db.execute(delete(IndexDaily).where(IndexDaily.index_code == code))
    if not members:
        db.flush()
        return {"basket_days": 0, "basket_members": 0}
    levels = equal_weight_basket(
        {t: data.adj[t] for t in members}, data.days, Decimal(str(cfg["base_value"]))
    )
    source = Source(
        name=f"{cfg['name']}: {len(members)} companies",
        url=None,
        fetched_at=now,
    )
    db.add(source)
    db.flush()
    db.add_all(IndexDaily(index_code=code, date=d, close=v, source_id=source.id) for d, v in levels)
    db.flush()
    return {"basket_days": len(levels), "basket_members": len(members)}


def basket_members(db: Session) -> list[str]:
    """The companies in the basket now (the current COMPLIANT set with prices)."""
    priced = set(db.scalars(select(PriceDaily.ticker).distinct()))
    return [t for t in compliant_tickers(db) if t in priced]


# --- F8 macro regime ------------------------------------------------------------------


@dataclass(frozen=True)
class RegimeChange:
    month: dt.date
    previous: str | None
    label: str


def compute_regimes(
    db: Session, data: MarketData, now: dt.datetime | None = None
) -> tuple[dict[str, int], RegimeChange | None]:
    """FR8.1 for every month with data, and FR8.2 sector records for every label.

    Returns a change when the newest month's label differs from the label stored for the
    newest month before this run (for FR7.2 alerts).
    """
    now = now or utcnow()
    cfg = get_config("regime").data
    version = get_config("regime").version
    yields = regime_rules.month_end_values(_macro_points(db, cfg["rate_trend"]["series"]))
    oil = regime_rules.month_end_values(_macro_points(db, cfg["oil_shock"]["series"]))
    inflation_series = (cfg.get("inflation") or {}).get("series")
    cpi = (
        regime_rules.month_end_values(_macro_points(db, inflation_series))
        if inflation_series
        else {}
    )
    months = sorted(yields)
    if not months:
        return {"regime_months": 0, "sector_stats": 0}, None

    previous_latest = db.scalar(select(RegimeMonth).order_by(RegimeMonth.month.desc()).limit(1))
    previous_label = previous_latest.label if previous_latest else None
    stored = {r.month: r for r in db.scalars(select(RegimeMonth))}
    labels: dict[dt.date, str] = {}
    for month in months:
        result = regime_rules.classify_month(month, yields, cpi, oil, cfg)
        labels[month] = result.label
        row = stored.get(month)
        if row is None:
            row = RegimeMonth(
                month=month, label=result.label, components={}, config_version=version
            )
            db.add(row)
        row.label, row.components, row.config_version = result.label, result.components, version
    db.flush()

    sector_returns = {
        sector: regime_rules.monthly_returns(
            regime_rules.month_end_values(list(data.sector_index(sector).items()))
        )
        for sector in data.sectors
    }
    db.execute(delete(RegimeSectorStat))
    n_stats = 0
    for label in sorted(set(labels.values())):
        for stat in regime_rules.sector_stats_for_label(label, labels, sector_returns):
            db.add(
                RegimeSectorStat(
                    label=label,
                    sector=stat.sector,
                    avg_monthly_return=stat.avg_monthly_return,
                    hit_rate=stat.hit_rate,
                    n_months=stat.n_months,
                    computed_at=now,
                )
            )
            n_stats += 1
    db.flush()

    newest = months[-1]
    change = None
    if previous_label is not None and labels[newest] != previous_label:
        change = RegimeChange(newest, previous_label, labels[newest])
    return {"regime_months": len(months), "sector_stats": n_stats}, change


def newest_price_day(db: Session) -> dt.date | None:
    return db.scalar(select(func.max(PriceDaily.date)))
