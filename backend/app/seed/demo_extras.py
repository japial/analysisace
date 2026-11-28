"""The rest of the demo: results a household gets by using the app, plus an admin.

`seed_demo_personal` creates the records a household keeps. This module runs the app's own
services on those records, the same way pressing the buttons would:

- FIRE plans (F17) and a what-if for every preset (F18)
- Zakat for both members (F13) and a tax statement (F13, FR27.5)
- notices from the alert run, the monthly report and the shock playbook (F7, F20)
- 55 fictional peers who opted in, so "Compare with peers" has a group to show (F21)
- an admin sign-in for the admin screens

Everything is fictional (docs/DECISIONS.md, D15). It runs once: a second call does nothing.
"""

import random
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.fire import FireInputs
from app.core.permissions import Role
from app.core.security import utcnow
from app.models import Event, FirePlan, Household, HouseholdMember, Notification, User
from app.models.enums import AlertFrequency, AlertType, Channel
from app.seed.demo_market import END
from app.seed.demo_personal import DEMO_EMAIL, _user
from app.services import alerts, market_alerts, planning, zakat_tax
from app.services.auth import ConsentPurpose, get_user_by_email
from app.services.email import EmailSender

ADMIN_EMAIL = "admin@example.com"
PEER_COUNT = 55  # above the 50 that `community.min_group_size` asks for
PEER_EMAIL = "peer{n:02d}@example.com"

# Alert types the base seed leaves off, turned on so every row in Alert settings is in use.
EXTRA_ALERT_RULES = (
    ("VOLATILITY", "APP", "INSTANT"),
    ("GOAL_REACHED", "BOTH", "INSTANT"),
    ("REVALUATION_DUE", "EMAIL", "DAILY_DIGEST"),
    ("MONTHLY_REPORT", "EMAIL", "INSTANT"),
    ("REGIME_CHANGE", "APP", "INSTANT"),
)


@dataclass
class DemoExtrasResult:
    created: bool
    counts: dict[str, int] = field(default_factory=dict)


def _grant(user: User, *purposes: ConsentPurpose) -> None:
    at = utcnow().isoformat()
    # A new dict, so the JSON column sees the change.
    user.consents = {
        **user.consents,
        **{purpose.value: {"granted": True, "at": at} for purpose in purposes},
    }


def _fire_inputs(values: dict[str, object], age: int) -> FireInputs:
    def dec(key: str, fallback: str) -> Decimal:
        value = values.get(key)
        return Decimal(str(value)) if value is not None else Decimal(fallback)

    return FireInputs(
        net_worth=dec("net_worth", "0"),
        monthly_savings=dec("monthly_savings", "40000"),
        yearly_expenses=dec("yearly_expenses", "900000"),
        nominal_return_pct=dec("nominal_return_pct", "9"),
        inflation_pct=dec("inflation_pct", "8"),
        withdrawal_rate_pct=dec("withdrawal_rate_pct", "4"),
        current_age=Decimal(age),
    )


