"""Portfolio aggregation (F14): accounts, holdings, transactions, liabilities, net worth.

Functions flush; the route commits. Values come from services/valuation.py.
"""

import csv
import datetime as dt
import io
import re
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core import crypto
from app.models import (
    Account,
    Company,
    Holding,
    Household,
    IslamicProduct,
    Liability,
    NetWorthSnapshot,
    SukukIssue,
    Transaction,
    Valuation,
)
from app.models.enums import AccountType, InstrumentType
from app.services.auth import AuthError
from app.services.costs import ImportResult, parse_amount
from app.services.households import OwnerInput, delete_owner_shares, set_owner_shares
from app.services.valuation import Portfolio, load_portfolio, personal_config, today_dhaka

Q2 = Decimal("0.01")
HUNDRED = Decimal(100)
# Instruments counted in units; the rest are a sum of money.
_UNIT_TYPES = {
    InstrumentType.DSE_SHARE.value,
    InstrumentType.MUTUAL_FUND_UNIT.value,
    InstrumentType.FOREIGN_SECURITY.value,
}


# --- accounts (FR14.1) ----------------------------------------------------------------


def _mask(number: str) -> str:
    digits = re.sub(r"\s+", "", number)
    return f"••••{digits[-4:]}" if len(digits) > 4 else "••••"


def _set_number(account: Account, number: str | None) -> None:
    """Keep the full number encrypted and show only its last digits (FR23.3)."""
    if not number or not number.strip():
        account.masked_number = None
        account.encrypted_number = None
        return
    try:
        account.encrypted_number = crypto.encrypt_text(number.strip())
    except crypto.EncryptionUnavailable as exc:
        raise AuthError("ENCRYPTION_NOT_CONFIGURED", 503) from exc
    account.masked_number = _mask(number)


def list_accounts(db: Session, household_id: uuid.UUID) -> list[Account]:
    return list(
        db.scalars(
            select(Account)
            .where(Account.household_id == household_id)
            .order_by(Account.created_at, Account.name)
        )
    )


def create_account(
    db: Session,
    household_id: uuid.UUID,
    *,
    type: AccountType,
    institution: str,
    name: str,
    number: str | None = None,
) -> Account:
    account = Account(
        household_id=household_id,
        type=type.value,
        institution=institution.strip(),
        name=name.strip(),
    )
    _set_number(account, number)
    db.add(account)
    db.flush()
    return account


def update_account(db: Session, account: Account, changes: dict[str, Any]) -> Account:
    if "number" in changes:
        _set_number(account, changes.pop("number"))
    for name, value in changes.items():
        if value is not None:
            setattr(account, name, value.value if isinstance(value, AccountType) else value)
    db.flush()
    return account


def delete_account(db: Session, account: Account) -> None:
    holding_ids = list(db.scalars(select(Holding.id).where(Holding.account_id == account.id)))
    _forget_assets(db, holding_ids)
    db.delete(account)
    db.flush()


def _forget_assets(db: Session, asset_ids: list[uuid.UUID]) -> None:
    """Owner shares and valuations have no foreign key, so they are removed by hand."""
    if asset_ids:
        delete_owner_shares(db, asset_ids)
        db.execute(delete(Valuation).where(Valuation.asset_id.in_(asset_ids)))


# --- holdings (FR14.2) ----------------------------------------------------------------


def get_holding(db: Session, household_id: uuid.UUID, holding_id: uuid.UUID) -> Holding:
    holding = db.get(Holding, holding_id)
    account = db.get(Account, holding.account_id) if holding else None
    if holding is None or account is None or account.household_id != household_id:
        raise AuthError("NOT_FOUND", 404)
    return holding


