"""FIRE plans (F17), what-if scenarios (F18) and goals (F19).

A plan projects the person's own inputs. The starting values offered by `defaults` come
from what the household has recorded; none of them is a forecast or a recommendation.
"""

import uuid
from dataclasses import replace
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics import fire
from app.analytics.returns import max_drawdown
from app.core.security import utcnow
from app.models import (
    Event,
    FirePlan,
    Goal,
    HouseholdMember,
    IndexDaily,
    MacroSeries,
    ScenarioResult,
)
from app.services import costs as cost_service
from app.services import islamic
from app.services.auth import AuthError
from app.services.households import member_age, owned
from app.services.valuation import Portfolio, load_portfolio, personal_config

Q2 = Decimal("0.01")
HUNDRED = Decimal(100)


def _fire_config() -> dict[str, Any]:
    config = personal_config()["fire"]
    assert isinstance(config, dict)
    return config


def investable_base(portfolio: Portfolio, include_illiquid: bool) -> tuple[Decimal, Decimal]:
    """(investable net worth, illiquid amount left out).

    Illiquid alternative assets, such as land and the family home, stay out of the base by
    default because they cannot be drawn on to live from (FR17.4).
    """
    illiquid = set(_fire_config()["illiquid"])
    excluded = sum(
        (p.household_value for p in portfolio.positions if p.alt and p.liquidity in illiquid),
        Decimal(0),
    )
    base = portfolio.net_worth if include_illiquid else portfolio.net_worth - excluded
    return base.quantize(Q2), excluded.quantize(Q2)


def market_share_pct(portfolio: Portfolio, include_illiquid: bool) -> Decimal:
    """Share of the investable assets that moves with the stock market (the equity class)."""
    illiquid = set(_fire_config()["illiquid"])
    counted = [
        p
        for p in portfolio.positions
        if include_illiquid or not (p.alt and p.liquidity in illiquid)
    ]
    total = sum((p.household_value for p in counted), Decimal(0))
    equity = sum((p.household_value for p in counted if p.asset_class == "EQUITY"), Decimal(0))
    return (equity / total * 100).quantize(Q2) if total > 0 else Decimal(0)


def defaults(
    db: Session, household_id: uuid.UUID, member: HouseholdMember | None, *, include_illiquid: bool
) -> tuple[dict[str, Any], set[uuid.UUID]]:
    """Starting values for the FIRE form, each from the household's own records (FR17.1)."""
    config = _fire_config()
    portfolio = load_portfolio(db, household_id)
    sources = set(portfolio.source_ids)
    base, excluded = investable_base(portfolio, include_illiquid)
    rows = list(
        db.scalars(
            select(MacroSeries)
            .where(
                MacroSeries.series_code == config["inflation_series"],
                MacroSeries.date <= portfolio.day,
            )
            .order_by(MacroSeries.date.desc())
            .limit(int(config["inflation_lookback_months"]))
        )
    )
    inflation = (
        (sum((r.value for r in rows), Decimal(0)) / len(rows)).quantize(Q2) if rows else None
    )
    sources |= {r.source_id for r in rows[:1]}
    safe_rate, safe_basis = islamic.safe_return_pct(db, household_id)
    data = {
        "net_worth": base,
        "total_net_worth": portfolio.net_worth.quantize(Q2),
        "illiquid_excluded": Decimal(0) if include_illiquid else excluded,
        "include_illiquid": include_illiquid,
        "yearly_expenses": cost_service.trailing_cost_of_living(db, household_id, portfolio.day),
        "inflation_pct": inflation,
        "inflation_months": len(rows),
        "nominal_return_pct": safe_rate,
        "nominal_return_basis": safe_basis,
        "withdrawal_rate_pct": Decimal(str(config["withdrawal_rate_pct"])),
        "current_age": member_age(member, portfolio.day) if member else None,
        "market_share_pct": market_share_pct(portfolio, include_illiquid),
        "max_age": int(config["max_age"]),
    }
    return data, sources


