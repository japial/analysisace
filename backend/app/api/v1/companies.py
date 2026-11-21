"""Public company endpoints (PRD section 10). Reads only; nothing is computed on request."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from app.api.envelopes import envelope as _envelope
from app.api.envelopes import source_refs as _source_refs
from app.core.db import get_db
from app.models import Company, PriceDaily
from app.schemas.common import Envelope, Page
from app.schemas.company import CompanyDetailOut, CompanyOut, LatestPriceOut

router = APIRouter(prefix="/companies", tags=["companies"])

Db = Annotated[Session, Depends(get_db)]


@router.get("")
def list_companies(
    db: Db,
    q: Annotated[str | None, Query(max_length=50, description="Ticker or name contains")] = None,
    sector: Annotated[str | None, Query(max_length=100)] = None,
    active_only: bool = True,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Envelope[Page[CompanyOut]]:
    filters: list[ColumnElement[bool]] = []
    if active_only:
        filters.append(Company.is_active.is_(True))
    if sector:
        filters.append(Company.sector == sector)
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(Company.ticker.ilike(pattern), Company.name.ilike(pattern)))

    total = db.scalar(select(func.count()).select_from(Company).where(*filters)) or 0
    rows = list(
        db.scalars(
            select(Company).where(*filters).order_by(Company.ticker).limit(limit).offset(offset)
        )
    )
    page = Page[CompanyOut](
        items=[CompanyOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset
    )
    return _envelope(page, _source_refs(db, {r.source_id for r in rows}))


@router.get("/{ticker}")
def get_company(ticker: str, db: Db) -> Envelope[CompanyDetailOut]:
    company = db.scalar(select(Company).where(Company.ticker == ticker.upper()))
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    price = db.scalar(
        select(PriceDaily)
        .where(PriceDaily.ticker == company.ticker)
        .order_by(PriceDaily.date.desc())
        .limit(1)
    )
    detail = CompanyDetailOut(
        **CompanyOut.model_validate(company).model_dump(),
        latest_price=LatestPriceOut.model_validate(price) if price else None,
    )
    source_ids = {company.source_id, price.source_id if price else None}
    return _envelope(detail, _source_refs(db, source_ids))
