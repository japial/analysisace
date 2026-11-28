"""The demo seed: complete, labelled as synthetic, and repeatable."""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.trading_calendar import TradingCalendar
from app.models import (
    AltAsset,
    BusinessClassification,
    Company,
    CorporateAction,
    Event,
    Expense,
    ExpenseCategory,
    Financials,
    Holding,
    HouseholdMember,
    IndexDaily,
    MacroSeries,
    OwnerShare,
    PriceDaily,
    Source,
    User,
)
from app.seed.demo_market import COMPANIES, DEMO_SOURCE, seed_demo_market
from app.seed.demo_personal import DEMO_EMAIL, seed_demo_personal
from app.seed.reference import DEFAULT_EXPENSE_CATEGORIES, seed_reference
from app.services import quality


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_reference_seed_adds_default_categories_once_fr12_1(session: Session) -> None:
    assert seed_reference(session) == len(DEFAULT_EXPENSE_CATEGORIES)
    assert seed_reference(session) == 0
    keys = set(session.scalars(select(ExpenseCategory.key)))
    assert {"food_bazar", "rent", "religious_giving", "other"} <= keys


def test_market_seed_is_complete_and_runs_once(session: Session, calendar: TradingCalendar) -> None:
    counts = seed_demo_market(session, calendar)
    assert counts["company"] == len(COMPANIES)
    assert seed_demo_market(session, calendar) == {}  # second run does nothing

    assert count(session, Company) == len(COMPANIES)
    assert count(session, BusinessClassification) == len(COMPANIES)
    assert count(session, PriceDaily) == counts["price_daily"] > 10_000
    assert count(session, Event) == 4
    assert count(session, CorporateAction) == 5
    assert {"DSEX", "DSES", "DS30"} == set(
        session.scalars(select(IndexDaily.index_code).distinct())
    )
    series = set(session.scalars(select(MacroSeries.series_code).distinct()))
    assert {"TBILL_91D", "POLICY_RATE", "CPI_YOY", "BDT_USD", "BRENT_USD"} <= series
    assert {"GOLD_22K_BDT_PER_GRAM", "SILVER_BDT_PER_GRAM"} <= series


def test_all_demo_market_rows_carry_the_synthetic_source(
    session: Session, calendar: TradingCalendar
) -> None:
    """Hard rule: every number is traceable, and demo numbers must say they are demo."""
    seed_demo_market(session, calendar)
    source = session.scalar(select(Source).where(Source.name == DEMO_SOURCE))
    assert source is not None
    assert "synthetic" in source.name
    for model in (PriceDaily, IndexDaily, MacroSeries, Financials, CorporateAction):
        other = session.scalar(
            select(func.count()).select_from(model).where(model.source_id != source.id)
        )
        assert other == 0, model.__name__
    # Fictional companies only: no real ticker gets invented prices.
    assert all(t.startswith("DM") for t in session.scalars(select(Company.ticker)))


def test_demo_prices_pass_the_quality_checks(session: Session, calendar: TradingCalendar) -> None:
    seed_demo_market(session, calendar)
    for ticker in ("DMPHARMA", "DMTECH", "DMPOWER"):
        closes = [
            (d, c)
            for d, c in session.execute(
                select(PriceDaily.date, PriceDaily.close).where(PriceDaily.ticker == ticker)
            )
        ]
        ex_dates = set(
            session.scalars(select(CorporateAction.ex_date).where(CorporateAction.ticker == ticker))
        )
        days = [d for d, _ in closes]
        assert quality.check_missing_trading_days(calendar, min(days), max(days), days, "p") == []
        assert quality.check_unexplained_moves(ticker, closes, ex_dates, Decimal("10")) == []


def test_adjusted_close_removes_the_split_jump(session: Session, calendar: TradingCalendar) -> None:
    seed_demo_market(session, calendar)
    action = session.scalar(select(CorporateAction).where(CorporateAction.ticker == "DMTECH"))
    assert action is not None and action.type == "SPLIT"
    rows = session.execute(
        select(PriceDaily.date, PriceDaily.close, PriceDaily.adj_close)
        .where(PriceDaily.ticker == "DMTECH")
        .order_by(PriceDaily.date)
    ).all()
    index = next(i for i, row in enumerate(rows) if row.date == action.ex_date)
    before, after = rows[index - 1], rows[index]
    assert after.close < before.close * Decimal("0.6")  # raw price roughly halves
    assert abs(after.adj_close / before.adj_close - 1) < Decimal("0.1")  # adjusted does not
    assert rows[-1].adj_close == rows[-1].close


