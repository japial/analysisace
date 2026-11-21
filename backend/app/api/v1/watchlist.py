"""Watchlist (FR7.1: watched stocks alert on Shariah status changes like held ones)."""

from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app.api.deps import CurrentUser, Db
from app.models import Company, CompanyShariahStatus, Watchlist
from app.schemas.market import WatchItem
from app.services.auth import AuthError
from app.services.screening import effective_status

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

MAX_ITEMS = 200


@router.get("")
def list_watchlist(user: CurrentUser, db: Db) -> list[WatchItem]:
    rows = db.execute(
        select(Company, CompanyShariahStatus)
        .join(Watchlist, Watchlist.ticker == Company.ticker)
        .outerjoin(CompanyShariahStatus, CompanyShariahStatus.ticker == Company.ticker)
        .where(Watchlist.user_id == user.id)
        .order_by(Company.ticker)
    ).all()
    return [
        WatchItem(ticker=c.ticker, name=c.name, status=effective_status(s) if s else None)
        for c, s in rows
    ]


@router.put("/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
def watch(ticker: str, user: CurrentUser, db: Db) -> Response:
    code = ticker.upper()
    if db.scalar(select(Company.id).where(Company.ticker == code)) is None:
        raise AuthError("NOT_FOUND", 404)
    exists = db.scalar(
        select(Watchlist.id).where(Watchlist.user_id == user.id, Watchlist.ticker == code)
    )
    if exists is None:
        count = len(list(db.scalars(select(Watchlist.id).where(Watchlist.user_id == user.id))))
        if count >= MAX_ITEMS:
            raise AuthError("LIMIT_REACHED", 422)
        db.add(Watchlist(user_id=user.id, ticker=code))
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
def unwatch(ticker: str, user: CurrentUser, db: Db) -> Response:
    row = db.scalar(
        select(Watchlist).where(Watchlist.user_id == user.id, Watchlist.ticker == ticker.upper())
    )
    if row is not None:
        db.delete(row)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
