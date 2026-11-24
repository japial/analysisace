"""Browser push subscriptions (D26). The web server calls these for the signed-in person;
the browser itself never talks to the API."""

from typing import Annotated, Any

from fastapi import APIRouter, Header, Response, status

from app.api.deps import AppSettings, CurrentUser, Db
from app.schemas.auth import PushEndpointIn, PushSubscriptionIn
from app.services import push
from app.services.auth import AuthError

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/config")
def push_config(user: CurrentUser, db: Db, settings: AppSettings) -> dict[str, Any]:
    """Whether push is on, the public key browsers subscribe with, and how many of this
    person's browsers are subscribed."""
    return {**push.describe(settings), "subscriptions": push.count_for(db, user.id)}


@router.post("/subscriptions", status_code=status.HTTP_201_CREATED)
def subscribe(
    body: PushSubscriptionIn,
    user: CurrentUser,
    db: Db,
    settings: AppSettings,
    user_agent: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    if not push.enabled(settings):
        raise AuthError("PUSH_NOT_CONFIGURED", 409)
    if not push.endpoint_allowed(body.endpoint):
        raise AuthError("PUSH_ENDPOINT_INVALID", 422)
    push.subscribe(db, user, body.endpoint, body.keys.model_dump(), user_agent)
    db.commit()
    return {"subscriptions": push.count_for(db, user.id)}


@router.post("/subscriptions/remove", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe(body: PushEndpointIn, user: CurrentUser, db: Db) -> Response:
    push.unsubscribe(db, user, body.endpoint)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
