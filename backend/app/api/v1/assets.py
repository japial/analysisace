"""Alternative investments (F25) and sukuk and Islamic bank investments (F26)."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import CurrentUser, Db, Editor, Viewer, require_permission
from app.api.envelopes import computed
from app.api.v1.households import no_content
from app.api.v1.portfolio import owner_inputs, owners_out, position_out
from app.core.permissions import Permission
from app.models import User
from app.schemas.common import Envelope
from app.schemas.personal import (
    AltAssetDetailOut,
    AltAssetIn,
    AltAssetOut,
    AltAssetUpdateIn,
    AltAssetViewOut,
    BankFlagIn,
    BankFlagOut,
    CashFlowIn,
    CashFlowOut,
    DocumentIn,
    DocumentOut,
    IslamicProductOut,
    SukukIssueOut,
    ValuationIn,
    ValuationOut,
)
from app.services import alt_assets, islamic
from app.services.storage import DocumentStorage, get_document_storage

router = APIRouter(tags=["assets"])
HOUSEHOLD = "/households/{household_id}"

Storage = Annotated[DocumentStorage, Depends(get_document_storage)]
ConfigManager = Annotated[User, Depends(require_permission(Permission.CONFIG_MANAGE))]


def _view_out(view: alt_assets.AssetView) -> AltAssetViewOut:
    position = view.position
    return AltAssetViewOut(
        **AltAssetOut.model_validate(view.asset).model_dump(),
        value=position.value,
        household_value=position.household_value,
        household_pct=position.ownership.household_pct,
        value_method=position.method,
        valued_on=position.valued_on,
        asset_class=position.asset_class,
        xirr_pct=view.xirr_pct,
        cash_received=view.net_cash_received,
        revaluation_due=view.revaluation_due,
        owners=owners_out(position),
    )


# --- F25 alternative investments ------------------------------------------------------


@router.get(f"{HOUSEHOLD}/alt-assets")
def list_alt_assets(access: Viewer, db: Db) -> Envelope[list[AltAssetViewOut]]:
    views, portfolio = alt_assets.list_views(db, access.household.id)
    return computed(db, [_view_out(v) for v in views], portfolio.source_ids)


@router.get(f"{HOUSEHOLD}/alt-assets/due-diligence")
def due_diligence(access: Viewer, db: Db) -> Envelope[dict[str, Any]]:
    """FR25.9: the checklist for a private deal and today's T-bill yield to set a promised
    return against. Facts only; no rating is produced."""
    context = alt_assets.due_diligence_context(db)
    source_id = context.pop("source_id")
    return computed(db, context, [source_id])


@router.post(f"{HOUSEHOLD}/alt-assets", status_code=status.HTTP_201_CREATED)
def create_alt_asset(body: AltAssetIn, access: Editor, db: Db) -> AltAssetOut:
    fields = body.model_dump(exclude={"owners", "current_value"})
    fields.update(
        type=body.type, liquidity=body.liquidity.value, shariah_flag=body.shariah_flag.value
    )
    asset = alt_assets.create_asset(
        db,
        access.household.id,
        fields,
        owner_inputs(body.owners),
        current_value=body.current_value,
    )
    db.commit()
    return AltAssetOut.model_validate(asset)


@router.get(f"{HOUSEHOLD}/alt-assets/{{asset_id}}")
def get_alt_asset(asset_id: uuid.UUID, access: Viewer, db: Db) -> Envelope[AltAssetDetailOut]:
    view, portfolio = alt_assets.get_view(db, access.household.id, asset_id)
    detail = AltAssetDetailOut(
        asset=_view_out(view),
        valuations=[
            ValuationOut.model_validate(v) for v in alt_assets.list_valuations(db, asset_id)
        ],
        cash_flows=[
            CashFlowOut.model_validate(f) for f in alt_assets.list_cash_flows(db, asset_id)
        ],
        documents=[DocumentOut.model_validate(d) for d in alt_assets.list_documents(db, asset_id)],
    )
    return computed(db, detail, portfolio.source_ids)


@router.patch(f"{HOUSEHOLD}/alt-assets/{{asset_id}}")
def update_alt_asset(
    asset_id: uuid.UUID, body: AltAssetUpdateIn, access: Editor, db: Db
) -> AltAssetOut:
    asset = alt_assets.get_asset(db, access.household.id, asset_id)
    changes = body.model_dump(exclude_unset=True)
    for name in ("liquidity", "shariah_flag"):
        if changes.get(name) is not None:
            changes[name] = changes[name].value
    alt_assets.update_asset(db, asset, changes)
    db.commit()
    return AltAssetOut.model_validate(asset)


@router.delete(f"{HOUSEHOLD}/alt-assets/{{asset_id}}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alt_asset(asset_id: uuid.UUID, access: Editor, db: Db, storage: Storage) -> Response:
    alt_assets.delete_asset(db, alt_assets.get_asset(db, access.household.id, asset_id), storage)
    db.commit()
    return no_content()


@router.post(f"{HOUSEHOLD}/alt-assets/{{asset_id}}/valuations", status_code=201)
def add_valuation(asset_id: uuid.UUID, body: ValuationIn, access: Editor, db: Db) -> ValuationOut:
    """FR25.2: a new value for the asset. History is kept."""
    asset = alt_assets.get_asset(db, access.household.id, asset_id)
    row = alt_assets.add_valuation(db, asset, body.date, body.value)
    db.commit()
    return ValuationOut.model_validate(row)


@router.delete(f"{HOUSEHOLD}/alt-assets/{{asset_id}}/valuations/{{valuation_id}}", status_code=204)
def delete_valuation(
    asset_id: uuid.UUID, valuation_id: uuid.UUID, access: Editor, db: Db
) -> Response:
    asset = alt_assets.get_asset(db, access.household.id, asset_id)
    alt_assets.delete_valuation(db, asset, valuation_id)
    db.commit()
    return no_content()


@router.post(f"{HOUSEHOLD}/alt-assets/{{asset_id}}/cash-flows", status_code=201)
def add_cash_flow(asset_id: uuid.UUID, body: CashFlowIn, access: Editor, db: Db) -> CashFlowOut:
    """FR25.3: rent, profit share, instalment, capital added or sale proceeds."""
    asset = alt_assets.get_asset(db, access.household.id, asset_id)
    row = alt_assets.add_cash_flow(
        db, asset, day=body.date, amount=body.amount, type=body.type.value, note=body.note
    )
    db.commit()
    return CashFlowOut.model_validate(row)


@router.delete(f"{HOUSEHOLD}/alt-assets/{{asset_id}}/cash-flows/{{flow_id}}", status_code=204)
def delete_cash_flow(asset_id: uuid.UUID, flow_id: uuid.UUID, access: Editor, db: Db) -> Response:
    asset = alt_assets.get_asset(db, access.household.id, asset_id)
    alt_assets.delete_cash_flow(db, asset, flow_id)
    db.commit()
    return no_content()


@router.post(f"{HOUSEHOLD}/alt-assets/{{asset_id}}/documents", status_code=201)
def add_document(
    asset_id: uuid.UUID, body: DocumentIn, access: Editor, db: Db, storage: Storage
) -> DocumentOut:
    """FR25.4: attach a deed, agreement or receipt. Stored encrypted."""
    asset = alt_assets.get_asset(db, access.household.id, asset_id)
    row = alt_assets.add_document(
        db,
        asset,
        storage,
        type=body.type,
        filename=body.filename,
        content_base64=body.content_base64,
        uploaded_by=access.user.id,
    )
    db.commit()
    return DocumentOut.model_validate(row)


@router.get(f"{HOUSEHOLD}/alt-assets/{{asset_id}}/documents/{{document_id}}")
def download_document(
    asset_id: uuid.UUID, document_id: uuid.UUID, access: Viewer, db: Db, storage: Storage
) -> Response:
    asset = alt_assets.get_asset(db, access.household.id, asset_id)
    row, data = alt_assets.read_document(db, asset, storage, document_id)
    safe_name = "".join(
        c if c.isascii() and (c.isalnum() or c in "._- ") else "_" for c in row.filename
    )
    return Response(
        data,
        # Never a type the browser would render: a stored file must only ever download.
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.delete(f"{HOUSEHOLD}/alt-assets/{{asset_id}}/documents/{{document_id}}", status_code=204)
def delete_document(
    asset_id: uuid.UUID, document_id: uuid.UUID, access: Editor, db: Db, storage: Storage
) -> Response:
    asset = alt_assets.get_asset(db, access.household.id, asset_id)
    alt_assets.delete_document(db, asset, storage, document_id)
    db.commit()
    return no_content()


# --- F26 sukuk and Islamic bank investments -------------------------------------------


@router.get("/islamic-products")
def list_products(_: CurrentUser, db: Db) -> Envelope[list[IslamicProductOut]]:
    """The product catalogue (F26). Names and rates are as each bank states them."""
    rows = islamic.list_products(db)
    return computed(
        db, [IslamicProductOut.model_validate(r) for r in rows], {r.source_id for r in rows}
    )


@router.get("/islamic-products/compare")
def compare_products(_: CurrentUser, db: Db) -> Envelope[dict[str, Any]]:
    """FR26.4: expected rates beside the 91-day T-bill yield and CPI inflation, with the
    return above inflation. Information only."""
    result = islamic.compare(db)
    data = {
        "tbill_pct": result.tbill_pct,
        "tbill_date": result.tbill_date,
        "inflation_pct": result.inflation_pct,
        "inflation_date": result.inflation_date,
        "rows": result.rows,
    }
    return computed(db, data, result.source_ids)


@router.get("/sukuk/issues")
def list_sukuk(_: CurrentUser, db: Db) -> Envelope[list[SukukIssueOut]]:
    rows = islamic.list_sukuk(db)
    return computed(
        db, [SukukIssueOut.model_validate(r) for r in rows], {r.source_id for r in rows}
    )


@router.get(f"{HOUSEHOLD}/sukuk/holdings")
def sukuk_holdings(access: Viewer, db: Db) -> Envelope[list[dict[str, Any]]]:
    """The household's sukuk and Islamic deposits with profit so far. A Mudaraba rate is
    provisional until the bank's final rate is entered (FR26.2)."""
    rows, portfolio = islamic.islamic_holdings(db, access.household.id)
    data = [
        {
            **position_out(r.position).model_dump(),
            "start_date": r.position.holding.start_date if r.position.holding else None,
            "maturity_date": r.position.holding.maturity_date if r.position.holding else None,
            "payment_frequency": r.position.holding.payment_frequency
            if r.position.holding
            else None,
            "rate_pct": r.rate_pct,
            "rate_is_final": r.rate_is_final,
            "profit_at_rate": r.profit_at_rate,
            "profit_received": r.profit_received,
            "tax_deducted": r.tax_deducted,
            "days_to_maturity": r.days_to_maturity,
        }
        for r in rows
    ]
    return computed(db, data, portfolio.source_ids)


