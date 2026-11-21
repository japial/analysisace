"""Market alerts (F7), shown in the app and emailed once a provider exists.

- FR7.1: a change of Shariah status reaches everyone who holds the stock (through a
  household) or watches it.
- FR7.2: a regime label change or a newly published shock event reaches users who turned
  that alert on. They are opt-in because they concern every user, not a holding.

Wording is descriptive only. Web push is not sent yet (no VAPID keys or service worker).
"""

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    AlertRule,
    Event,
    Holding,
    HouseholdMember,
    User,
    Watchlist,
)
from app.models.enums import AlertType
from app.services.alerts import notify
from app.services.email import EmailSender
from app.services.market_analytics import RegimeChange
from app.services.screening import StatusChange


def _interested_users(db: Session, ticker: str) -> list[User]:
    holder_ids = set(
        db.scalars(
            select(HouseholdMember.user_id)
            .join(Account, Account.household_id == HouseholdMember.household_id)
            .join(Holding, Holding.account_id == Account.id)
            .where(Holding.ticker == ticker, Holding.is_active.is_(True))
        )
    )
    watcher_ids = set(db.scalars(select(Watchlist.user_id).where(Watchlist.ticker == ticker)))
    ids = {i for i in holder_ids | watcher_ids if i is not None}
    if not ids:
        return []
    return list(db.scalars(select(User).where(User.id.in_(ids), User.is_active.is_(True))))


def _opted_in(db: Session, alert_type: AlertType) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .join(AlertRule, AlertRule.user_id == User.id)
            .where(
                AlertRule.type == alert_type.value,
                AlertRule.is_active.is_(True),
                User.is_active.is_(True),
            )
        )
    )


def status_changed(db: Session, sender: EmailSender, change: StatusChange, at: dt.datetime) -> int:
    """FR7.1. Returns how many notifications were created."""
    created = 0
    for user in _interested_users(db, change.ticker):
        row = notify(
            db,
            sender,
            user,
            type=AlertType.SHARIAH_STATUS.value,
            message_key="SHARIAH_STATUS_CHANGED",
            data={
                "ticker": change.ticker,
                "from_status": change.from_status,
                "to_status": change.to_status,
            },
            link=f"/companies/{change.ticker}",
            dedupe_key=f"shariah:{change.ticker}:{change.to_status}:{at.isoformat()}",
        )
        created += row is not None
    return created


def regime_changed(db: Session, sender: EmailSender, change: RegimeChange) -> int:
    """FR7.2, regime label."""
    created = 0
    for user in _opted_in(db, AlertType.REGIME_CHANGE):
        row = notify(
            db,
            sender,
            user,
            type=AlertType.REGIME_CHANGE.value,
            message_key="REGIME_CHANGED",
            data={
                "previous": change.previous,
                "label": change.label,
                "month": change.month.isoformat(),
            },
            link="/regime",
            dedupe_key=f"regime:{change.month.isoformat()}:{change.label}",
        )
        created += row is not None
    return created


def event_published(db: Session, sender: EmailSender, event: Event) -> int:
    """FR7.2, new shock event."""
    created = 0
    for user in _opted_in(db, AlertType.SHOCK_EVENT):
        row = notify(
            db,
            sender,
            user,
            type=AlertType.SHOCK_EVENT.value,
            message_key="SHOCK_EVENT_PUBLISHED",
            data={
                "title_en": event.title_en,
                "title_bn": event.title_bn,
                "event_type": event.type,
                "date": event.t0.isoformat(),
            },
            link=f"/events/{event.slug}",
            dedupe_key=f"event:{event.slug}",
        )
        created += row is not None
    return created
