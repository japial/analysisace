"""Personal alerts and the monthly report (F20), and community benchmarks (F21).

The worker runs `run_personal_alerts` once a day and `send_monthly_reports` once a month.
Every alert becomes a `notification` row, shown in the app in the reader's language; it is
also emailed when the person's rule for that alert type says so. Alerts describe what has
happened ("drift from your target"). They never say what to do about it.

Web push is not sent yet: it needs VAPID keys and a service worker. A rule set to PUSH
therefore shows in the app only.
"""

import datetime as dt
import statistics
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.costs import add_months, month_start
from app.core.config import get_settings
from app.core.security import utcnow
from app.models import (
    AlertRule,
    Expense,
    FirePlan,
    Household,
    HouseholdMember,
    IncomeEntry,
    Notification,
    User,
)
from app.models.enums import AlertFrequency, AlertType, Channel
from app.services import alt_assets, islamic, performance, planning, push, zakat_tax
from app.services.alert_texts import DISCLAIMER, EMAIL_TEXT, REPORT_TEXT
from app.services.auth import AuthError, ConsentPurpose
from app.services.email import Email, EmailSender, send_safely
from app.services.households import has_consent, list_households
from app.services.valuation import load_portfolio, personal_config, today_dhaka

Q2 = Decimal("0.01")
_BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


def taka(amount: Decimal, locale: str) -> str:
    """ "Tk 12,34,567.50" with lakh and crore grouping; Bangla digits for Bangla."""
    whole, _, cents = f"{abs(amount):.2f}".partition(".")
    head, tail = whole[:-3], whole[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    text = f"{'-' if amount < 0 else ''}{','.join([*groups, tail])}.{cents}"
    return f"৳{text.translate(_BN_DIGITS)}" if locale == "bn" else f"Tk {text}"


# --- rules (FR20.1, FR7.3) ------------------------------------------------------------


def list_rules(db: Session, user: User) -> list[AlertRule]:
    return list(
        db.scalars(select(AlertRule).where(AlertRule.user_id == user.id).order_by(AlertRule.type))
    )


def set_rule(
    db: Session,
    user: User,
    *,
    type: AlertType,
    channel: Channel,
    frequency: AlertFrequency,
    is_active: bool,
    params: dict[str, Any] | None = None,
) -> AlertRule:
    rule = db.scalar(
        select(AlertRule).where(AlertRule.user_id == user.id, AlertRule.type == type.value)
    )
    if rule is None:
        rule = AlertRule(user_id=user.id, type=type.value)
        db.add(rule)
    cleaned: dict[str, Any] = {}
    if type is AlertType.VOLATILITY and params and params.get("max_volatility_pct") is not None:
        try:
            limit = Decimal(str(params["max_volatility_pct"]))
        except ArithmeticError as exc:
            raise AuthError("VALIDATION", 422) from exc
        if not Decimal(0) < limit <= Decimal(500):
            raise AuthError("VALIDATION", 422)
        cleaned["max_volatility_pct"] = str(limit)
    rule.channel, rule.frequency = channel.value, frequency.value
    rule.is_active, rule.params = is_active, cleaned
    db.flush()
    return rule


# --- notifications --------------------------------------------------------------------


def list_notifications(
    db: Session, user: User, *, unread_only: bool = False, limit: int = 50
) -> tuple[list[Notification], int]:
    filters = [Notification.user_id == user.id]
    unread = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
    )
    if unread_only:
        filters.append(Notification.read_at.is_(None))
    rows = db.scalars(
        select(Notification).where(*filters).order_by(Notification.created_at.desc()).limit(limit)
    )
    return list(rows), unread or 0


def mark_read(db: Session, user: User, notification_id: uuid.UUID | None = None) -> int:
    """Mark one notification, or all of the user's, as read."""
    statement = select(Notification).where(
        Notification.user_id == user.id, Notification.read_at.is_(None)
    )
    if notification_id is not None:
        statement = statement.where(Notification.id == notification_id)
    rows = list(db.scalars(statement))
    if notification_id is not None and not rows and db.get(Notification, notification_id) is None:
        raise AuthError("NOT_FOUND", 404)
    for row in rows:
        row.read_at = utcnow()
    db.flush()
    return len(rows)


def _rules(db: Session, user_id: uuid.UUID) -> dict[str, AlertRule]:
    return {r.type: r for r in db.scalars(select(AlertRule).where(AlertRule.user_id == user_id))}


