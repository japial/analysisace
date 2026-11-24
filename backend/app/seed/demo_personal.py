"""A fictional household, firm and staff user for development and demos.

All people, banks and brokers here are invented. Run after `seed_demo_market`, because
share holdings are bought at the seeded demo prices.
"""

import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.analytics.costs import add_months, month_start
from app.core.permissions import Role
from app.core.security import hash_token, new_token, utcnow
from app.models import (
    Account,
    AlertRule,
    AltAsset,
    ApiKey,
    CashFlow,
    Expense,
    ExpenseCategory,
    Firm,
    FirmSeat,
    Goal,
    Holding,
    Household,
    HouseholdMember,
    IncomeEntry,
    IncomeRule,
    IslamicProduct,
    Liability,
    MacroSeries,
    OwnerShare,
    PriceDaily,
    RecurringRule,
    Subscription,
    SukukIssue,
    TargetAllocation,
    Transaction,
    User,
    Valuation,
    Watchlist,
)
from app.seed.demo_market import END
from app.seed.reference import seed_reference
from app.services.auth import ConsentPurpose, get_user_by_email, register_user
from app.services.portfolio import store_net_worth

D = Decimal
DEMO_EMAIL = "demo@example.com"
ANALYST_EMAIL = "analyst@example.com"
FIRM_EMAIL = "firm@example.com"
EXPENSES_FROM = date(2025, 9, 1)


@dataclass
class DemoPersonalResult:
    created: bool
    counts: dict[str, int]
    # Shown once by the seed script; only its hash is stored.
    firm_api_key: str | None = None


def _price_on(session: Session, ticker: str, day: date) -> Decimal:
    """Demo close on the last session on or before `day`."""
    price = session.scalar(
        select(PriceDaily.close)
        .where(PriceDaily.ticker == ticker, PriceDaily.date <= day)
        .order_by(PriceDaily.date.desc())
        .limit(1)
    )
    if price is None:
        raise RuntimeError(f"No demo price for {ticker}; run the market seed first")
    return price


def _user(session: Session, email: str, name: str, password: str, role: Role, locale: str) -> User:
    user = register_user(
        session,
        email=email,
        password=password,
        full_name=name,
        locale=locale,
        accept_terms=True,
        role=role,
    )
    # Demo addresses are fictional; mark them confirmed so alert emails behave as in use (D25).
    user.email_verified_at = utcnow()
    return user


