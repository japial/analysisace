from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    name: str
    sector: str | None
    listing_date: date | None
    is_active: bool


class LatestPriceOut(BaseModel):
    """Money is serialised as a decimal string, never a float."""

    model_config = ConfigDict(from_attributes=True)

    date: date
    close: Decimal
    adj_close: Decimal | None
    volume: int | None


class CompanyDetailOut(CompanyOut):
    latest_price: LatestPriceOut | None
