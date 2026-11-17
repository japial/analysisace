"""Zakat and tax snapshots (F13), FIRE plans (F17), scenarios (F18) and goals (F19)."""

import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app.analytics.fire import FireInputs
from app.api.deps import Db, Editor, Viewer
from app.api.envelopes import computed
from app.api.v1.households import no_content
from app.models import Event, Goal
from app.schemas.common import Envelope
from app.schemas.personal import (
    EventOut,
    FirePlanDetailOut,
    FirePlanIn,
    FirePlanOut,
    GoalIn,
    GoalOut,
    GoalProgressOut,
    GoalUpdateIn,
    ScenarioIn,
    ScenarioOut,
    TaxIn,
    TaxSnapshotOut,
    ZakatIn,
    ZakatSnapshotOut,
)
from app.services import households, planning, zakat_tax
from app.services.auth import ConsentPurpose
from app.services.valuation import load_portfolio, today_dhaka

router = APIRouter(tags=["planning"])
HOUSEHOLD = "/households/{household_id}"


# --- F13 Zakat ------------------------------------------------------------------------


@router.post(f"{HOUSEHOLD}/zakat/snapshots", status_code=status.HTTP_201_CREATED)
def create_zakat_snapshot(body: ZakatIn, access: Editor, db: Db) -> Envelope[ZakatSnapshotOut]:
    """Work out one person's Zakat on a date and keep every line (FR13.1 to FR13.4).

    Needs the "Zakat and Shariah preferences" consent (FR23.2). The rules are provisional
    until a Shariah advisor approves them; `config_version` records which were used.
    """
    member = households.get_member(db, access.household.id, body.member_id)
    snapshot, sources = zakat_tax.create_zakat_snapshot(
        db,
        access.user,
        access.household.id,
        member,
        day=body.date,
        nisab_basis=body.nisab_basis.value if body.nisab_basis else None,
        price_per_gram=body.price_per_gram,
        shares_method=body.shares_method,
    )
    db.commit()
    return computed(db, ZakatSnapshotOut.model_validate(snapshot), sources)


@router.get(f"{HOUSEHOLD}/zakat/snapshots")
def list_zakat_snapshots(access: Viewer, db: Db) -> list[ZakatSnapshotOut]:
    households.require_consent(access.user, ConsentPurpose.RELIGIOUS_PREFERENCES)
    rows = zakat_tax.list_zakat_snapshots(db, access.household.id)
    return [ZakatSnapshotOut.model_validate(r) for r in rows]


@router.get(f"{HOUSEHOLD}/zakat/snapshots/{{snapshot_id}}")
def get_zakat_snapshot(snapshot_id: uuid.UUID, access: Viewer, db: Db) -> ZakatSnapshotOut:
    households.require_consent(access.user, ConsentPurpose.RELIGIOUS_PREFERENCES)
    row = zakat_tax.get_zakat_snapshot(db, access.household.id, snapshot_id)
    return ZakatSnapshotOut.model_validate(row)


@router.delete(f"{HOUSEHOLD}/zakat/snapshots/{{snapshot_id}}", status_code=204)
def delete_zakat_snapshot(snapshot_id: uuid.UUID, access: Editor, db: Db) -> Response:
    db.delete(zakat_tax.get_zakat_snapshot(db, access.household.id, snapshot_id))
    db.commit()
    return no_content()


# --- F13 tax --------------------------------------------------------------------------


@router.get(f"{HOUSEHOLD}/tax/current-year")
def current_tax_year(access: Viewer) -> dict[str, str]:
    return {"tax_year": zakat_tax.current_tax_year(today_dhaka())}