def notify(
    db: Session,
    sender: EmailSender,
    user: User,
    *,
    type: str,
    message_key: str,
    data: dict[str, Any],
    link: str,
    dedupe_key: str,
    rules: dict[str, AlertRule] | None = None,
) -> Notification | None:
    """Create one notification unless it was already raised or the person turned it off."""
    rules = rules if rules is not None else _rules(db, user.id)
    rule = rules.get(type)
    if rule is not None and not rule.is_active:
        return None
    exists = db.scalar(
        select(Notification.id).where(
            Notification.user_id == user.id, Notification.dedupe_key == dedupe_key
        )
    )
    if exists is not None:
        return None
    row = Notification(
        user_id=user.id,
        type=type,
        message_key=message_key,
        data=data,
        link=link,
        dedupe_key=dedupe_key,
    )
    db.add(row)
    template = EMAIL_TEXT.get(message_key)
    # D25: email only a confirmed address; the notice is in the app either way.
    if (
        rule is not None
        and rule.channel in ("EMAIL", "BOTH")
        and template is not None
        and user.email_verified_at is not None
    ):
        locale = user.locale if user.locale in ("bn", "en") else "en"
        subject, body = template[locale]
        # The notice stays in the app either way; sent_at records that the email went.
        if send_safely(
            sender,
            Email(
                to=user.email,
                subject=subject,
                body=f"{body.format(**data)}\n\n{DISCLAIMER[locale]}",
            ),
        ):
            row.sent_at = utcnow()
    # D26: a push copy to the person's browsers when the rule asks for one.
    if rule is not None and rule.channel in ("PUSH", "BOTH") and template is not None:
        locale = user.locale if user.locale in ("bn", "en") else "en"
        title, body = template[locale]
        push.push_to_user(
            db,
            push.get_push_sender(),
            user.id,
            push.notice_message(
                title, body.format(**data), link, get_settings().web_base_url, locale
            ),
        )
    db.flush()
    return row


def _household_users(db: Session, household_id: uuid.UUID) -> list[tuple[User, HouseholdMember]]:
    rows = db.execute(
        select(User, HouseholdMember)
        .join(HouseholdMember, HouseholdMember.user_id == User.id)
        .where(HouseholdMember.household_id == household_id, User.is_active.is_(True))
    ).all()
    return [(user, member) for user, member in rows]


def run_household_alerts(
    db: Session, sender: EmailSender, household_id: uuid.UUID, today: dt.date
) -> int:
    """Raise today's alerts for one household (FR20.1). Returns how many were created."""
    config = personal_config()["alerts"]
    assert isinstance(config, dict)
    people = _household_users(db, household_id)
    if not people:
        return 0
    portfolio = load_portfolio(db, household_id, today)
    drift = [row for row in performance.drift_rows(db, portfolio, household_id) if row.outside_band]
    volatility = performance.volatility_pct(db, portfolio)
    reached = planning.check_goals(db, household_id)
    horizon = today + dt.timedelta(days=int(config["maturity_reminder_days"]))
    maturing = [
        p.holding
        for p in portfolio.positions
        if p.holding and p.holding.maturity_date and today <= p.holding.maturity_date <= horizon
    ]
    views, _ = alt_assets.list_views(db, household_id)
    stale = [v for v in views if v.revaluation_due is not None and v.asset.is_active]
    auctions = islamic.upcoming_auctions(
        db, today, today + dt.timedelta(days=int(config["auction_notice_days"]))
    )
    members = portfolio.members
    hawl_until = today + dt.timedelta(days=int(config["hawl_reminder_days"]))
    created = 0

    for user, own_member in people:
        rules = _rules(db, user.id)

        def send(type_: str, key: str, data: dict[str, Any], link: str, dedupe: str) -> None:
            nonlocal created
            row = notify(
                db,
                sender,
                user,  # noqa: B023 - called only inside this iteration
                type=type_,
                message_key=key,
                data=data,
                link=link,
                dedupe_key=dedupe,
                rules=rules,  # noqa: B023
            )
            created += row is not None

        month = today.strftime("%Y-%m")
        for row in drift:
            send(
                "ALLOCATION_DRIFT",
                "ALLOCATION_DRIFT",
                {
                    "asset_class": row.asset_class,
                    "actual_pct": str(row.actual_pct),
                    "target_pct": str(row.target_pct.normalize()),
                    "band_pct": str(row.band_pct.normalize()),
                },
                "/personal/allocation",
                f"drift:{household_id}:{row.asset_class}:{month}",
            )
        rule = rules.get("VOLATILITY")
        limit = Decimal(
            str((rule.params or {}).get("max_volatility_pct") if rule else "")
            or config["default_max_volatility_pct"]
        )
        if volatility is not None and volatility > limit:
            send(
                "VOLATILITY",
                "VOLATILITY",
                {"volatility_pct": str(volatility), "limit_pct": str(limit.normalize())},
                "/personal/performance",
                f"volatility:{household_id}:{month}",
            )
        for goal in reached:
            send(
                "GOAL_REACHED",
                "GOAL_REACHED",
                {"name": goal.name},
                "/personal/goals",
                f"goal:{goal.id}",
            )
        for holding in maturing:
            assert holding is not None and holding.maturity_date is not None
            send(
                "MATURITY_DUE",
                "MATURITY_DUE",
                {
                    "name": holding.name,
                    "date": holding.maturity_date.isoformat(),
                    "days": (holding.maturity_date - today).days,
                },
                "/personal/sukuk",
                f"maturity:{holding.id}:{holding.maturity_date}",
            )
        for issue in auctions:
            assert issue.auction_date is not None
            send(
                "MATURITY_DUE",
                "SUKUK_AUCTION",
                {
                    "name": issue.name,
                    "date": issue.auction_date.isoformat(),
                    "days": (issue.auction_date - today).days,
                },
                "/personal/sukuk",
                f"auction:{issue.id}:{issue.auction_date}",
            )
        for view in stale:
            send(
                "REVALUATION_DUE",
                "REVALUATION_DUE",
                {"name": view.asset.name, "months": view.asset.revaluation_months},
                f"/personal/assets/{view.asset.id}",
                f"revaluation:{view.asset.id}:{view.revaluation_due}",
            )
        # FR23.2: a Zakat date is a religious preference, so it is only used for someone
        # who has given that consent. A member without a login is covered by the owners.
        if has_consent(user, ConsentPurpose.RELIGIOUS_PREFERENCES):
            for member in members:
                mine = member.id == own_member.id
                proxy = member.user_id is None and own_member.role == "OWNER"
                due = member.hawl_date
                if due is None or not (mine or proxy) or not today <= due <= hawl_until:
                    continue
                send(
                    "HAWL_APPROACHING",
                    "HAWL_APPROACHING",
                    {
                        "name": member.display_name,
                        "date": due.isoformat(),
                        "days": (due - today).days,
                    },
                    "/personal/zakat",
                    f"hawl:{member.id}:{due}",
                )
    db.flush()
    return created


