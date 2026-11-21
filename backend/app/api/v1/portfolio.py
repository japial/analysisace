"""Portfolio aggregation (F14), performance (F15) and allocation (F16)."""

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Response, status

from app.api.deps import Db, Editor, Viewer
from app.api.envelopes import computed
from app.api.v1.households import no_content
from app.models import Account, Liability
from app.schemas.common import Envelope
from app.schemas.personal import (
    AccountIn,
    AccountOut,
    AccountUpdateIn,
    BrokerCsvIn,
    HoldingIn,
    HoldingOut,
    HoldingUpdateIn,
    ImportOut,
    LiabilityIn,
    LiabilityOut,
    LiabilityUpdateIn,
    NetWorthPointOut,
    OwnerIn,
    OwnerOut,
    PositionOut,
    TargetsIn,
    TransactionIn,
    TransactionOut,
)
from app.services import market_check, performance, portfolio
from app.services.households import OwnerInput, owned
from app.services.valuation import Portfolio, Position, today_dhaka

router = APIRouter(prefix="/households/{household_id}", tags=["portfolio"])


def owner_inputs(owners: list[OwnerIn] | None) -> list[OwnerInput] | None:
    if owners is None:
        return None
    return [
        OwnerInput(pct=o.pct, member_id=o.member_id, external_name=o.external_name) for o in owners
    ]


def owners_out(position: Position) -> list[OwnerOut]:
    ownership = position.ownership
    return [
        *(
            OwnerOut(pct=pct, member_id=member_id, external_name=None)
            for member_id, pct in ownership.members.items()
        ),
        *(
            OwnerOut(pct=pct, member_id=None, external_name=name)
            for name, pct in ownership.external.items()
        ),
    ]


def position_out(position: Position) -> PositionOut:
    return PositionOut(
        kind=position.kind,
        id=position.id,
        name=position.name,
        type=position.type,
        asset_class=position.asset_class,
        value=position.value,
        household_value=position.household_value,
        household_pct=position.ownership.household_pct,
        cost=position.cost,
        method=position.method,
        valued_on=position.valued_on,
        account_id=position.account_id,
        institution=position.institution,
        ticker=position.ticker,
        sector=position.sector,
        liquidity=position.liquidity,
        shariah=position.shariah,
        quantity=position.holding.quantity if position.holding else None,
        owners=owners_out(position),
    )


# --- accounts -------------------------------------------------------------------------


@router.get("/accounts")
def list_accounts(access: Viewer, db: Db) -> list[AccountOut]:
    return [AccountOut.model_validate(a) for a in portfolio.list_accounts(db, access.household.id)]


@router.post("/accounts", status_code=status.HTTP_201_CREATED)
def create_account(body: AccountIn, access: Editor, db: Db) -> AccountOut:
    account = portfolio.create_account(db, access.household.id, **body.model_dump())
    db.commit()
    return AccountOut.model_validate(account)


@router.patch("/accounts/{account_id}")
def update_account(
    account_id: uuid.UUID, body: AccountUpdateIn, access: Editor, db: Db
) -> AccountOut:
    account = owned(db, Account, account_id, access.household.id)
    portfolio.update_account(db, account, body.model_dump(exclude_unset=True))
    db.commit()
    return AccountOut.model_validate(account)


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: uuid.UUID, access: Editor, db: Db) -> Response:
    """Removes the account and every holding in it."""
    portfolio.delete_account(db, owned(db, Account, account_id, access.household.id))
    db.commit()
    return no_content()


# --- holdings and transactions --------------------------------------------------------


@router.post("/holdings", status_code=status.HTTP_201_CREATED)
def create_holding(body: HoldingIn, access: Editor, db: Db) -> HoldingOut:
    account = owned(db, Account, body.account_id, access.household.id)
    fields = body.model_dump(exclude={"account_id", "owners"})
    holding = portfolio.create_holding(
        db, access.household.id, account, fields, owner_inputs(body.owners)
    )
    db.commit()
    return HoldingOut.model_validate(holding)