def _check_links(db: Session, fields: dict[str, Any]) -> None:
    ticker = fields.get("ticker")
    if ticker:
        fields["ticker"] = ticker.strip().upper()
        if db.scalar(select(Company.id).where(Company.ticker == fields["ticker"])) is None:
            raise AuthError("UNKNOWN_TICKER", 422)
    if fields.get("product_id") and db.get(IslamicProduct, fields["product_id"]) is None:
        raise AuthError("NOT_FOUND", 404)
    if fields.get("sukuk_issue_id") and db.get(SukukIssue, fields["sukuk_issue_id"]) is None:
        raise AuthError("NOT_FOUND", 404)
    start, end = fields.get("start_date"), fields.get("maturity_date")
    if start and end and end < start:
        raise AuthError("VALIDATION", 422)


def create_holding(
    db: Session,
    household_id: uuid.UUID,
    account: Account,
    fields: dict[str, Any],
    owners: list[OwnerInput] | None = None,
) -> Holding:
    """Add a position. An opening transaction is written so later sales have a cost basis."""
    _check_links(db, fields)
    kind = InstrumentType(fields["instrument_type"]).value
    holding = Holding(account_id=account.id, **{**fields, "instrument_type": kind})
    if holding.quantity is None:
        holding.quantity = Decimal(1)
    db.add(holding)
    db.flush()
    opened = holding.start_date or today_dhaka()
    if holding.cost > 0:
        unit_based = kind in _UNIT_TYPES
        db.add(
            Transaction(
                holding_id=holding.id,
                date=opened,
                type="BUY" if unit_based else "DEPOSIT",
                amount=holding.cost,
                units=holding.quantity if unit_based else None,
                note="Opening balance",
            )
        )
    if owners:
        set_owner_shares(db, household_id, "HOLDING", holding.id, owners)
    db.flush()
    return holding


def update_holding(db: Session, holding: Holding, changes: dict[str, Any]) -> Holding:
    dates = {
        "start_date": changes.get("start_date", holding.start_date),
        "maturity_date": changes.get("maturity_date", holding.maturity_date),
    }
    _check_links(db, {**changes, **dates})
    nullable = {
        "manual_value",
        "maturity_date",
        "expected_rate",
        "final_rate",
        "payment_frequency",
        "start_date",
        "ticker",
        "product_id",
        "sukuk_issue_id",
    }
    for name, value in changes.items():
        if value is not None or name in nullable:
            setattr(holding, name, value.upper() if name == "ticker" and value else value)
    db.flush()
    return holding


def delete_holding(db: Session, holding: Holding) -> None:
    _forget_assets(db, [holding.id])
    db.delete(holding)
    db.flush()


# --- transactions ---------------------------------------------------------------------

# Types whose effect on the holding can be undone exactly when the record is removed.
_REVERSIBLE = {"BUY", "DEPOSIT", "DIVIDEND", "PROFIT", "TAX", "FEE", "BONUS"}


def _apply(holding: Holding, type_: str, amount: Decimal, units: Decimal | None, sign: int) -> None:
    """Move the holding's running totals for one transaction. `sign` is -1 to undo."""
    signed = amount * sign
    count = (units or Decimal(0)) * sign
    if type_ == "BUY":
        holding.quantity += count
        holding.cost += signed
    elif type_ == "BONUS":
        holding.quantity += count
    elif type_ == "FEE":
        holding.cost += signed
    elif type_ == "DEPOSIT":
        holding.cost += signed
        if holding.manual_value is not None:
            holding.manual_value += signed
    elif type_ in ("DIVIDEND", "PROFIT"):
        holding.profit_received += signed
    elif type_ == "TAX":
        holding.tax_deducted += signed
    elif type_ == "SELL":
        if units is None or units <= 0 or units > holding.quantity:
            raise AuthError("NOT_ENOUGH_UNITS", 422)
        # Average cost: the cost leaves in proportion to the units sold.
        basis = (holding.cost * units / holding.quantity).quantize(Q2)
        holding.quantity -= units
        holding.cost -= basis
    elif type_ == "WITHDRAWAL":
        value = holding.manual_value if holding.manual_value is not None else holding.cost
        if amount > value:
            raise AuthError("NOT_ENOUGH_BALANCE", 422)
        share = amount / value if value > 0 else Decimal(1)
        holding.cost -= (holding.cost * share).quantize(Q2)
        if holding.manual_value is not None:
            holding.manual_value -= amount


