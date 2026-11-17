"""Alternative investments (F25): land, gold, business stakes, private loans and the like.

Values are entered by the household, with a reminder to revalue; gold and silver are valued
from the price per gram. Cash flows give a money-weighted return (XIRR). Documents are
stored encrypted. Nothing here rates a deal or recommends one (FR25.9).
"""

import base64
import binascii
import datetime as dt
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.analytics.costs import add_months
from app.analytics.returns import xirr
from app.core import crypto
from app.core.app_config import get_config
from app.models import AltAsset, CashFlow, Document, Valuation
from app.models.enums import AltAssetType, ValuationMethod
from app.services.auth import AuthError
from app.services.households import OwnerInput, delete_owner_shares, owned, set_owner_shares
from app.services.storage import DocumentStorage
from app.services.valuation import (
    Portfolio,
    Position,
    latest_macro,
    load_portfolio,
    personal_config,
    today_dhaka,
)

Q2 = Decimal("0.01")
_NULLABLE = {
    "purchase_date",
    "counterparty",
    "expected_exit_date",
    "notes",
    "weight_grams",
    "karat",
    "shariah_reason",
    "zakat_rule",
    "due_diligence",
}


def get_asset(db: Session, household_id: uuid.UUID, asset_id: uuid.UUID) -> AltAsset:
    return owned(db, AltAsset, asset_id, household_id)


def _validate(db: Session, fields: dict[str, Any]) -> None:
    rule = fields.get("zakat_rule")
    if rule and rule not in get_config("zakat").data["assets"]:
        raise AuthError("VALIDATION", 422)
    checklist = fields.get("due_diligence")
    if checklist is not None:
        allowed = {
            *personal_config()["due_diligence"]["checklist"],  # type: ignore[index]
            "promised_return_pct",
        }
        if set(checklist) - allowed:
            raise AuthError("VALIDATION", 422)


def create_asset(
    db: Session,
    household_id: uuid.UUID,
    fields: dict[str, Any],
    owners: list[OwnerInput] | None = None,
    *,
    current_value: Decimal | None = None,
) -> AltAsset:
    _validate(db, fields)
    fields = {**fields, "type": AltAssetType(fields["type"]).value}
    checklist = fields.get("due_diligence")
    if checklist and "promised_return_pct" in checklist:
        fields["due_diligence"] = _with_tbill(db, checklist)
    asset = AltAsset(household_id=household_id, **fields)
    db.add(asset)
    db.flush()
    if current_value is not None:
        add_valuation(db, asset, today_dhaka(), current_value)
    if owners:
        set_owner_shares(db, household_id, "ALT_ASSET", asset.id, owners)
    return asset


def _with_tbill(db: Session, checklist: dict[str, Any]) -> dict[str, Any]:
    """Keep the T-bill yield of the day beside a promised return (FR25.9), for reference."""
    code = str(personal_config()["performance"]["risk_free_series"])  # type: ignore[index]
    tbill = latest_macro(db, code)
    if tbill is None or "tbill_yield_pct_at_entry" in checklist:
        return checklist
    return {**checklist, "tbill_yield_pct_at_entry": str(tbill.value.normalize())}


def update_asset(db: Session, asset: AltAsset, changes: dict[str, Any]) -> AltAsset:
    _validate(db, changes)
    if changes.get("due_diligence") and "promised_return_pct" in changes["due_diligence"]:
        previous = (asset.due_diligence or {}).get("tbill_yield_pct_at_entry")
        merged = {**changes["due_diligence"]}
        if previous is not None:
            merged["tbill_yield_pct_at_entry"] = previous
        changes["due_diligence"] = _with_tbill(db, merged)
    for name, value in changes.items():
        if value is not None or name in _NULLABLE:
            setattr(asset, name, value)
    db.flush()
    return asset


