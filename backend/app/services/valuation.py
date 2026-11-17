"""What a household owns and owes, valued on a date (FR14.3, FR14.4, FR25.2).

One place works out the value of every holding, alternative asset and liability, so the
net worth, allocation, Zakat, tax and FIRE figures all agree. Listed holdings use the DSE
close on or before the date; gold and silver use the price per gram; everything else uses
the value the household entered.
"""

import datetime as dt
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.allocation import metal_value
from app.core.app_config import get_config
from app.core.security import utcnow
from app.models import (
    Account,
    AltAsset,
    Company,
    CompanyShariahStatus,
    Holding,
    HouseholdMember,
    Liability,
    MacroSeries,
    PriceDaily,
    Valuation,
)
from app.services.households import JOINT, Ownership, list_members, ownership_map

Q2 = Decimal("0.01")
HUNDRED = Decimal(100)
DHAKA = ZoneInfo("Asia/Dhaka")


def today_dhaka() -> dt.date:
    """Today's date where the users are. Dates are shown in Asia/Dhaka (PRD section 12)."""
    return utcnow().astimezone(DHAKA).date()


def personal_config() -> dict[str, object]:
    return get_config("personal").data


@dataclass(frozen=True)
class Position:
    kind: str  # HOLDING or ALT_ASSET
    id: uuid.UUID
    name: str
    type: str  # instrument type or alternative asset type
    asset_class: str
    value: Decimal  # the whole asset
    cost: Decimal
    method: str  # MARKET_PRICE, METAL_PRICE, MANUAL or COST
    ownership: Ownership
    valued_on: dt.date | None = None
    source_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None
    institution: str | None = None
    ticker: str | None = None
    sector: str | None = None
    liquidity: str | None = None
    shariah: str = "UNKNOWN"
    holding: Holding | None = None
    alt: AltAsset | None = None

    @property
    def household_value(self) -> Decimal:
        """The household's part, leaving out co-owners outside it (FR25.8)."""
        return (self.value * self.ownership.household_pct / HUNDRED).quantize(Q2)


@dataclass(frozen=True)
class Debt:
    liability: Liability
    ownership: Ownership

    @property
    def household_outstanding(self) -> Decimal:
        pct = self.ownership.household_pct
        return (self.liability.outstanding * pct / HUNDRED).quantize(Q2)


@dataclass
class Portfolio:
    day: dt.date
    positions: list[Position] = field(default_factory=list)
    debts: list[Debt] = field(default_factory=list)
    members: list[HouseholdMember] = field(default_factory=list)
    source_ids: set[uuid.UUID] = field(default_factory=set)

    @property
    def assets(self) -> Decimal:
        return sum((p.household_value for p in self.positions), Decimal(0)).quantize(Q2)

    @property
    def liabilities(self) -> Decimal:
        return sum((d.household_outstanding for d in self.debts), Decimal(0)).quantize(Q2)

    @property
    def net_worth(self) -> Decimal:
        return self.assets - self.liabilities

    def by_class(self) -> dict[str, Decimal]:
        totals: dict[str, Decimal] = {}
        for position in self.positions:
            totals[position.asset_class] = (
                totals.get(position.asset_class, Decimal(0)) + position.household_value
            )
        return dict(sorted(totals.items(), key=lambda item: -item[1]))

    def member_value(self, position: Position, member_id: uuid.UUID) -> Decimal:
        pct = position.ownership.member_pct(member_id, len(self.members))
        return (position.value * pct / HUNDRED).quantize(Q2)

    def by_member(self) -> dict[uuid.UUID, tuple[Decimal, Decimal]]:
        """Member -> (assets, liabilities), with joint items split equally."""
        out: dict[uuid.UUID, tuple[Decimal, Decimal]] = {}
        n = len(self.members)
        for member in self.members:
            assets = sum((self.member_value(p, member.id) for p in self.positions), Decimal(0))
            owed = sum(
                (
                    (d.liability.outstanding * d.ownership.member_pct(member.id, n) / HUNDRED)
                    for d in self.debts
                ),
                Decimal(0),
            )
            out[member.id] = (assets.quantize(Q2), owed.quantize(Q2))
        return out


def latest_macro(db: Session, code: str, day: dt.date | None = None) -> MacroSeries | None:
    """The newest value of a macro series on or before `day`."""
    statement = select(MacroSeries).where(MacroSeries.series_code == code)
    if day is not None:
        statement = statement.where(MacroSeries.date <= day)
    return db.scalar(statement.order_by(MacroSeries.date.desc()).limit(1))


def closes_on(db: Session, tickers: set[str], day: dt.date) -> dict[str, PriceDaily]:
    """Each ticker's last price row on or before `day`."""
    if not tickers:
        return {}
    latest = (
        select(PriceDaily.ticker, func.max(PriceDaily.date).label("day"))
        .where(PriceDaily.ticker.in_(tickers), PriceDaily.date <= day)
        .group_by(PriceDaily.ticker)
        .subquery()
    )
    rows = db.scalars(
        select(PriceDaily).join(
            latest, (PriceDaily.ticker == latest.c.ticker) & (PriceDaily.date == latest.c.day)
        )
    )
    return {row.ticker: row for row in rows}