@router.get(f"{HOUSEHOLD}/sukuk/calendar")
def sukuk_calendar(
    access: Viewer, db: Db, days: Annotated[int, Query(ge=1, le=3650)] = 365
) -> list[dict[str, Any]]:
    """FR26.3: maturities of the household's holdings and upcoming government sukuk auctions."""
    return islamic.calendar(db, access.household.id, days=days)


@router.get(f"{HOUSEHOLD}/sukuk/bank-safety")
def bank_safety(access: Viewer, db: Db) -> list[dict[str, Any]]:
    """FR26.5: how the household's bank money is spread, with any notice on a bank."""
    return islamic.bank_safety(db, access.household.id)


@router.get("/admin/bank-flags")
def list_bank_flags(_: ConfigManager, db: Db) -> list[BankFlagOut]:
    return [BankFlagOut.model_validate(f) for f in islamic.list_bank_flags(db)]


@router.put("/admin/bank-flags")
def set_bank_flag(body: BankFlagIn, actor: ConfigManager, db: Db) -> BankFlagOut:
    """Add or change the notice on a bank (FR26.5). Keep it neutral and sourced."""
    flag = islamic.set_bank_flag(
        db,
        actor,
        bank=body.bank,
        status=body.status,
        note_en=body.note_en,
        note_bn=body.note_bn,
        source_links=[link.model_dump() for link in body.source_links],
    )
    db.commit()
    return BankFlagOut.model_validate(flag)


@router.delete("/admin/bank-flags/{flag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bank_flag(flag_id: uuid.UUID, actor: ConfigManager, db: Db) -> Response:
    islamic.delete_bank_flag(db, actor, flag_id)
    db.commit()
    return no_content()