def delete_asset(db: Session, asset: AltAsset, storage: DocumentStorage) -> None:
    for document in db.scalars(select(Document).where(Document.asset_id == asset.id)):
        storage.delete(document.encrypted_blob_ref)
    delete_owner_shares(db, [asset.id])
    db.execute(delete(Valuation).where(Valuation.asset_id == asset.id))
    db.delete(asset)
    db.flush()


# --- valuations (FR25.2) --------------------------------------------------------------


def list_valuations(db: Session, asset_id: uuid.UUID) -> list[Valuation]:
    return list(
        db.scalars(
            select(Valuation)
            .where(Valuation.asset_kind == "ALT_ASSET", Valuation.asset_id == asset_id)
            .order_by(Valuation.date.desc())
        )
    )


def add_valuation(db: Session, asset: AltAsset, day: dt.date, value: Decimal) -> Valuation:
    """Record what the asset is worth on a date. A second entry for a date replaces the first."""
    row = db.scalar(
        select(Valuation).where(
            Valuation.asset_kind == "ALT_ASSET",
            Valuation.asset_id == asset.id,
            Valuation.date == day,
        )
    )
    if row is None:
        row = Valuation(asset_kind="ALT_ASSET", asset_id=asset.id, date=day)
        db.add(row)
    row.value = value
    row.method = ValuationMethod.MANUAL.value
    db.flush()
    return row


def delete_valuation(db: Session, asset: AltAsset, valuation_id: uuid.UUID) -> None:
    row = db.get(Valuation, valuation_id)
    if row is None or row.asset_id != asset.id:
        raise AuthError("NOT_FOUND", 404)
    db.delete(row)
    db.flush()


def revaluation_due(
    asset: AltAsset, last_valued: dt.date | None, method: str, today: dt.date
) -> dt.date | None:
    """The date a fresh value was due, when it has passed. Metals reprice daily."""
    if method == "METAL_PRICE" or not asset.is_active:
        return None
    basis = last_valued or asset.purchase_date
    if basis is None:
        return today
    due = add_months(basis, asset.revaluation_months)
    return due if due <= today else None


# --- cash flows and return (FR25.3) ---------------------------------------------------


def list_cash_flows(db: Session, asset_id: uuid.UUID) -> list[CashFlow]:
    return list(
        db.scalars(
            select(CashFlow).where(CashFlow.asset_id == asset_id).order_by(CashFlow.date.desc())
        )
    )


def add_cash_flow(
    db: Session, asset: AltAsset, *, day: dt.date, amount: Decimal, type: str, note: str | None
) -> CashFlow:
    """Money received is positive; money put in is negative."""
    if amount == 0:
        raise AuthError("VALIDATION", 422)
    row = CashFlow(
        asset_id=asset.id, date=day, amount=amount, type=type, note=(note or "").strip() or None
    )
    db.add(row)
    db.flush()
    return row


def delete_cash_flow(db: Session, asset: AltAsset, flow_id: uuid.UUID) -> None:
    row = db.get(CashFlow, flow_id)
    if row is None or row.asset_id != asset.id:
        raise AuthError("NOT_FOUND", 404)
    db.delete(row)
    db.flush()


def asset_xirr(
    asset: AltAsset, flows: list[CashFlow], value: Decimal, today: dt.date
) -> Decimal | None:
    """Yearly money-weighted return: recorded flows plus today's value as the last flow.

    When no money going in was recorded, the purchase cost on the purchase date is used.
    """
    series = [(flow.date, flow.amount) for flow in flows]
    if not any(amount < 0 for _, amount in series) and asset.purchase_date and asset.cost > 0:
        series.append((asset.purchase_date, -asset.cost))
    series.append((today, value))
    return xirr(series)


# --- documents (FR25.4) ---------------------------------------------------------------


def list_documents(db: Session, asset_id: uuid.UUID) -> list[Document]:
    return list(
        db.scalars(
            select(Document).where(Document.asset_id == asset_id).order_by(Document.created_at)
        )
    )


