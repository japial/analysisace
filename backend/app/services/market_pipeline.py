"""Runs the market analytics in order, for the worker, the demo seed and admin "run now".

Order matters: adjusted prices, then the screen (the basket needs statuses), then the
scores, event metrics, basket and regime, then the FR7 alerts for what changed.
"""

import datetime as dt
from typing import Any

from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.services import market_alerts, market_analytics, market_data, screening
from app.services.email import EmailSender


def run_market_analytics(
    db: Session, sender: EmailSender, now: dt.datetime | None = None
) -> dict[str, Any]:
    now = now or utcnow()
    detail: dict[str, Any] = {"adjusted": market_data.recompute_adjusted_closes(db)}
    changes = screening.run_screening(db, now)
    detail["status_changes"] = len(changes)
    data = market_analytics.load_market_data(db)
    detail |= market_analytics.compute_rate_scores(db, data, now)
    detail |= market_analytics.compute_event_metrics(db, data, now)
    detail |= market_analytics.compute_basket(db, data, now)
    regimes, regime_change = market_analytics.compute_regimes(db, data, now)
    detail |= regimes

    alerts = sum(market_alerts.status_changed(db, sender, c, now) for c in changes if c.from_status)
    if regime_change is not None:
        alerts += market_alerts.regime_changed(db, sender, regime_change)
    detail["alerts"] = alerts
    return detail