def seed_demo_extras(session: Session, sender: EmailSender, password: str) -> DemoExtrasResult:
    """Run after `seed_demo_personal` and the market analytics. Does nothing the second time."""
    karim = get_user_by_email(session, DEMO_EMAIL)
    if karim is None:
        return DemoExtrasResult(created=False)
    member = session.scalar(select(HouseholdMember).where(HouseholdMember.user_id == karim.id))
    assert member is not None
    hid = member.household_id
    if session.scalar(select(FirePlan.id).where(FirePlan.household_id == hid)) is not None:
        return DemoExtrasResult(created=False)

    counts: dict[str, int] = {}
    _grant(karim, ConsentPurpose.COMMUNITY_BENCHMARKING, ConsentPurpose.MARKETING)
    age = END.year - (member.birth_year or 1988)

    # --- FIRE plans (F17) and what-ifs (F18) ----------------------------------------
    values, _ = planning.defaults(session, hid, member, include_illiquid=False)
    plan = planning.create_plan(
        session, hid, name="My plan", inputs=_fire_inputs(values, age), member_id=member.id
    )
    with_home, _ = planning.defaults(session, hid, member, include_illiquid=True)
    planning.create_plan(
        session,
        hid,
        name="If we sell the land too",
        inputs=_fire_inputs(with_home, age),
        member_id=member.id,
        include_illiquid=True,
    )
    counts["fire_plans"] = 2
    presets: list[tuple[str, dict[str, object]]] = [
        ("MARKET_CRASH", {"fall_pct": "30"}),
        ("EXPENSES_UP", {"pct": "20"}),
        ("INFLATION_SHOCK", {"points": "3"}),
    ]
    if plan.fire_age is not None:
        presets.append(("RETIRE_EARLIER", {"years": "3"}))
    event = session.scalar(
        select(Event).where(Event.published.is_(True)).order_by(Event.t0.desc()).limit(1)
    )
    if event is not None:
        presets.append(("EVENT_REPLAY", {"event_id": str(event.id)}))
    for preset, params in presets:
        planning.run_scenario(session, plan, preset, params)
    counts["what_ifs"] = len(presets)

    # --- Zakat for each member, and a tax statement (F13) ---------------------------
    members = session.scalars(
        select(HouseholdMember).where(HouseholdMember.household_id == hid)
    ).all()
    for person in members:
        zakat_tax.create_zakat_snapshot(session, karim, hid, person, day=END)
    counts["zakat_snapshots"] = len(members)
    zakat_tax.create_tax_snapshot(session, hid, member, zakat_tax.current_tax_year(END))
    counts["tax_snapshots"] = 1

    # --- notices (F7, F20) ------------------------------------------------------------
    for kind, channel, frequency in EXTRA_ALERT_RULES:
        alerts.set_rule(
            session,
            karim,
            type=AlertType(kind),
            channel=Channel(channel),
            frequency=AlertFrequency(frequency),
            is_active=True,
        )
    session.flush()
    alerts.run_household_alerts(session, sender, hid, END)
    alerts.send_monthly_reports(session, sender, "http://localhost:3000", END)
    if event is not None:
        market_alerts.event_published(session, sender, event)
    session.flush()
    counts["notices"] = len(
        session.scalars(select(Notification.id).where(Notification.user_id == karim.id)).all()
    )

    # --- an admin for the admin screens ---------------------------------------------
    if get_user_by_email(session, ADMIN_EMAIL) is None:
        _user(session, ADMIN_EMAIL, "Demo Admin", password, Role.ADMIN, "en")
        counts["admins"] = 1

    # --- peers for "Compare with peers" (F21) -----------------------------------------
    rng = random.Random(20261128)
    for n in range(1, PEER_COUNT + 1):
        peer = _user(
            session, PEER_EMAIL.format(n=n), f"Demo peer {n:02d}", password, Role.USER, "en"
        )
        _grant(peer, ConsentPurpose.COMMUNITY_BENCHMARKING)
        session.flush()
        household = Household(name=f"Demo peer household {n:02d}", created_by=peer.id)
        session.add(household)
        session.flush()
        peer_age = rng.randint(30, 39)
        peer_member = HouseholdMember(
            household_id=household.id,
            user_id=peer.id,
            display_name=f"Demo peer {n:02d}",
            role="OWNER",
            birth_year=END.year - peer_age,
        )
        session.add(peer_member)
        session.flush()
        expenses = Decimal(rng.randrange(450_000, 1_500_000, 10_000))
        savings = (expenses / 12 * Decimal(rng.uniform(0.15, 0.9))).quantize(Decimal(1000))
        planning.create_plan(
            session,
            household.id,
            name="My plan",
            member_id=peer_member.id,
            inputs=FireInputs(
                net_worth=Decimal(rng.randrange(300_000, 9_000_000, 50_000)),
                monthly_savings=savings,
                yearly_expenses=expenses,
                nominal_return_pct=Decimal("9"),
                inflation_pct=Decimal("8"),
                withdrawal_rate_pct=Decimal("4"),
                current_age=Decimal(peer_age),
            ),
        )
    counts["peers"] = PEER_COUNT
    session.flush()
    return DemoExtrasResult(created=True, counts=counts)


__all__ = ["ADMIN_EMAIL", "DemoExtrasResult", "seed_demo_extras"]