def add_transaction(
    db: Session,
    holding: Holding,
    *,
    type: str,
    day: dt.date,
    amount: Decimal,
    units: Decimal | None = None,
    note: str | None = None,
) -> Transaction:
    """Record a purchase, sale, deposit, profit or tax, and update the holding's totals."""
    if type in ("BUY", "SELL", "BONUS") and (units is None or units <= 0):
        raise AuthError("UNITS_REQUIRED", 422)
    _apply(holding, type, amount, units, 1)
    row = Transaction(
        holding_id=holding.id,
        date=day,
        type=type,
        amount=amount,
        units=units,
        note=(note or "").strip() or None,
    )
    db.add(row)
    db.flush()
    return row


def list_transactions(db: Session, holding_id: uuid.UUID) -> list[Transaction]:
    return list(
        db.scalars(
            select(Transaction)
            .where(Transaction.holding_id == holding_id)
            .order_by(Transaction.date.desc(), Transaction.created_at.desc())
        )
    )


def delete_transaction(db: Session, holding: Holding, transaction_id: uuid.UUID) -> None:
    row = db.get(Transaction, transaction_id)
    if row is None or row.holding_id != holding.id:
        raise AuthError("NOT_FOUND", 404)
    if row.type not in _REVERSIBLE:
        # A sale or withdrawal changed the average cost; undoing it would guess.
        raise AuthError("TRANSACTION_NOT_REVERSIBLE", 409)
    if row.type in ("BUY", "BONUS") and (row.units or 0) > holding.quantity:
        raise AuthError("TRANSACTION_NOT_REVERSIBLE", 409)
    _apply(holding, row.type, row.amount, row.units, -1)
    db.delete(row)
    db.flush()


# --- liabilities ----------------------------------------------------------------------


def list_liabilities(db: Session, household_id: uuid.UUID) -> list[Liability]:
    return list(
        db.scalars(
            select(Liability)
            .where(Liability.household_id == household_id)
            .order_by(Liability.created_at, Liability.name)
        )
    )


def create_liability(
    db: Session, household_id: uuid.UUID, fields: dict[str, Any], owners: list[OwnerInput] | None
) -> Liability:
    if fields.get("due_within_year", Decimal(0)) > fields["outstanding"]:
        raise AuthError("VALIDATION", 422)
    row = Liability(household_id=household_id, **fields)
    db.add(row)
    db.flush()
    if owners:
        set_owner_shares(db, household_id, "LIABILITY", row.id, owners)
    return row


def update_liability(db: Session, row: Liability, changes: dict[str, Any]) -> Liability:
    for name, value in changes.items():
        if value is not None or name in ("lender", "end_date"):
            setattr(row, name, value)
    if row.due_within_year > row.outstanding:
        raise AuthError("VALIDATION", 422)
    db.flush()
    return row


def delete_liability(db: Session, row: Liability) -> None:
    _forget_assets(db, [row.id])
    db.delete(row)
    db.flush()


# --- net worth (FR14.4) ---------------------------------------------------------------


def capital_at_work(portfolio: Portfolio) -> Decimal:
    """See `ace.capital_at_work`; imported here so the snapshot and the card agree."""
    from app.services.ace import capital_at_work as measure

    return measure(portfolio)


def store_net_worth(db: Session, household_id: uuid.UUID, day: dt.date) -> NetWorthSnapshot:
    """Write (or rewrite) one day's net worth. Run daily by the worker."""
    portfolio = load_portfolio(db, household_id, day)
    row = db.scalar(
        select(NetWorthSnapshot).where(
            NetWorthSnapshot.household_id == household_id, NetWorthSnapshot.date == day
        )
    )
    if row is None:
        row = NetWorthSnapshot(household_id=household_id, date=day)
        db.add(row)
    row.assets = portfolio.assets
    row.liabilities = portfolio.liabilities
    row.net_worth = portfolio.net_worth
    row.breakdown = {key: str(value) for key, value in portfolio.by_class().items()}
    row.capital = capital_at_work(portfolio)
    db.flush()
    return row