# --- plans (F17) ----------------------------------------------------------------------


def _inputs(values: dict[str, Any]) -> fire.FireInputs:
    return fire.FireInputs(
        net_worth=Decimal(values["net_worth"]),
        monthly_savings=Decimal(values["monthly_savings"]),
        yearly_expenses=Decimal(values["yearly_expenses"]),
        nominal_return_pct=Decimal(values["nominal_return_pct"]),
        inflation_pct=Decimal(values["inflation_pct"]),
        withdrawal_rate_pct=Decimal(values["withdrawal_rate_pct"]),
        current_age=Decimal(values["current_age"]),
        max_age=int(_fire_config()["max_age"]),
    )


def create_plan(
    db: Session,
    household_id: uuid.UUID,
    *,
    name: str,
    inputs: fire.FireInputs,
    member_id: uuid.UUID | None = None,
    include_illiquid: bool = False,
) -> FirePlan:
    """Run the projection and store it with its inputs (FR17.2, FR17.3)."""
    if member_id is not None:
        owned(db, HouseholdMember, member_id, household_id)
    inputs = replace(inputs, max_age=int(_fire_config()["max_age"]))
    if inputs.current_age >= inputs.max_age:
        raise AuthError("VALIDATION", 422)
    portfolio = load_portfolio(db, household_id)
    result = fire.project(inputs)
    plan = FirePlan(
        household_id=household_id,
        member_id=member_id,
        name=name.strip(),
        inputs={
            **inputs.as_dict(),
            "include_illiquid": include_illiquid,
            "market_share_pct": str(market_share_pct(portfolio, include_illiquid)),
            "real_return_pct": str(result.real_return_pct),
        },
        fire_number=result.fire_number,
        fire_age=result.fire_age,
        projection=[point.as_dict() for point in result.path],
        computed_at=utcnow(),
    )
    db.add(plan)
    db.flush()
    return plan


def list_plans(db: Session, household_id: uuid.UUID) -> list[FirePlan]:
    return list(
        db.scalars(
            select(FirePlan)
            .where(FirePlan.household_id == household_id)
            .order_by(FirePlan.computed_at.desc())
        )
    )


def get_plan(db: Session, household_id: uuid.UUID, plan_id: uuid.UUID) -> FirePlan:
    return owned(db, FirePlan, plan_id, household_id)


# --- scenarios (F18) ------------------------------------------------------------------


def event_fall_pct(db: Session, event_id: uuid.UUID) -> tuple[Decimal, Event, set[uuid.UUID]]:
    """How far the index fell after a past event: the largest drop from the last close
    before the event within the configured number of sessions (FR5.2, FR18.1)."""
    config = personal_config()["scenarios"]
    assert isinstance(config, dict)
    event = db.get(Event, event_id)
    if event is None or not event.published:
        raise AuthError("EVENT_NOT_FOUND", 404)
    code = str(config["replay_index"])
    before = db.execute(
        select(IndexDaily.close, IndexDaily.source_id)
        .where(IndexDaily.index_code == code, IndexDaily.date < event.t0)
        .order_by(IndexDaily.date.desc())
        .limit(1)
    ).first()
    after = db.execute(
        select(IndexDaily.close, IndexDaily.source_id)
        .where(IndexDaily.index_code == code, IndexDaily.date >= event.t0)
        .order_by(IndexDaily.date)
        .limit(int(config["replay_sessions"]))
    ).all()
    if before is None or not after:
        raise AuthError("EVENT_DATA_MISSING", 409)
    fall = -max_drawdown([float(before.close), *(float(row.close) for row in after)])
    return Decimal(str(fall * 100)).quantize(Q2), event, {before.source_id}