def seed_demo_personal(session: Session, password: str) -> DemoPersonalResult:
    """Create the demo users and their data. Does nothing if the demo user exists."""
    if get_user_by_email(session, DEMO_EMAIL) is not None:
        return DemoPersonalResult(created=False, counts={})

    seed_reference(session)
    rng = random.Random(20261115)
    now = datetime.now(UTC)
    counts: dict[str, int] = {}

    # --- users --------------------------------------------------------------------
    karim = _user(session, DEMO_EMAIL, "Karim Rahman", password, Role.USER, "en")
    _user(session, ANALYST_EMAIL, "Nadia Analyst", password, Role.ANALYST, "en")
    firm_user = _user(session, FIRM_EMAIL, "Farhan Broker", password, Role.USER, "en")
    # Hawl date and nisab basis are religious preferences, so the consent is recorded (FR23.2).
    karim.consents = {
        **karim.consents,
        ConsentPurpose.RELIGIOUS_PREFERENCES.value: {"granted": True, "at": now.isoformat()},
    }
    counts["users"] = 3

    # --- household (F24) ----------------------------------------------------------
    household = Household(name="Rahman family", created_by=karim.id)
    session.add(household)
    session.flush()
    hid = household.id
    m_karim = HouseholdMember(
        household_id=hid,
        user_id=karim.id,
        display_name="Karim Rahman",
        role="OWNER",
        birth_year=1988,
        hawl_date=date(2027, 2, 18),
        nisab_basis="GOLD",
    )
    m_ayesha = HouseholdMember(
        household_id=hid,
        user_id=None,
        display_name="Ayesha Rahman",
        role="EDITOR",
        birth_year=1990,
        hawl_date=date(2027, 2, 18),
        nisab_basis="SILVER",
    )
    session.add_all([m_karim, m_ayesha])
    session.flush()

    def share(kind: str, asset_id: object, *owners: tuple[HouseholdMember | str, str]) -> None:
        for owner, pct in owners:
            session.add(
                OwnerShare(
                    asset_kind=kind,
                    asset_id=asset_id,
                    member_id=None if isinstance(owner, str) else owner.id,
                    external_name=owner if isinstance(owner, str) else None,
                    pct=D(pct),
                )
            )

    # --- accounts and holdings (F14, F26) -----------------------------------------
    def account(kind: str, institution: str, name: str, masked: str | None = None) -> Account:
        row = Account(
            household_id=hid, type=kind, institution=institution, name=name, masked_number=masked
        )
        session.add(row)
        session.flush()
        return row

    bo = account("BO", "Demo Securities Ltd.", "Karim BO account", "••••4821")
    islamic = account("ISLAMIC_BANK", "Demo Islami Bank PLC", "Islami bank deposits", "••••7730")
    sukuk_acct = account("SUKUK", "Demo Islami Bank PLC", "Government sukuk")
    bank = account("FDR", "Demo Commercial Bank PLC", "Fixed deposit", "••••1054")
    certs = account("SAVINGS_CERTIFICATE", "National Savings Directorate", "Sanchayapatra")
    pf = account("PROVIDENT_FUND", "Employer provident fund", "Provident fund")
    cash = account("CASH", "Cash and bank", "Cash and current account")

    holdings: list[Holding] = []

    def holding(
        acct: Account, kind: str, name: str, cost: str, owner: HouseholdMember, **fields: object
    ) -> Holding:
        row = Holding(account_id=acct.id, instrument_type=kind, name=name, cost=D(cost), **fields)
        session.add(row)
        session.flush()
        share("HOLDING", row.id, (owner, "100"))
        holdings.append(row)
        return row

    n_tx = 0
    for ticker, quantity, bought in (
        ("DMPHARMA", 500, date(2024, 3, 10)),
        ("DMTEL", 300, date(2024, 8, 18)),
        ("DMCEMENT", 800, date(2025, 2, 9)),
        ("DMPOWER", 400, date(2023, 6, 11)),
        ("DMISLBANK", 2000, date(2025, 9, 14)),
        ("DMBANK", 1000, date(2022, 5, 15)),
    ):
        price = _price_on(session, ticker, bought)
        cost = (price * quantity).quantize(D("0.01"))
        row = holding(
            bo,
            "DSE_SHARE",
            ticker,
            str(cost),
            m_karim,
            ticker=ticker,
            quantity=D(quantity),
            start_date=bought,
        )
        session.add(
            Transaction(holding_id=row.id, date=bought, type="BUY", amount=cost, units=D(quantity))
        )
        n_tx += 1
    # A dividend with tax deducted at source, for the tax view (FR13.6).
    tel = next(h for h in holdings if h.ticker == "DMTEL")
    session.add_all(
        [
            Transaction(
                holding_id=tel.id,
                date=date(2026, 4, 30),
                type="DIVIDEND",
                amount=D("3600.00"),
                note="Cash dividend Tk 12 per share",
            ),
            Transaction(
                holding_id=tel.id,
                date=date(2026, 4, 30),
                type="TAX",
                amount=D("360.00"),
                note="Tax deducted at source 10%",
            ),
        ]
    )
    tel.profit_received, tel.tax_deducted = D("3600.00"), D("360.00")
    n_tx += 2

    term = session.scalar(
        select(IslamicProduct).where(
            IslamicProduct.name == "Mudaraba Term Deposit",
            IslamicProduct.tenor_months == 12,
            IslamicProduct.bank == "Demo Islami Bank PLC",
        )
    )
    scheme = session.scalar(
        select(IslamicProduct).where(IslamicProduct.product_type == "MUDARABA_SAVINGS_SCHEME")
    )
    sukuk = session.scalar(select(SukukIssue).where(SukukIssue.code == "IRIDPNFL"))
    assert term is not None and scheme is not None and sukuk is not None

    holding(
        islamic,
        "ISLAMIC_DEPOSIT",
        "Mudaraba Term Deposit (12 months)",
        "300000",
        m_karim,
        product_id=term.id,
        manual_value=D("300000"),
        start_date=date(2026, 1, 15),
        maturity_date=date(2027, 1, 15),
        expected_rate=D("9.25"),
        payment_frequency="AT_MATURITY",
    )
    holding(
        islamic,
        "ISLAMIC_DEPOSIT",
        "Mudaraba Monthly Savings Scheme",
        "70000",
        m_ayesha,
        product_id=scheme.id,
        manual_value=D("72650"),
        start_date=date(2025, 9, 1),
        maturity_date=date(2030, 9, 1),
        expected_rate=D("9.60"),
        payment_frequency="AT_MATURITY",
    )
    holding(
        sukuk_acct,
        "SUKUK",
        "Bangladesh Government Investment Sukuk (IRIDPNFL)",
        "100000",
        m_karim,
        sukuk_issue_id=sukuk.id,
        manual_value=D("100000"),
        start_date=date(2024, 6, 20),
        maturity_date=date(2031, 6, 20),
        expected_rate=D("9.60"),
        payment_frequency="HALF_YEARLY",
        profit_received=D("19200"),
        tax_deducted=D("960"),
    )
    holding(
        bank,
        "FDR",
        "Fixed deposit (1 year)",
        "200000",
        m_karim,
        manual_value=D("200000"),
        start_date=date(2026, 3, 1),
        maturity_date=date(2027, 3, 1),
        expected_rate=D("8.50"),
        payment_frequency="AT_MATURITY",
        is_interest_bearing=True,
    )
    holding(
        certs,
        "SAVINGS_CERTIFICATE",
        "5-year Bangladesh Sanchayapatra",
        "500000",
        m_ayesha,
        manual_value=D("500000"),
        start_date=date(2023, 10, 5),
        maturity_date=date(2028, 10, 5),
        expected_rate=D("11.28"),
        payment_frequency="QUARTERLY",
        is_interest_bearing=True,
        profit_received=D("141000"),
        tax_deducted=D("14100"),
    )
    holding(
        pf, "PROVIDENT_FUND", "Provident fund balance", "480000", m_karim, manual_value=D("650000")
    )
    holding(cash, "CASH", "Cash at home", "85000", m_karim, manual_value=D("85000"))
    holding(
        cash, "BANK_BALANCE", "Current account balance", "240000", m_karim, manual_value=D("240000")
    )
    counts["accounts"] = 7
    counts["holdings"] = len(holdings)
    counts["transactions"] = n_tx

    # --- alternative investments (F25) --------------------------------------------
    gold_price = session.scalar(
        select(MacroSeries.value)
        .where(MacroSeries.series_code == "GOLD_22K_BDT_PER_GRAM")
        .order_by(MacroSeries.date.desc())
        .limit(1)
    ) or D("9000")

    def alt(
        kind: str, name: str, cost: str, bought: date, liquidity: str, **fields: object
    ) -> AltAsset:
        row = AltAsset(
            household_id=hid,
            type=kind,
            name=name,
            cost=D(cost),
            purchase_date=bought,
            liquidity=liquidity,
            **fields,
        )
        session.add(row)
        session.flush()
        return row

    def value(asset: AltAsset, day: date, amount: Decimal | str, method: str = "MANUAL") -> None:
        session.add(
            Valuation(
                asset_kind="ALT_ASSET", asset_id=asset.id, date=day, value=D(amount), method=method
            )
        )

    home = alt(
        "FAMILY_HOME",
        "Family flat, Mirpur",
        "6000000",
        date(2018, 4, 1),
        ">1Y",
        shariah_flag="COMPLIANT",
    )
    value(home, date(2026, 1, 1), "8500000")
    share("ALT_ASSET", home.id, (m_karim, "50"), (m_ayesha, "50"))

    land = alt(
        "LAND",
        "Plot in Gazipur (held for resale)",
        "2500000",
        date(2019, 11, 20),
        ">1Y",
        shariah_flag="COMPLIANT",
        zakat_rule="property_for_resale",
        notes="5 katha. Deed registered.",
    )
    value(land, date(2024, 1, 1), "3600000")
    value(land, date(2026, 1, 1), "4200000")
    share("ALT_ASSET", land.id, (m_karim, "50"), (m_ayesha, "50"))

    gold = alt(
        "GOLD",
        "Gold jewellery (22 karat)",
        "480000",
        date(2016, 2, 14),
        "<1M",
        weight_grams=D("80"),
        karat=22,
        revaluation_months=6,
        shariah_flag="COMPLIANT",
    )
    value(gold, END, (gold_price * 80).quantize(D("0.01")), "METAL_PRICE")
    share("ALT_ASSET", gold.id, (m_ayesha, "100"))

    flat = alt(
        "RENTAL_PROPERTY",
        "Rental flat, Uttara",
        "4500000",
        date(2021, 7, 1),
        ">1Y",
        shariah_flag="COMPLIANT",
    )
    value(flat, date(2026, 1, 1), "5800000")
    share("ALT_ASSET", flat.id, (m_karim, "60"), ("Rafiq Rahman (brother)", "40"))
    flows = [
        CashFlow(
            asset_id=flat.id,
            date=date(2021, 7, 1),
            amount=D("-4500000"),
            type="CAPITAL_ADDED",
            note="Purchase",
        )
    ]
    month = date(2021, 9, 1)
    while month <= END:
        flows.append(CashFlow(asset_id=flat.id, date=month, amount=D("22000"), type="RENT"))
        month = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
    session.add_all(flows)

    loan = alt(
        "PRIVATE_LOAN",
        "Interest-free loan to a cousin",
        "150000",
        date(2025, 5, 10),
        "<1Y",
        counterparty="Cousin",
        expected_exit_date=date(2027, 5, 10),
        shariah_flag="COMPLIANT",
        is_recoverable=True,
    )
    value(loan, date(2025, 5, 10), "150000")
    share("ALT_ASSET", loan.id, (m_karim, "100"))

    stake = alt(
        "BUSINESS_STAKE",
        "20% stake in a friend's poultry farm",
        "400000",
        date(2024, 2, 1),
        ">1Y",
        counterparty="Green Poultry (partnership)",
        shariah_flag="COMPLIANT",
        due_diligence={
            "registered_business": True,
            "written_agreement": True,
            "promised_return_pct": "18",
            "tbill_yield_pct_at_entry": "11.2",
        },
    )
    value(stake, date(2026, 6, 30), "460000")
    share("ALT_ASSET", stake.id, (m_karim, "100"))
    session.add_all(
        [
            CashFlow(
                asset_id=stake.id, date=date(2024, 2, 1), amount=D("-400000"), type="CAPITAL_ADDED"
            ),
            CashFlow(
                asset_id=stake.id, date=date(2025, 1, 31), amount=D("52000"), type="PROFIT_SHARE"
            ),
            CashFlow(
                asset_id=stake.id, date=date(2026, 1, 31), amount=D("61000"), type="PROFIT_SHARE"
            ),
        ]
    )
    counts["alt_assets"] = 6

    # --- liabilities --------------------------------------------------------------
    home_loan = Liability(
        household_id=hid,
        type="HOME_LOAN",
        name="Home loan",
        lender="Demo Commercial Bank PLC",
        outstanding=D("1800000"),
        due_within_year=D("240000"),
        is_interest_bearing=True,
        end_date=date(2033, 4, 1),
    )
    debt = Liability(
        household_id=hid,
        type="PRIVATE_DEBT",
        name="Borrowed from a friend",
        outstanding=D("50000"),
        due_within_year=D("50000"),
    )
    session.add_all([home_loan, debt])
    session.flush()
    share("LIABILITY", home_loan.id, (m_karim, "50"), (m_ayesha, "50"))
    share("LIABILITY", debt.id, (m_karim, "100"))
    counts["liabilities"] = 2

    # --- daily costs (F12) --------------------------------------------------------
    category = {
        c.key: c.id
        for c in session.scalars(
            select(ExpenseCategory).where(ExpenseCategory.household_id.is_(None))
        )
    }
    rules = [
        RecurringRule(
            household_id=hid,
            member_id=m_karim.id,
            category_id=category["rent"],
            amount=D("25000"),
            note="Garage and service charge",
            frequency="MONTHLY",
            start_date=EXPENSES_FROM,
        ),
        RecurringRule(
            household_id=hid,
            member_id=m_ayesha.id,
            category_id=category["education"],
            amount=D("8000"),
            note="School fees",
            frequency="MONTHLY",
            start_date=EXPENSES_FROM,
        ),
        RecurringRule(
            household_id=hid,
            member_id=m_karim.id,
            category_id=category["family_support"],
            amount=D("10000"),
            note="Sent to parents",
            frequency="MONTHLY",
            start_date=EXPENSES_FROM,
        ),
    ]
    session.add_all(rules)
    session.flush()

    expenses: list[dict[str, object]] = []

    def spend(
        day: date,
        key: str,
        amount: float,
        note: str | None = None,
        rule: RecurringRule | None = None,
        member: HouseholdMember = m_karim,
    ) -> None:
        expenses.append(
            {
                "household_id": hid,
                "member_id": member.id,
                "date": day,
                "amount": D(str(round(amount / 10) * 10)),
                "category_id": category[key],
                "note": note,
                "recurring_id": rule.id if rule else None,
            }
        )

    day = EXPENSES_FROM
    while day <= END:
        if day.day == 1:
            for rule in rules:
                spend(
                    day,
                    "rent"
                    if rule is rules[0]
                    else "education"
                    if rule is rules[1]
                    else "family_support",
                    float(rule.amount),
                    rule.note,
                    rule,
                )
        if day.day == 5:
            spend(day, "utilities", rng.uniform(4200, 6800), "Electricity, gas, water, internet")
        if rng.random() < 0.8:
            spend(
                day,
                "food_bazar",
                rng.uniform(350, 1900),
                member=m_ayesha if rng.random() < 0.6 else m_karim,
            )
        if day.weekday() in (6, 0, 1, 2, 3) and rng.random() < 0.85:
            spend(day, "transport", rng.uniform(120, 420))
        if rng.random() < 0.05:
            spend(day, "health", rng.uniform(600, 4500), "Doctor and medicine")
        if day.weekday() == 4 and rng.random() < 0.7:
            spend(day, "religious_giving", rng.uniform(100, 1000), "Sadaqah")
        if rng.random() < 0.06:
            spend(day, "other", rng.uniform(500, 6000))
        day += timedelta(days=1)
    session.execute(insert(Expense), expenses)
    counts["expenses"] = len(expenses)

    # --- income (F27): two salaries as recurring rules, and a yearly bonus --------
    salary_rules = [
        IncomeRule(
            household_id=hid,
            member_id=m_karim.id,
            kind="SALARY",
            amount=D("120000"),
            note="Demo salary",
            frequency="MONTHLY",
            start_date=EXPENSES_FROM,
        ),
        IncomeRule(
            household_id=hid,
            member_id=m_ayesha.id,
            kind="SALARY",
            amount=D("45000"),
            note="Demo salary",
            frequency="MONTHLY",
            start_date=EXPENSES_FROM,
        ),
    ]
    session.add_all(salary_rules)
    session.flush()
    incomes: list[dict[str, object]] = []
    day = EXPENSES_FROM
    while day <= END:
        if day.day == 1:
            for salary in salary_rules:
                incomes.append(
                    {
                        "household_id": hid,
                        "member_id": salary.member_id,
                        "date": day,
                        "amount": salary.amount,
                        "kind": salary.kind,
                        "note": salary.note,
                        "recurring_id": salary.id,
                    }
                )
        if day.month == 6 and day.day == 20:
            incomes.append(
                {
                    "household_id": hid,
                    "member_id": m_karim.id,
                    "date": day,
                    "amount": D("150000"),
                    "kind": "SALARY",
                    "note": "Demo festival bonus",
                    "recurring_id": None,
                }
            )
        day += timedelta(days=1)
    session.execute(insert(IncomeEntry), incomes)
    counts["income_entries"] = len(incomes)

    # --- goals, target allocation, watchlist, alerts ------------------------------
    session.add_all(
        [
            Goal(
                household_id=hid,
                type="NET_WORTH",
                name="Net worth of Tk 3 crore",
                target_amount=D("30000000"),
                target_date=date(2032, 12, 31),
            ),
            Goal(
                household_id=hid,
                member_id=m_karim.id,
                type="INVESTED_AMOUNT",
                name="Tk 25 lakh invested in shares and sukuk",
                target_amount=D("2500000"),
            ),
            Goal(
                household_id=hid,
                member_id=m_karim.id,
                type="FIRE_AGE",
                name="Financially independent by 52",
                target_age=52,
            ),
        ]
    )
    for asset_class, target, band in (
        ("EQUITY", "15", "5"),
        ("ISLAMIC_FIXED_INCOME", "10", "3"),
        ("CONVENTIONAL_FIXED_INCOME", "5", "3"),
        ("PROPERTY", "55", "10"),
        ("GOLD", "5", "2"),
        ("CASH", "5", "3"),
        ("OTHER", "5", "3"),
    ):
        session.add(
            TargetAllocation(
                household_id=hid, asset_class=asset_class, target_pct=D(target), band_pct=D(band)
            )
        )
    session.add_all(
        [
            Watchlist(user_id=karim.id, ticker="DMFOOD"),
            Watchlist(user_id=karim.id, ticker="DMSTEEL"),
        ]
    )
    for kind, channel, frequency in (
        ("SHARIAH_STATUS", "BOTH", "INSTANT"),
        ("SHOCK_EVENT", "EMAIL", "INSTANT"),
        ("MATURITY_DUE", "EMAIL", "DAILY_DIGEST"),
        ("HAWL_APPROACHING", "EMAIL", "INSTANT"),
        ("ALLOCATION_DRIFT", "EMAIL", "DAILY_DIGEST"),
    ):
        session.add(AlertRule(user_id=karim.id, type=kind, channel=channel, frequency=frequency))
    session.add(
        Subscription(
            user_id=karim.id, plan="PRO", status="ACTIVE", provider="MANUAL", provider_ref="demo"
        )
    )

    # --- firm (F9) ----------------------------------------------------------------
    firm = Firm(
        name="Demo Brokerage Ltd.",
        report_disclaimer="For clients of Demo Brokerage Ltd. Historical analysis for education only. Not investment advice.",
        seat_limit=5,
    )
    session.add(firm)
    session.flush()
    api_key = f"dn_demo_{new_token()}"
    session.add_all(
        [
            FirmSeat(firm_id=firm.id, user_id=firm_user.id, role="ADMIN"),
            ApiKey(
                firm_id=firm.id,
                name="Research desk",
                prefix=api_key[:12],
                key_hash=hash_token(api_key),
            ),
            Subscription(
                firm_id=firm.id,
                plan="FIRM",
                status="ACTIVE",
                provider="MANUAL",
                provider_ref="demo",
            ),
        ]
    )
    counts["firms"] = 1
    session.flush()

    # --- ACE trend (D23): month-end snapshots for the last 12 months ---------------
    snapshot_days = [
        add_months(month_start(END), -n) - timedelta(days=1) for n in range(11, -1, -1)
    ] + [END]
    for day in snapshot_days:
        store_net_worth(session, hid, day)
    counts["net_worth_snapshots"] = len(snapshot_days)
    session.flush()
    return DemoPersonalResult(created=True, counts=counts, firm_api_key=api_key)