def run_personal_alerts(db: Session, sender: EmailSender, today: dt.date | None = None) -> int:
    today = today or today_dhaka()
    return sum(
        run_household_alerts(db, sender, household_id, today)
        for household_id in list(db.scalars(select(Household.id)))
    )


# --- monthly report (FR20.2) ----------------------------------------------------------


def monthly_figures(
    db: Session, user: User, household_id: uuid.UUID, member: HouseholdMember, today: dt.date
) -> dict[str, Any]:
    """Last month's spending, income and savings, net worth now, a Zakat estimate and
    FIRE progress."""
    first = add_months(month_start(today), -1)
    last = month_start(today) - dt.timedelta(days=1)
    spending = db.scalar(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.household_id == household_id, Expense.date >= first, Expense.date <= last
        )
    )
    earned = db.scalar(
        select(func.coalesce(func.sum(IncomeEntry.amount), 0)).where(
            IncomeEntry.household_id == household_id,
            IncomeEntry.date >= first,
            IncomeEntry.date <= last,
        )
    )
    income = Decimal(earned or 0).quantize(Q2)
    spent = Decimal(spending or 0).quantize(Q2)
    portfolio = load_portfolio(db, household_id, today)
    zakat_due: Decimal | None = None
    if has_consent(user, ConsentPurpose.RELIGIOUS_PREFERENCES) and member.nisab_basis:
        try:
            result, _, _ = zakat_tax.compute_zakat(db, household_id, member, day=today)
            zakat_due = result.zakat_due
        except AuthError:
            zakat_due = None
    progress = planning.fire_progress(db, household_id)
    return {
        "month": first.strftime("%Y-%m"),
        "spending": spent,
        # FR27.3: None when nothing was recorded, so the report does not show a saving of 0.
        "income": income if income > 0 else None,
        "savings": income - spent if income > 0 else None,
        "net_worth": portfolio.net_worth.quantize(Q2),
        "zakat_due": zakat_due,
        "fire_progress_pct": progress["progress_pct"] if progress else None,
    }