def run_scenario(
    db: Session, plan: FirePlan, preset: str, params: dict[str, Any]
) -> tuple[ScenarioResult, set[uuid.UUID]]:
    """Apply one preset to a plan and store the result beside the base case (FR18.2)."""
    config = personal_config()["scenarios"]
    assert isinstance(config, dict)
    if preset not in fire.PRESETS:
        raise AuthError("VALIDATION", 422)
    inputs = _inputs(plan.inputs)
    base = fire.project(inputs)
    share = Decimal(plan.inputs.get("market_share_pct", "100"))
    sources: set[uuid.UUID] = set()
    used: dict[str, Any]
    values: dict[str, Decimal]

    def number(name: str, default_key: str, low: str, high: str) -> Decimal:
        value = Decimal(str(params.get(name, config[default_key])))
        if not Decimal(low) <= value <= Decimal(high):
            raise AuthError("VALIDATION", 422)
        return value

    if preset == "MARKET_CRASH":
        fall = number("fall_pct", "crash_pct", "0", "100")
        values = {"fall_pct": fall, "market_share_pct": share}
        used = {"fall_pct": str(fall), "market_share_pct": str(share)}
    elif preset == "EVENT_REPLAY":
        try:
            event_id = uuid.UUID(str(params.get("event_id")))
        except ValueError as exc:
            raise AuthError("VALIDATION", 422) from exc
        fall, event, sources = event_fall_pct(db, event_id)
        values = {"fall_pct": fall, "market_share_pct": share}
        used = {
            "event_id": str(event.id),
            "event_title_en": event.title_en,
            "event_title_bn": event.title_bn,
            "fall_pct": str(fall),
            "market_share_pct": str(share),
        }
    elif preset == "EXPENSES_UP":
        pct = number("pct", "expenses_up_pct", "0", "500")
        values, used = {"pct": pct}, {"pct": str(pct)}
    elif preset == "INFLATION_SHOCK":
        points = number("points", "inflation_shock_pts", "0", "50")
        values, used = {"points": points}, {"points": str(points)}
    else:  # RETIRE_EARLIER
        years = number("years", "retire_earlier_years", "0", "60")
        if base.fire_age is None:
            raise AuthError("PLAN_NEVER_REACHES_FIRE", 409)
        values, used = {"years": years}, {"years": str(years)}

    result = fire.run_scenario(inputs, preset, values, base)
    change = (
        result.fire_age - base.fire_age
        if result.fire_age is not None and base.fire_age is not None
        else None
    )
    row = ScenarioResult(
        fire_plan_id=plan.id,
        preset=preset,
        params=used,
        result={
            "fire_number": str(result.fire_number),
            "fire_age": str(result.fire_age) if result.fire_age is not None else None,
            "base_fire_age": str(base.fire_age) if base.fire_age is not None else None,
            "fire_age_change": str(change) if change is not None else None,
            "worst_year_net_worth": str(result.worst_year_net_worth),
            "base_worst_year_net_worth": str(base.worst_year_net_worth),
            "depleted_age": str(result.depleted_age) if result.depleted_age is not None else None,
            "projection": [point.as_dict() for point in result.path],
        },
        computed_at=utcnow(),
    )
    db.add(row)
    db.flush()
    return row, sources


def list_scenarios(db: Session, plan_id: uuid.UUID) -> list[ScenarioResult]:
    return list(
        db.scalars(
            select(ScenarioResult)
            .where(ScenarioResult.fire_plan_id == plan_id)
            .order_by(ScenarioResult.computed_at.desc())
        )
    )


def delete_scenario(db: Session, plan: FirePlan, scenario_id: uuid.UUID) -> None:
    row = db.get(ScenarioResult, scenario_id)
    if row is None or row.fire_plan_id != plan.id:
        raise AuthError("NOT_FOUND", 404)
    db.delete(row)
    db.flush()


# --- goals (F19) ----------------------------------------------------------------------


def list_goals(db: Session, household_id: uuid.UUID) -> list[Goal]:
    return list(
        db.scalars(select(Goal).where(Goal.household_id == household_id).order_by(Goal.created_at))
    )