@router.post(f"{HOUSEHOLD}/tax/snapshots", status_code=status.HTTP_201_CREATED)
def create_tax_snapshot(body: TaxIn, access: Editor, db: Db) -> Envelope[TaxSnapshotOut]:
    """Figures for one person's tax return: wealth statement, income summary, tax deducted
    at source and rebate-eligible investments (FR13.6). analysisACE never files returns."""
    member = households.get_member(db, access.household.id, body.member_id)
    snapshot, sources = zakat_tax.create_tax_snapshot(
        db,
        access.household.id,
        member,
        body.tax_year,
        salary_income=body.salary_income,
        other_income=body.other_income,
    )
    db.commit()
    return computed(db, TaxSnapshotOut.model_validate(snapshot), sources)


@router.get(f"{HOUSEHOLD}/tax/snapshots")
def list_tax_snapshots(access: Viewer, db: Db) -> list[TaxSnapshotOut]:
    rows = zakat_tax.list_tax_snapshots(db, access.household.id)
    return [TaxSnapshotOut.model_validate(r) for r in rows]


@router.get(f"{HOUSEHOLD}/tax/snapshots/{{snapshot_id}}")
def get_tax_snapshot(snapshot_id: uuid.UUID, access: Viewer, db: Db) -> TaxSnapshotOut:
    row = zakat_tax.get_tax_snapshot(db, access.household.id, snapshot_id)
    return TaxSnapshotOut.model_validate(row)


@router.get(f"{HOUSEHOLD}/tax/snapshots/{{snapshot_id}}/export.csv")
def export_tax_snapshot(snapshot_id: uuid.UUID, access: Viewer, db: Db) -> Response:
    row = zakat_tax.get_tax_snapshot(db, access.household.id, snapshot_id)
    return Response(
        zakat_tax.tax_snapshot_csv(row),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="analysisace-tax-{row.tax_year}.csv"'
        },
    )


@router.delete(f"{HOUSEHOLD}/tax/snapshots/{{snapshot_id}}", status_code=204)
def delete_tax_snapshot(snapshot_id: uuid.UUID, access: Editor, db: Db) -> Response:
    db.delete(zakat_tax.get_tax_snapshot(db, access.household.id, snapshot_id))
    db.commit()
    return no_content()


# --- F17 FIRE -------------------------------------------------------------------------


@router.get(f"{HOUSEHOLD}/fire/defaults")
def fire_defaults(
    access: Viewer, db: Db, member_id: uuid.UUID | None = None, include_illiquid: bool = False
) -> Envelope[dict[str, Any]]:
    """Starting values for the FIRE form, taken from the household's records (FR17.1):
    investable net worth, the last 12 months of costs, average CPI inflation, and the rate
    of its own sukuk and deposits. Every one can be changed before the plan is run."""
    member = (
        households.get_member(db, access.household.id, member_id) if member_id else access.member
    )
    data, sources = planning.defaults(
        db, access.household.id, member, include_illiquid=include_illiquid
    )
    return computed(db, data, sources)


@router.post(f"{HOUSEHOLD}/fire/plan", status_code=status.HTTP_201_CREATED)
def create_fire_plan(body: FirePlanIn, access: Editor, db: Db) -> FirePlanOut:
    """Project the inputs month by month in today's taka (FR17.2, FR17.3). A projection of
    the person's own assumptions, not a forecast."""
    plan = planning.create_plan(
        db,
        access.household.id,
        name=body.name,
        member_id=body.member_id,
        include_illiquid=body.include_illiquid,
        inputs=FireInputs(
            net_worth=body.net_worth,
            monthly_savings=body.monthly_savings,
            yearly_expenses=body.yearly_expenses,
            nominal_return_pct=body.nominal_return_pct,
            inflation_pct=body.inflation_pct,
            withdrawal_rate_pct=body.withdrawal_rate_pct,
            current_age=Decimal(body.current_age),
        ),
    )
    db.commit()
    return FirePlanOut.model_validate(plan)


@router.get(f"{HOUSEHOLD}/fire/plans")
def list_fire_plans(access: Viewer, db: Db) -> list[FirePlanOut]:
    return [FirePlanOut.model_validate(p) for p in planning.list_plans(db, access.household.id)]