def send_monthly_reports(
    db: Session, sender: EmailSender, web_base_url: str, today: dt.date | None = None
) -> int:
    """One report per user per month, for their first household. Shown in the app; emailed
    when the person's MONTHLY_REPORT rule asks for email."""
    today = today or today_dhaka()
    sent = 0
    for user in db.scalars(select(User).where(User.is_active.is_(True))):
        households = list_households(db, user)
        if not households:
            continue
        household, member = households[0]
        figures = monthly_figures(db, user, household.id, member, today)
        dedupe = f"report:{user.id}:{figures['month']}"
        rules = _rules(db, user.id)
        rule = rules.get("MONTHLY_REPORT")
        if rule is not None and not rule.is_active:
            continue
        if db.scalar(select(Notification.id).where(Notification.dedupe_key == dedupe)) is not None:
            continue
        row = Notification(
            user_id=user.id,
            type="MONTHLY_REPORT",
            message_key="MONTHLY_REPORT",
            data={k: (str(v) if v is not None else None) for k, v in figures.items()},
            link="/personal",
            dedupe_key=dedupe,
        )
        db.add(row)
        if (
            rule is not None
            and rule.channel in ("EMAIL", "BOTH")
            and user.email_verified_at is not None
        ):
            locale = user.locale if user.locale in ("bn", "en") else "en"
            subject, body, zakat_line, fire_line, savings_line = REPORT_TEXT[locale]
            text = body.format(
                month=figures["month"],
                spending=taka(figures["spending"], locale),
                savings=savings_line.format(
                    income=taka(figures["income"], locale),
                    savings=taka(figures["savings"], locale),
                )
                if figures["income"] is not None
                else "",
                net_worth=taka(figures["net_worth"], locale),
                zakat=zakat_line.format(amount=taka(figures["zakat_due"], locale))
                if figures["zakat_due"] is not None
                else "",
                fire=fire_line.format(pct=figures["fire_progress_pct"])
                if figures["fire_progress_pct"] is not None
                else "",
                link=f"{web_base_url}/{locale}/personal",
            )
            if send_safely(
                sender,
                Email(
                    to=user.email,
                    subject=subject.format(month=figures["month"]),
                    body=f"{text}\n\n{DISCLAIMER[locale]}",
                ),
            ):
                row.sent_at = utcnow()
        sent += 1
    db.flush()
    return sent


# --- community benchmarks (F21) -------------------------------------------------------


def _age_band(age: Decimal, bands: list[list[int]]) -> tuple[int, int] | None:
    for low, high in bands:
        if low <= age <= high:
            return low, high
    return None


def community_benchmarks(db: Session, user: User) -> dict[str, Any]:
    """Anonymous averages for people in the user's age band (FR21).

    Only people who opted in are counted, each through their newest FIRE plan. A group is
    shown only when it has enough people that no one can be picked out (FR21.1).
    """
    if not has_consent(user, ConsentPurpose.COMMUNITY_BENCHMARKING):
        raise AuthError("CONSENT_REQUIRED", 403)
    config = personal_config()["community"]
    assert isinstance(config, dict)
    bands: list[list[int]] = config["age_bands"]
    minimum = int(config["min_group_size"])

    newest: dict[uuid.UUID, FirePlan] = {}
    owner: dict[uuid.UUID, User] = {}
    rows = db.execute(
        select(FirePlan, User)
        .join(HouseholdMember, HouseholdMember.household_id == FirePlan.household_id)
        .join(User, User.id == HouseholdMember.user_id)
        .where(User.is_active.is_(True))
        .order_by(FirePlan.computed_at)
    ).all()
    for plan, person in rows:
        if has_consent(person, ConsentPurpose.COMMUNITY_BENCHMARKING):
            newest[person.id] = plan
            owner[person.id] = person

    def measures(plan: FirePlan) -> tuple[Decimal, float | None, float]:
        inputs = plan.inputs
        saved = Decimal(inputs["monthly_savings"]) * 12
        income = saved + Decimal(inputs["yearly_expenses"])
        rate = float(saved / income * 100) if income > 0 else None
        progress = 0.0
        if plan.fire_number > 0:
            progress = float(Decimal(inputs["net_worth"]) / plan.fire_number * 100)
        progress = min(progress, 100.0)
        return Decimal(inputs["current_age"]), rate, max(progress, 0.0)

    mine = newest.get(user.id)
    out: dict[str, Any] = {
        "min_group_size": minimum,
        "has_plan": mine is not None,
        "age_band": None,
        "group_size_met": False,
        "you": None,
        "group": None,
    }
    if mine is None:
        return out
    age, my_rate, my_progress = measures(mine)
    band = _age_band(age, bands)
    out["age_band"] = list(band) if band else None
    out["you"] = {
        "savings_rate_pct": Decimal(str(my_rate)).quantize(Q2) if my_rate is not None else None,
        "fire_progress_pct": Decimal(str(my_progress)).quantize(Q2),
    }
    if band is None:
        return out
    peers = [measures(plan) for plan in newest.values()]
    group = [
        (rate, progress) for peer_age, rate, progress in peers if _age_band(peer_age, bands) == band
    ]
    if len(group) < minimum:
        return out
    rates = [rate for rate, _ in group if rate is not None]
    out["group_size_met"] = True
    out["group"] = {
        # Rounded down to the nearest ten, so the exact head count is not given away.
        "size_at_least": len(group) // 10 * 10,
        "median_savings_rate_pct": Decimal(str(statistics.median(rates))).quantize(Q2)
        if rates
        else None,
        "median_fire_progress_pct": Decimal(str(statistics.median(p for _, p in group))).quantize(
            Q2
        ),
    }
    return out