def create_goal(db: Session, household_id: uuid.UUID, fields: dict[str, Any]) -> Goal:
    kind = fields["type"]
    if kind == "FIRE_AGE":
        if not fields.get("target_age"):
            raise AuthError("VALIDATION", 422)
    elif not fields.get("target_amount"):
        raise AuthError("VALIDATION", 422)
    if fields.get("member_id") is not None:
        owned(db, HouseholdMember, fields["member_id"], household_id)
    goal = Goal(household_id=household_id, **fields)
    db.add(goal)
    db.flush()
    return goal


def update_goal(db: Session, goal: Goal, changes: dict[str, Any]) -> Goal:
    for name, value in changes.items():
        if value is not None or name in ("target_date", "member_id"):
            setattr(goal, name, value)
    # A changed target is measured afresh.
    if {"target_amount", "target_age"} & set(changes):
        goal.achieved_at = None
    db.flush()
    return goal


def goal_progress(
    db: Session, household_id: uuid.UUID, portfolio: Portfolio | None = None
) -> list[dict[str, Any]]:
    """Each goal with where the household stands against it (FR19.1)."""
    portfolio = portfolio or load_portfolio(db, household_id)
    invested_types = set(personal_config()["portfolio"]["invested_types"])  # type: ignore[index]
    invested = sum(
        (p.household_value for p in portfolio.positions if p.type in invested_types), Decimal(0)
    )
    plans = list_plans(db, household_id)
    today = portfolio.day
    rows = []
    for goal in list_goals(db, household_id):
        current: Decimal | None
        target: Decimal | None
        reached = False
        if goal.type == "FIRE_AGE":
            plan = next((p for p in plans if p.member_id == goal.member_id), None) or (
                plans[0] if plans else None
            )
            target = Decimal(goal.target_age or 0)
            current = plan.fire_age if plan else None
            base = Decimal(plan.inputs["net_worth"]) if plan else None
            pct = (
                min(base / plan.fire_number * 100, HUNDRED).quantize(Q2)
                if plan and base is not None and plan.fire_number > 0
                else None
            )
            reached = bool(plan and base is not None and base >= plan.fire_number)
        else:
            current = portfolio.net_worth if goal.type == "NET_WORTH" else invested
            target = goal.target_amount
            pct = (
                max(min(current / target * 100, HUNDRED), Decimal(0)).quantize(Q2)
                if target
                else None
            )
            reached = bool(target and current >= target)
        rows.append(
            {
                "goal": goal,
                "current": current.quantize(Q2) if current is not None else None,
                "target": target,
                "progress_pct": pct,
                "reached": reached or goal.achieved_at is not None,
                # For a FIRE-age goal: is the projected age at or before the age wanted.
                "on_track": (current is not None and target is not None and current <= target)
                if goal.type == "FIRE_AGE"
                else None,
                "days_left": (goal.target_date - today).days if goal.target_date else None,
            }
        )
    return rows


def check_goals(db: Session, household_id: uuid.UUID) -> list[Goal]:
    """Mark goals that have just been reached and return them, so the household can be
    told (FR19.1). Run by the daily alerts job."""
    newly: list[Goal] = []
    for row in goal_progress(db, household_id):
        goal: Goal = row["goal"]
        if goal.is_active and goal.achieved_at is None and row["reached"]:
            goal.achieved_at = utcnow()
            newly.append(goal)
    db.flush()
    return newly


def fire_progress(db: Session, household_id: uuid.UUID) -> dict[str, Any] | None:
    """The newest plan against today's investable base, for the dashboard and the report."""
    plans = list_plans(db, household_id)
    if not plans:
        return None
    plan = plans[0]
    portfolio = load_portfolio(db, household_id)
    base, _ = investable_base(portfolio, bool(plan.inputs.get("include_illiquid")))
    pct = (base / plan.fire_number * 100).quantize(Q2) if plan.fire_number > 0 else Decimal(0)
    return {
        "plan_id": plan.id,
        "name": plan.name,
        "fire_number": plan.fire_number,
        "fire_age": plan.fire_age,
        "net_worth": base,
        "progress_pct": max(min(pct, HUNDRED), Decimal(0)),
        "computed_at": plan.computed_at,
    }
