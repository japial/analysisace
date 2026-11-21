"""Portfolio check against the market layer (F6).

Uses the household's listed holdings (DSE shares and listed mutual funds, FR6.1) at their
household value and shows:

- the share of value by Shariah status, with unknown-status holdings apart (FR6.2, AC);
- the value-weighted rate sensitivity over holdings that have a score;
- for each published shock event, the value-weighted outcomes of the holdings that have
  metrics for it (historical shock exposure);
- a dividend purification estimate: dividends received in the last 12 months x the company's
  non-permissible income ratio, where that ratio is known (FR6.3).

Weights are rounded to two places and the largest is adjusted so they sum to exactly 100.
"""

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CompanyShariahStatus, Event, EventMetric, Score, Transaction
from app.models.enums import ScoreType, SubjectType, TransactionType
from app.services.valuation import Portfolio, Position, load_portfolio

LISTED = ("DSE_SHARE", "MUTUAL_FUND_UNIT")
_Q2 = Decimal("0.01")
_HUNDRED = Decimal(100)


def _weights(values: list[Decimal]) -> list[Decimal]:
    total = sum(values, Decimal(0))
    if total <= 0:
        return [Decimal(0) for _ in values]
    weights = [(v / total * _HUNDRED).quantize(_Q2) for v in values]
    gap = _HUNDRED - sum(weights, Decimal(0))
    if gap and weights:
        biggest = max(range(len(weights)), key=lambda i: values[i])
        weights[biggest] += gap
    return weights


def _weighted(pairs: list[tuple[Decimal, Decimal | None]]) -> tuple[Decimal | None, Decimal]:
    """Weighted mean over pairs with a value, and the weight they cover (percent)."""
    known = [(w, v) for w, v in pairs if v is not None]
    covered = sum((w for w, _ in known), Decimal(0))
    if covered <= 0:
        return None, Decimal(0)
    mean = sum((w * v for w, v in known), Decimal(0)) / covered
    return mean.quantize(Decimal("0.0001")), covered.quantize(_Q2)


def market_check(
    db: Session, household_id: uuid.UUID, today: dt.date | None = None
) -> tuple[dict[str, Any], Portfolio]:
    portfolio = load_portfolio(db, household_id, today)
    listed: list[Position] = [
        p for p in portfolio.positions if p.type in LISTED and p.ticker and p.household_value > 0
    ]
    values = [p.household_value for p in listed]
    weights = _weights(values)
    tickers = sorted({p.ticker for p in listed if p.ticker})

    scores = {
        s.subject: s
        for s in db.scalars(
            select(Score).where(
                Score.subject_type == SubjectType.TICKER.value,
                Score.score_type == ScoreType.RATE_SENSITIVITY.value,
                Score.subject.in_(tickers),
            )
        )
    }
    statuses = {
        s.ticker: s
        for s in db.scalars(
            select(CompanyShariahStatus).where(CompanyShariahStatus.ticker.in_(tickers))
        )
    }
    since = portfolio.day - dt.timedelta(days=365)
    holding_ids = [p.holding.id for p in listed if p.holding is not None]
    dividends: dict[uuid.UUID, Decimal] = {}
    for holding_id, amount in db.execute(
        select(Transaction.holding_id, Transaction.amount).where(
            Transaction.holding_id.in_(holding_ids),
            Transaction.type == TransactionType.DIVIDEND.value,
            Transaction.date > since,
            Transaction.date <= portfolio.day,
        )
    ):
        dividends[holding_id] = dividends.get(holding_id, Decimal(0)) + amount

    rows: list[dict[str, Any]] = []
    by_status: dict[str, Decimal] = {}
    purification_total = Decimal(0)
    unknown_ratio_dividends = Decimal(0)
    for position, weight in zip(listed, weights, strict=True):
        assert position.ticker is not None
        score = scores.get(position.ticker)
        status_row = statuses.get(position.ticker)
        ratio = status_row.non_permissible_income_ratio if status_row else None
        received = (
            dividends.get(position.holding.id, Decimal(0)) if position.holding else Decimal(0)
        )
        purification = (received * ratio).quantize(_Q2) if ratio is not None else None
        if purification is not None:
            purification_total += purification
        elif received > 0:
            unknown_ratio_dividends += received
        by_status[position.shariah] = by_status.get(position.shariah, Decimal(0)) + weight
        rows.append(
            {
                "holding_id": str(position.id),
                "name": position.name,
                "ticker": position.ticker,
                "sector": position.sector,
                "value": str(position.household_value),
                "weight_pct": str(weight),
                "shariah": position.shariah,
                "rate_sensitivity_pct": None
                if score is None or score.value is None
                else str(score.value),
                "rate_confidence": None if score is None else score.confidence,
                "dividends_12m": str(received.quantize(_Q2)),
                "non_permissible_income_ratio": None if ratio is None else str(ratio),
                "non_permissible_income_pct": None
                if ratio is None
                else str((ratio * _HUNDRED).quantize(Decimal("0.0001"))),
                "purification": None if purification is None else str(purification),
            }
        )

    rate, rate_cover = _weighted(
        [
            (
                w,
                scores[p.ticker].value
                if p.ticker in scores and scores[p.ticker].value is not None
                else None,
            )
            for p, w in zip(listed, weights, strict=True)
        ]
    )

    events = list(
        db.scalars(select(Event).where(Event.published.is_(True)).order_by(Event.t0.desc()))
    )
    metrics: dict[tuple[uuid.UUID, str], EventMetric] = {
        (m.event_id, m.subject): m
        for m in db.scalars(
            select(EventMetric).where(
                EventMetric.subject_type == SubjectType.TICKER.value,
                EventMetric.subject.in_(tickers),
            )
        )
    }
    shock_rows = []
    for event in events:
        out: dict[str, Any] = {
            "event_id": str(event.id),
            "slug": event.slug,
            "type": event.type,
            "t0": event.t0.isoformat(),
            "title_en": event.title_en,
            "title_bn": event.title_bn,
        }
        cover = Decimal(0)
        for field in ("ret_1", "ret_5", "ret_20", "max_dd_60"):
            pairs = []
            for p, w in zip(listed, weights, strict=True):
                m = metrics.get((event.id, p.ticker or ""))
                pairs.append((w, getattr(m, field) if m else None))
            mean, covered = _weighted(pairs)
            out[field] = None if mean is None else str(mean)
            cover = max(cover, covered)
        out["coverage_pct"] = str(cover)
        shock_rows.append(out)

    data = {
        "as_of_day": portfolio.day.isoformat(),
        "listed_value": str(sum(values, Decimal(0)).quantize(_Q2)),
        "holdings": rows,
        "shariah_share": [
            {"status": k, "weight_pct": str(v)}
            for k, v in sorted(by_status.items(), key=lambda kv: -kv[1])
        ],
        "rate_sensitivity": {
            "weighted_pct": None if rate is None else str(rate),
            "coverage_pct": str(rate_cover),
        },
        "shock_exposure": shock_rows,
        "purification": {
            "total": str(purification_total.quantize(_Q2)),
            "dividends_unknown_ratio": str(unknown_ratio_dividends.quantize(_Q2)),
        },
    }
    return data, portfolio