def test_financial_profiles_cover_every_screening_outcome(
    session: Session, calendar: TradingCalendar
) -> None:
    seed_demo_market(session, calendar)
    failed_stage1 = set(
        session.scalars(
            select(BusinessClassification.ticker).where(
                BusinessClassification.stage1_pass.is_(False)
            )
        )
    )
    assert failed_stage1 == {"DMBANK", "DMTOBAC", "DMINSUR"}
    # A report that does not state non-permissible income (leads to UNDER_REVIEW).
    missing = session.scalars(
        select(Financials.ticker).where(Financials.non_permissible_income.is_(None)).distinct()
    ).all()
    assert missing == ["DMTECH"]
    assert count(session, Financials) == 10 * 3


def test_personal_seed_builds_a_household_with_owner_shares(
    session: Session, calendar: TradingCalendar
) -> None:
    seed_demo_market(session, calendar)
    result = seed_demo_personal(session, "demo-pass-1234")
    assert result.created and result.firm_api_key
    assert seed_demo_personal(session, "demo-pass-1234").created is False

    user = session.scalar(select(User).where(User.email == DEMO_EMAIL))
    assert user is not None
    assert user.consents["RELIGIOUS_PREFERENCES"]["granted"] is True  # FR23.2
    members = session.scalars(select(HouseholdMember)).all()
    assert {m.display_name for m in members} == {"Karim Rahman", "Ayesha Rahman"}
    assert sum(m.user_id is None for m in members) == 1  # a member without a login

    assert count(session, Holding) == 14
    assert count(session, AltAsset) == 6
    assert count(session, Expense) > 700
    # Recurring entries are generated once per rule per month (FR12.2).
    rent_days = session.scalars(
        select(Expense.date).where(Expense.recurring_id.is_not(None), Expense.amount == 25000)
    ).all()
    assert len(rent_days) == len(set(rent_days)) == 15
    assert min(rent_days) == date(2025, 9, 1)


def test_owner_shares_never_exceed_100_percent(session: Session, calendar: TradingCalendar) -> None:
    seed_demo_market(session, calendar)
    seed_demo_personal(session, "demo-pass-1234")
    totals = session.execute(
        select(OwnerShare.asset_id, func.sum(OwnerShare.pct)).group_by(OwnerShare.asset_id)
    ).all()
    assert totals
    assert all(total == Decimal(100) for _, total in totals)


def test_unit_tests_enforce_foreign_keys(session: Session, source: Source) -> None:
    """Guards the test setup itself: a row pointing at a missing company must be refused."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    session.add(PriceDaily(ticker="NOPE", date=date(2026, 1, 4), close=1, source_id=source.id))
    with pytest.raises(IntegrityError):
        session.flush()


def test_demo_extras_fill_every_personal_page_f13_f17_f18_f21(
    session: Session, calendar: TradingCalendar
) -> None:
    """The demo user sees plans, what-ifs, Zakat, tax, notices and a peer group (D15)."""
    from app.models import FirePlan, Notification, ScenarioResult, TaxSnapshot, ZakatSnapshot
    from app.seed.demo_extras import ADMIN_EMAIL, PEER_COUNT, seed_demo_extras
    from app.services.alerts import community_benchmarks
    from app.services.email import LoggingEmailSender

    seed_demo_market(session, calendar)
    seed_demo_personal(session, "demo-pass-1234")
    result = seed_demo_extras(session, LoggingEmailSender(), "demo-pass-1234")
    assert result.created
    assert seed_demo_extras(session, LoggingEmailSender(), "demo-pass-1234").created is False

    user = session.scalar(select(User).where(User.email == DEMO_EMAIL))
    assert user is not None
    assert count(session, FirePlan) == 2 + PEER_COUNT
    assert count(session, ScenarioResult) >= 4
    assert count(session, ZakatSnapshot) == 2
    assert count(session, TaxSnapshot) == 1
    assert session.scalar(
        select(func.count()).select_from(Notification).where(Notification.user_id == user.id)
    )
    admin = session.scalar(select(User).where(User.email == ADMIN_EMAIL))
    assert admin is not None and admin.role == "ADMIN"
    # FR21.1: the peer group is big enough to show.
    assert community_benchmarks(session, user)["group_size_met"] is True
