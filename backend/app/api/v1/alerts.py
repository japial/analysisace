"""Alert preferences and notifications (F20) and community benchmarks (F21).

These belong to the signed-in user, not to a household.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, Db
from app.models.enums import AlertType
from app.schemas.personal import (
    AlertRuleIn,
    AlertRuleOut,
    MarkReadIn,
    NotificationOut,
    NotificationsOut,
)
from app.services import alerts

router = APIRouter(tags=["alerts"])


@router.get("/alerts")
def list_alert_rules(user: CurrentUser, db: Db) -> list[AlertRuleOut]:
    """The user's alert preferences. A type with no rule is shown in the app only."""
    return [AlertRuleOut.model_validate(r) for r in alerts.list_rules(db, user)]


@router.put("/alerts/{alert_type}")
def set_alert_rule(
    alert_type: AlertType, body: AlertRuleIn, user: CurrentUser, db: Db
) -> AlertRuleOut:
    """Turn an alert on or off and choose its channel and frequency (FR7.3, FR20.1)."""
    rule = alerts.set_rule(
        db,
        user,
        type=alert_type,
        channel=body.channel,
        frequency=body.frequency,
        is_active=body.is_active,
        params=body.params,
    )
    db.commit()
    return AlertRuleOut.model_validate(rule)


@router.get("/notifications")
def list_notifications(
    user: CurrentUser,
    db: Db,
    unread_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> NotificationsOut:
    rows, unread = alerts.list_notifications(db, user, unread_only=unread_only, limit=limit)
    return NotificationsOut(items=[NotificationOut.model_validate(r) for r in rows], unread=unread)


@router.post("/notifications/read")
def mark_notifications_read(body: MarkReadIn, user: CurrentUser, db: Db) -> dict[str, int]:
    """Mark one notification as read, or all of them when no id is given."""
    marked = alerts.mark_read(db, user, body.id)
    db.commit()
    return {"marked": marked}


@router.get("/community/benchmarks")
def community_benchmarks(user: CurrentUser, db: Db) -> dict[str, Any]:
    """FR21: anonymous medians for the user's age band. Opt-in only, and a group is shown
    only when it is large enough that no one can be picked out."""
    return alerts.community_benchmarks(db, user)