def add_document(
    db: Session,
    asset: AltAsset,
    storage: DocumentStorage,
    *,
    type: str,
    filename: str,
    content_base64: str,
    uploaded_by: uuid.UUID,
) -> Document:
    config = personal_config()["documents"]
    assert isinstance(config, dict)
    if type not in config["types"]:
        raise AuthError("VALIDATION", 422)
    try:
        data = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AuthError("VALIDATION", 422) from exc
    if not data:
        raise AuthError("VALIDATION", 422)
    if len(data) > int(config["max_bytes"]):
        raise AuthError("DOCUMENT_TOO_LARGE", 413)
    try:
        ref = storage.put(data)
    except crypto.EncryptionUnavailable as exc:
        raise AuthError("ENCRYPTION_NOT_CONFIGURED", 503) from exc
    # Keep only the name, never a path the browser may have sent.
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()[:255] or "document"
    row = Document(
        asset_id=asset.id,
        type=type,
        filename=name,
        size_bytes=len(data),
        encrypted_blob_ref=ref,
        uploaded_by=uploaded_by,
    )
    db.add(row)
    db.flush()
    return row


def _document(db: Session, asset: AltAsset, document_id: uuid.UUID) -> Document:
    row = db.get(Document, document_id)
    if row is None or row.asset_id != asset.id:
        raise AuthError("NOT_FOUND", 404)
    return row


def read_document(
    db: Session, asset: AltAsset, storage: DocumentStorage, document_id: uuid.UUID
) -> tuple[Document, bytes]:
    row = _document(db, asset, document_id)
    try:
        return row, storage.get(row.encrypted_blob_ref)
    except (crypto.EncryptionUnavailable, FileNotFoundError) as exc:
        raise AuthError("DOCUMENT_UNAVAILABLE", 503) from exc


def delete_document(
    db: Session, asset: AltAsset, storage: DocumentStorage, document_id: uuid.UUID
) -> None:
    row = _document(db, asset, document_id)
    storage.delete(row.encrypted_blob_ref)
    db.delete(row)
    db.flush()


# --- views ----------------------------------------------------------------------------


@dataclass
class AssetView:
    asset: AltAsset
    position: Position
    xirr_pct: Decimal | None
    net_cash_received: Decimal
    revaluation_due: dt.date | None


def _view(db: Session, position: Position, today: dt.date) -> AssetView:
    asset = position.alt
    assert asset is not None
    flows = list_cash_flows(db, asset.id)
    return AssetView(
        asset=asset,
        position=position,
        xirr_pct=asset_xirr(asset, flows, position.value, today),
        net_cash_received=sum((f.amount for f in flows if f.amount > 0), Decimal(0)),
        revaluation_due=revaluation_due(asset, position.valued_on, position.method, today),
    )


def list_views(db: Session, household_id: uuid.UUID) -> tuple[list[AssetView], Portfolio]:
    portfolio = load_portfolio(db, household_id, active_only=False)
    today = portfolio.day
    views = [_view(db, p, today) for p in portfolio.positions if p.kind == "ALT_ASSET"]
    return views, portfolio


def get_view(
    db: Session, household_id: uuid.UUID, asset_id: uuid.UUID
) -> tuple[AssetView, Portfolio]:
    views, portfolio = list_views(db, household_id)
    for view in views:
        if view.asset.id == asset_id:
            return view, portfolio
    raise AuthError("NOT_FOUND", 404)


def due_diligence_context(db: Session) -> dict[str, Any]:
    """The checklist questions and today's T-bill yield, for comparison with a promised
    return (FR25.9). Facts only: no score, no verdict."""
    config = personal_config()
    code = str(config["performance"]["risk_free_series"])  # type: ignore[index]
    tbill = latest_macro(db, code)
    return {
        "checklist": list(config["due_diligence"]["checklist"]),  # type: ignore[index]
        "tbill_yield_pct": tbill.value if tbill else None,
        "tbill_date": tbill.date if tbill else None,
        "source_id": tbill.source_id if tbill else None,
    }
