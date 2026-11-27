"""Links inside emails that work without signing in (D34). The web app calls these for the
visitor; the token in the link says whose emails and which ones."""

from typing import Any

from fastapi import APIRouter

from app.api.deps import Db
from app.schemas.auth import UnsubscribeIn
from app.services import unsubscribe as unsubscribe_service

router = APIRouter(prefix="/email", tags=["email"])


@router.post("/unsubscribe/check")
def check_unsubscribe(body: UnsubscribeIn, db: Db) -> dict[str, Any]:
    """What the link would stop, so the page can ask before changing anything (mail
    scanners open links, so opening one never unsubscribes)."""
    return unsubscribe_service.describe(db, body.token)


@router.post("/unsubscribe")
def unsubscribe(body: UnsubscribeIn, db: Db) -> dict[str, Any]:
    """Stop the emails the link names (RFC 8058 one-click, or the confirm button)."""
    result = unsubscribe_service.unsubscribe(db, body.token)
    db.commit()
    return result