def _holding_shariah(holding: Holding, statuses: dict[str, str]) -> str:
    if holding.is_interest_bearing:
        return "NON_COMPLIANT"
    if holding.instrument_type in ("SUKUK", "ISLAMIC_DEPOSIT"):
        return "COMPLIANT"
    if holding.ticker:
        return statuses.get(holding.ticker, "UNKNOWN")
    return "UNKNOWN"


def load_portfolio(
    db: Session, household_id: uuid.UUID, day: dt.date | None = None, *, active_only: bool = True
) -> Portfolio:
    """Value everything the household holds as of `day` (today when omitted)."""
    config = personal_config()["portfolio"]
    assert isinstance(config, dict)
    day = day or today_dhaka()
    portfolio = Portfolio(day=day, members=list_members(db, household_id))

    accounts = {
        a.id: a for a in db.scalars(select(Account).where(Account.household_id == household_id))
    }
    holdings = list(
        db.scalars(
            select(Holding).where(Holding.account_id.in_(list(accounts))).order_by(Holding.name)
        )
    )
    alts = list(
        db.scalars(
            select(AltAsset).where(AltAsset.household_id == household_id).order_by(AltAsset.name)
        )
    )
    liabilities = list(
        db.scalars(
            select(Liability).where(Liability.household_id == household_id).order_by(Liability.name)
        )
    )
    if active_only:
        holdings = [h for h in holdings if h.is_active]
        alts = [a for a in alts if a.is_active]
        liabilities = [x for x in liabilities if x.is_active]

    owners = ownership_map(
        db, [h.id for h in holdings] + [a.id for a in alts] + [x.id for x in liabilities]
    )
    tickers = {
        h.ticker for h in holdings if h.ticker and h.instrument_type in config["market_priced"]
    }
    prices = closes_on(db, tickers, day)
    sectors = dict(
        db.execute(select(Company.ticker, Company.sector).where(Company.ticker.in_(tickers))).all()
    )
    statuses = {
        row.ticker: (row.override_status or row.status)
        for row in db.scalars(
            select(CompanyShariahStatus).where(CompanyShariahStatus.ticker.in_(tickers))
        )
    }

    for holding in holdings:
        account = accounts[holding.account_id]
        price = prices.get(holding.ticker) if holding.ticker in tickers else None
        if price is not None:
            value, method = (holding.quantity * price.close).quantize(Q2), "MARKET_PRICE"
            portfolio.source_ids.add(price.source_id)
        elif holding.manual_value is not None:
            value, method = holding.manual_value, "MANUAL"
        else:
            value, method = holding.cost, "COST"
        portfolio.positions.append(
            Position(
                kind="HOLDING",
                id=holding.id,
                name=holding.name,
                type=holding.instrument_type,
                asset_class=str(config["asset_classes"].get(holding.instrument_type, "OTHER")),
                value=value,
                cost=holding.cost,
                method=method,
                ownership=owners.get(holding.id, JOINT),
                valued_on=price.date if price else None,
                source_id=price.source_id if price else None,
                account_id=account.id,
                institution=account.institution,
                ticker=holding.ticker,
                sector=sectors.get(holding.ticker) if holding.ticker else None,
                shariah=_holding_shariah(holding, statuses),
                holding=holding,
            )
        )

    metal_rows = {
        kind: latest_macro(db, code, day) for kind, code in config["metal_price_series"].items()
    }
    last_valuation: dict[uuid.UUID, Valuation] = {}
    if alts:
        for row in db.scalars(
            select(Valuation)
            .where(
                Valuation.asset_kind == "ALT_ASSET",
                Valuation.asset_id.in_([a.id for a in alts]),
                Valuation.date <= day,
            )
            .order_by(Valuation.date)
        ):
            last_valuation[row.asset_id] = row
    for alt in alts:
        metal = metal_rows.get(alt.type)
        source_id: uuid.UUID | None = None
        valued_on: dt.date | None = None
        if metal is not None and alt.weight_grams:
            karat = alt.karat if alt.type == "GOLD" else None
            value = metal_value(alt.weight_grams, metal.value, karat, config["gold_series_karat"])
            method, source_id, valued_on = "METAL_PRICE", metal.source_id, metal.date
            portfolio.source_ids.add(metal.source_id)
        elif alt.id in last_valuation:
            row = last_valuation[alt.id]
            value, method, valued_on = row.value, "MANUAL", row.date
        else:
            value, method = alt.cost, "COST"
        portfolio.positions.append(
            Position(
                kind="ALT_ASSET",
                id=alt.id,
                name=alt.name,
                type=alt.type,
                asset_class=str(config["alt_asset_classes"].get(alt.type, "OTHER")),
                value=value,
                cost=alt.cost,
                method=method,
                ownership=owners.get(alt.id, JOINT),
                valued_on=valued_on,
                source_id=source_id,
                liquidity=alt.liquidity,
                shariah=alt.shariah_flag,
                alt=alt,
            )
        )

    portfolio.debts = [Debt(liability=x, ownership=owners.get(x.id, JOINT)) for x in liabilities]
    return portfolio