@router.get("/holdings/{holding_id}")
def get_holding(holding_id: uuid.UUID, access: Viewer, db: Db) -> HoldingOut:
    return HoldingOut.model_validate(portfolio.get_holding(db, access.household.id, holding_id))


@router.patch("/holdings/{holding_id}")
def update_holding(
    holding_id: uuid.UUID, body: HoldingUpdateIn, access: Editor, db: Db
) -> HoldingOut:
    """Also where a Mudaraba deposit's final profit rate is entered (FR26.2)."""
    holding = portfolio.get_holding(db, access.household.id, holding_id)
    portfolio.update_holding(db, holding, body.model_dump(exclude_unset=True))
    db.commit()
    return HoldingOut.model_validate(holding)


@router.delete("/holdings/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holding(holding_id: uuid.UUID, access: Editor, db: Db) -> Response:
    portfolio.delete_holding(db, portfolio.get_holding(db, access.household.id, holding_id))
    db.commit()
    return no_content()


@router.get("/holdings/{holding_id}/transactions")
def list_transactions(holding_id: uuid.UUID, access: Viewer, db: Db) -> list[TransactionOut]:
    holding = portfolio.get_holding(db, access.household.id, holding_id)
    return [TransactionOut.model_validate(t) for t in portfolio.list_transactions(db, holding.id)]


@router.post("/holdings/{holding_id}/transactions", status_code=status.HTTP_201_CREATED)
def add_transaction(
    holding_id: uuid.UUID, body: TransactionIn, access: Editor, db: Db
) -> TransactionOut:
    """A purchase, sale, deposit, profit, dividend or tax deducted at source (FR26.6)."""
    holding = portfolio.get_holding(db, access.household.id, holding_id)
    row = portfolio.add_transaction(
        db,
        holding,
        type=body.type.value,
        day=body.date,
        amount=body.amount,
        units=body.units,
        note=body.note,
    )
    db.commit()
    return TransactionOut.model_validate(row)


@router.delete(
    "/holdings/{holding_id}/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_transaction(
    holding_id: uuid.UUID, transaction_id: uuid.UUID, access: Editor, db: Db
) -> Response:
    holding = portfolio.get_holding(db, access.household.id, holding_id)
    portfolio.delete_transaction(db, holding, transaction_id)
    db.commit()
    return no_content()


@router.post("/imports/broker-statement")
def import_broker_statement(body: BrokerCsvIn, access: Editor, db: Db) -> ImportOut:
    """FR14.2: read a broker's portfolio statement (CSV) into a BO account."""
    account = owned(db, Account, body.account_id, access.household.id)
    result = portfolio.import_broker_statement(db, access.household.id, account, body.csv)
    db.commit()
    return ImportOut(imported=result.imported, updated=result.updated, errors=result.errors)


# --- liabilities ----------------------------------------------------------------------


@router.get("/liabilities")
def list_liabilities(access: Viewer, db: Db) -> list[LiabilityOut]:
    rows = portfolio.list_liabilities(db, access.household.id)
    return [LiabilityOut.model_validate(r) for r in rows]


@router.post("/liabilities", status_code=status.HTTP_201_CREATED)
def create_liability(body: LiabilityIn, access: Editor, db: Db) -> LiabilityOut:
    fields = body.model_dump(exclude={"owners"})
    fields["type"] = body.type.value
    row = portfolio.create_liability(db, access.household.id, fields, owner_inputs(body.owners))
    db.commit()
    return LiabilityOut.model_validate(row)


@router.patch("/liabilities/{liability_id}")
def update_liability(
    liability_id: uuid.UUID, body: LiabilityUpdateIn, access: Editor, db: Db
) -> LiabilityOut:
    row = owned(db, Liability, liability_id, access.household.id)
    portfolio.update_liability(db, row, body.model_dump(exclude_unset=True))
    db.commit()
    return LiabilityOut.model_validate(row)


@router.delete("/liabilities/{liability_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_liability(liability_id: uuid.UUID, access: Editor, db: Db) -> Response:
    portfolio.delete_liability(db, owned(db, Liability, liability_id, access.household.id))
    db.commit()
    return no_content()


# --- net worth ------------------------------------------------------------------------


def summary_data(result: Portfolio) -> dict[str, Any]:
    by_member = result.by_member()
    return {
        "as_of_date": result.day,
        "assets": result.assets,
        "liabilities": result.liabilities,
        "net_worth": result.net_worth,
        "by_class": [{"key": k, "value": v} for k, v in result.by_class().items()],
        # FR24.3: one combined view, with each person's part beside it.
        "by_member": [
            {
                "member_id": m.id,
                "display_name": m.display_name,
                "assets": by_member[m.id][0],
                "liabilities": by_member[m.id][1],
                "net_worth": by_member[m.id][0] - by_member[m.id][1],
            }
            for m in result.members
        ],
        "positions": [position_out(p) for p in result.positions],
        "debts": [
            {
                **LiabilityOut.model_validate(d.liability).model_dump(),
                "household_outstanding": d.household_outstanding,
            }
            for d in result.debts
        ],
    }


@router.get("/portfolio/summary")
def portfolio_summary(access: Viewer, db: Db) -> Envelope[dict[str, Any]]:
    """Everything the household owns and owes, valued today, and its net worth (FR14.4)."""
    result = portfolio.summary(db, access.household.id)
    return computed(db, summary_data(result), result.source_ids)


@router.get("/portfolio/market-check")
def portfolio_market_check(access: Viewer, db: Db) -> Envelope[dict[str, Any]]:
    """F6: Shariah share, rate sensitivity, shock exposure and purification of the listed
    holdings."""
    data, result = market_check.market_check(db, access.household.id)
    return computed(db, data, result.source_ids)


@router.get("/portfolio/history")
def net_worth_history(
    access: Viewer, db: Db, since: dt.date | None = None
) -> list[NetWorthPointOut]:
    """Daily net worth as stored by the worker (FR14.4)."""
    rows = portfolio.net_worth_history(db, access.household.id, since)
    return [NetWorthPointOut.model_validate(r) for r in rows]


@router.post("/portfolio/history", status_code=status.HTTP_201_CREATED)
def record_net_worth(access: Editor, db: Db) -> NetWorthPointOut:
    """Store today's net worth now, without waiting for the daily job."""
    row = portfolio.store_net_worth(db, access.household.id, today_dhaka())
    db.commit()
    return NetWorthPointOut.model_validate(row)


# --- performance and allocation -------------------------------------------------------


@router.get("/portfolio/performance")
def portfolio_performance(
    access: Viewer,
    db: Db,
    period: Literal["1Y", "3Y", "5Y", "ALL"] = "ALL",
    account_id: uuid.UUID | None = None,
) -> Envelope[dict[str, Any]]:
    """Time-weighted and money-weighted return, volatility, drawdown, benchmarks and
    diversification (FR15). Describes the past; it does not predict."""
    data, sources = performance.performance(
        db, access.household.id, period=period, account_id=account_id
    )
    return computed(db, data, sources)


@router.get("/portfolio/allocation")
def portfolio_allocation(access: Viewer, db: Db) -> Envelope[dict[str, Any]]:
    """Allocation by class, sector, holding and Shariah status, with drift from the
    household's own target (FR16)."""
    data, sources = performance.allocation(db, access.household.id)
    return computed(db, data, sources)


@router.put("/portfolio/targets")
def set_targets(body: TargetsIn, access: Editor, db: Db) -> list[dict[str, Any]]:
    """Replace the target allocation. Targets must total 100%. Send an empty list to clear."""
    rows = performance.set_targets(
        db,
        access.household.id,
        [(t.asset_class, t.target_pct, t.band_pct) for t in body.targets],
    )
    db.commit()
    return [
        {
            "asset_class": r.asset_class,
            "target_pct": Decimal(r.target_pct),
            "band_pct": Decimal(r.band_pct),
        }
        for r in rows
    ]