@router.get(f"{HOUSEHOLD}/fire/plans/{{plan_id}}")
def get_fire_plan(plan_id: uuid.UUID, access: Viewer, db: Db) -> FirePlanDetailOut:
    plan = planning.get_plan(db, access.household.id, plan_id)
    return FirePlanDetailOut(
        plan=FirePlanOut.model_validate(plan),
        scenarios=[ScenarioOut.model_validate(s) for s in planning.list_scenarios(db, plan.id)],
    )


@router.delete(f"{HOUSEHOLD}/fire/plans/{{plan_id}}", status_code=204)
def delete_fire_plan(plan_id: uuid.UUID, access: Editor, db: Db) -> Response:
    db.delete(planning.get_plan(db, access.household.id, plan_id))
    db.commit()
    return no_content()


# --- F18 scenarios --------------------------------------------------------------------


@router.post(f"{HOUSEHOLD}/fire/scenarios", status_code=status.HTTP_201_CREATED)
def run_scenario(body: ScenarioIn, access: Editor, db: Db) -> Envelope[ScenarioOut]:
    """Apply a what-if to a plan and compare with the base case (FR18): a market fall in
    year 1, the replay of a past event, higher costs, stopping work earlier, or higher
    inflation."""
    plan = planning.get_plan(db, access.household.id, body.plan_id)
    row, sources = planning.run_scenario(db, plan, body.preset, body.params)
    db.commit()
    return computed(db, ScenarioOut.model_validate(row), sources)


@router.delete(f"{HOUSEHOLD}/fire/plans/{{plan_id}}/scenarios/{{scenario_id}}", status_code=204)
def delete_scenario(plan_id: uuid.UUID, scenario_id: uuid.UUID, access: Editor, db: Db) -> Response:
    plan = planning.get_plan(db, access.household.id, plan_id)
    planning.delete_scenario(db, plan, scenario_id)
    db.commit()
    return no_content()


@router.get("/events")
def list_events(db: Db) -> list[EventOut]:
    """Published events in the library (FR5.1), newest first. Used to pick an event to
    replay in a scenario (FR18.1)."""
    rows = db.scalars(select(Event).where(Event.published.is_(True)).order_by(Event.t0.desc()))
    return [EventOut.model_validate(r) for r in rows]


# --- F19 goals ------------------------------------------------------------------------


@router.get(f"{HOUSEHOLD}/goals")
def list_goals(access: Viewer, db: Db) -> Envelope[list[GoalProgressOut]]:
    """Each goal with the household's progress towards it (FR19.1)."""
    portfolio = load_portfolio(db, access.household.id)
    rows = planning.goal_progress(db, access.household.id, portfolio)
    data = [GoalProgressOut(**{**row, "goal": GoalOut.model_validate(row["goal"])}) for row in rows]
    return computed(db, data, portfolio.source_ids)


@router.post(f"{HOUSEHOLD}/goals", status_code=status.HTTP_201_CREATED)
def create_goal(body: GoalIn, access: Editor, db: Db) -> GoalOut:
    fields = body.model_dump()
    fields["type"] = body.type.value
    goal = planning.create_goal(db, access.household.id, fields)
    db.commit()
    return GoalOut.model_validate(goal)


@router.patch(f"{HOUSEHOLD}/goals/{{goal_id}}")
def update_goal(goal_id: uuid.UUID, body: GoalUpdateIn, access: Editor, db: Db) -> GoalOut:
    goal = households.owned(db, Goal, goal_id, access.household.id)
    planning.update_goal(db, goal, body.model_dump(exclude_unset=True))
    db.commit()
    return GoalOut.model_validate(goal)


@router.delete(f"{HOUSEHOLD}/goals/{{goal_id}}", status_code=204)
def delete_goal(goal_id: uuid.UUID, access: Editor, db: Db) -> Response:
    db.delete(households.owned(db, Goal, goal_id, access.household.id))
    db.commit()
    return no_content()