def store_all_net_worth(db: Session, day: dt.date | None = None) -> int:
    day = day or today_dhaka()
    household_ids = list(db.scalars(select(Household.id)))
    for household_id in household_ids:
        store_net_worth(db, household_id, day)
    return len(household_ids)


def net_worth_history(
    db: Session, household_id: uuid.UUID, since: dt.date | None = None
) -> list[NetWorthSnapshot]:
    statement = select(NetWorthSnapshot).where(NetWorthSnapshot.household_id == household_id)
    if since:
        statement = statement.where(NetWorthSnapshot.date >= since)
    return list(db.scalars(statement.order_by(NetWorthSnapshot.date)))


def summary(db: Session, household_id: uuid.UUID) -> Portfolio:
    return load_portfolio(db, household_id)


# --- broker statement import (FR14.2) -------------------------------------------------


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


@dataclass
class BrokerImportResult(ImportResult):
    updated: int = 0
    tickers: list[str] = field(default_factory=list)


def import_broker_statement(
    db: Session, household_id: uuid.UUID, account: Account, text: str
) -> BrokerImportResult:
    """Read a broker's portfolio statement (CSV) into a BO account.

    Column names differ by broker, so each column is found by the aliases in
    config/personal.yaml. A ticker already in the account has its quantity and cost
    replaced with the statement's; a new one is added. Unknown tickers are reported.
    """
    aliases: dict[str, list[str]] = personal_config()["portfolio"]["broker_csv"]  # type: ignore[index]
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    header_at = -1
    columns: dict[str, int] = {}
    # Statements often start with the broker's name and the client's details.
    for index, row in enumerate(rows[:30]):
        cells = [_norm(cell) for cell in row]
        found: dict[str, int] = {}
        for name, options in aliases.items():
            for alias in (_norm(option) for option in options):
                if alias in cells:
                    found[name] = cells.index(alias)
                    break
        if "ticker" in found and "quantity" in found:
            header_at, columns = index, found
            break
    if header_at < 0 or not ({"average_cost", "total_cost"} & set(columns)):
        raise AuthError("CSV_HEADER_INVALID", 422)

    existing = {
        h.ticker: h
        for h in db.scalars(
            select(Holding).where(Holding.account_id == account.id, Holding.ticker.is_not(None))
        )
    }
    known = set(db.scalars(select(Company.ticker)))
    result = BrokerImportResult()

    def cell(row: list[str], name: str) -> str:
        position = columns.get(name)
        return row[position].strip() if position is not None and position < len(row) else ""

    for number, row in enumerate(rows[header_at + 1 :], start=header_at + 2):
        ticker = cell(row, "ticker").upper()
        if not ticker or not any(c.strip() for c in row):
            continue
        quantity = parse_amount(cell(row, "quantity"))
        total = parse_amount(cell(row, "total_cost"))
        average = parse_amount(cell(row, "average_cost"))
        if quantity is None:
            # Totals rows and footers have text where the ticker is and no quantity.
            if ticker in known:
                result.errors.append({"row": number, "code": "BAD_QUANTITY"})
            continue
        if ticker not in known:
            result.errors.append({"row": number, "code": "UNKNOWN_TICKER", "value": ticker[:20]})
            continue
        cost = (
            total if total is not None else (average * quantity).quantize(Q2) if average else None
        )
        if cost is None:
            result.errors.append({"row": number, "code": "BAD_AMOUNT"})
            continue
        holding = existing.get(ticker)
        if holding is not None:
            holding.quantity, holding.cost, holding.is_active = quantity, cost, True
            result.updated += 1
        else:
            holding = create_holding(
                db,
                household_id,
                account,
                {
                    "instrument_type": InstrumentType.DSE_SHARE,
                    "name": ticker,
                    "ticker": ticker,
                    "quantity": quantity,
                    "cost": cost,
                },
            )
            existing[ticker] = holding
            result.imported += 1
        result.tickers.append(ticker)
    db.flush()
    return result
