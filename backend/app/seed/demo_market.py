"""Synthetic market data for development and demos.

NOTHING HERE IS REAL MARKET DATA. Companies are fictional (tickers start with "DM"),
prices are a seeded random walk, and macro series only follow a plausible shape. Every row
points at a `source` named DEMO_SOURCE, so the app shows it as demo data wherever it
appears. Index codes (DSEX, DSES, DS30) are the real names, but the levels are synthetic.

Only base data is seeded. Screening results, scores, event metrics and regimes are left to
the analytics jobs, so those numbers are always computed, never typed in.
"""

import itertools
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from math import exp

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.analytics.adjustment import Action, back_adjust
from app.core.app_config import get_config
from app.core.trading_calendar import TradingCalendar
from app.models import (
    BankFlag,
    BusinessClassification,
    Company,
    CorporateAction,
    CorporateActionType,
    Event,
    Financials,
    IndexDaily,
    IslamicProduct,
    MacroSeries,
    PriceDaily,
    Source,
    SukukIssue,
)

DEMO_SOURCE = "Demo data (synthetic, not real market data)"
START = date(2021, 11, 1)
END = date(2026, 11, 12)
D = Decimal
Q4 = D("0.0001")
Q2 = D("0.01")


@dataclass(frozen=True)
class DemoCompany:
    ticker: str
    name: str
    sector: str
    base_price: float
    shares: int
    market_beta: float
    # Percent move per 1-point rise in the 91-day yield, built into the price path (F3).
    rate_beta: float
    shock_mult: float
    # Stage 1 (PRD 7.1): None passes; otherwise the excluded activity.
    excluded_activity: str | None
    stage1_reason: str
    # Financial profile as percent of market cap (revenue-based for income). None = not stated.
    debt_pct: float | None
    cash_pct: float | None
    npi_pct: float | None
    recv_pct: float | None


# The profiles are chosen so the screen shows every outcome: pass, fail by debt, fail by
# income, a borderline case, a missing input, and methods that disagree.
COMPANIES = [
    DemoCompany(
        "DMPHARMA",
        "Demo Pharma Ltd.",
        "Pharmaceuticals & Chemicals",
        210,
        880_000_000,
        0.8,
        -1.0,
        0.7,
        None,
        "Makes medicines.",
        12,
        8,
        1.2,
        20,
    ),
    DemoCompany(
        "DMTEL",
        "Demo Telecom PLC",
        "Telecommunication",
        320,
        1_350_000_000,
        0.9,
        -2.5,
        0.9,
        None,
        "Mobile network operator.",
        22,
        10,
        2.0,
        15,
    ),
    DemoCompany(
        "DMCEMENT",
        "Demo Cement Ltd.",
        "Cement",
        68,
        1_160_000_000,
        1.1,
        -4.0,
        1.2,
        None,
        "Makes cement.",
        29.2,
        9,
        1.5,
        24,
    ),
    DemoCompany(
        "DMPOWER",
        "Demo Power Generation Ltd.",
        "Fuel & Power",
        145,
        580_000_000,
        1.0,
        -5.5,
        1.5,
        None,
        "Runs power plants.",
        45,
        6,
        0.8,
        30,
    ),
    DemoCompany(
        "DMTEX",
        "Demo Textiles Ltd.",
        "Textile",
        42,
        310_000_000,
        1.2,
        -3.0,
        1.3,
        None,
        "Makes garments and fabric.",
        18,
        6,
        6.5,
        28,
    ),
    DemoCompany(
        "DMFOOD",
        "Demo Foods Ltd.",
        "Food & Allied",
        185,
        200_000_000,
        0.7,
        -0.5,
        0.6,
        None,
        "Makes packaged food.",
        9,
        12,
        0.9,
        11,
    ),
    DemoCompany(
        "DMSTEEL",
        "Demo Steel Mills Ltd.",
        "Engineering",
        92,
        300_000_000,
        1.3,
        -6.0,
        1.4,
        None,
        "Makes steel rods.",
        31.5,
        7,
        1.1,
        26,
    ),
    DemoCompany(
        "DMTECH",
        "Demo Technologies Ltd.",
        "IT Sector",
        58,
        150_000_000,
        1.4,
        1.5,
        1.1,
        None,
        "Software and IT services.",
        6,
        21,
        None,
        18,
    ),
    DemoCompany(
        "DMAGRO",
        "Demo Agro Industries Ltd.",
        "Food & Allied",
        76,
        120_000_000,
        0.9,
        -1.5,
        0.8,
        None,
        "Farms and processes crops.",
        14,
        5,
        2.4,
        52,
    ),
    DemoCompany(
        "DMISLBANK",
        "Demo Islami Bank PLC",
        "Bank",
        34,
        1_600_000_000,
        1.0,
        2.5,
        1.0,
        None,
        "Islamic bank; passes the activity stage.",
        0,
        14,
        0.6,
        10,
    ),
    DemoCompany(
        "DMBANK",
        "Demo Commercial Bank PLC",
        "Bank",
        28,
        1_200_000_000,
        1.0,
        3.0,
        1.0,
        "conventional_banking",
        "Conventional bank: income is interest-based.",
        None,
        None,
        None,
        None,
    ),
    DemoCompany(
        "DMTOBAC",
        "Demo Tobacco Company Ltd.",
        "Food & Allied",
        410,
        540_000_000,
        0.6,
        -0.5,
        0.5,
        "tobacco",
        "Makes cigarettes.",
        None,
        None,
        None,
        None,
    ),
    DemoCompany(
        "DMINSUR",
        "Demo General Insurance Ltd.",
        "Insurance",
        47,
        90_000_000,
        1.1,
        1.0,
        1.0,
        "conventional_insurance",
        "Conventional insurer.",
        None,
        None,
        None,
        None,
    ),
]

# (first day, type, slug, English title, Bangla title, description en, description bn, published)
EVENTS = [
    (
        date(2022, 2, 24),
        "WAR",
        "russia-ukraine-2022",
        "Russia-Ukraine war begins",
        "রাশিয়া-ইউক্রেন যুদ্ধ শুরু",
        "Russia invaded Ukraine. Energy and commodity prices rose worldwide.",
        "রাশিয়া ইউক্রেনে হামলা চালায়। বিশ্বজুড়ে জ্বালানি ও পণ্যের দাম বাড়ে।",
        True,
    ),
    (
        date(2025, 6, 22),
        "WAR",
        "us-strikes-iran-israel-war-2025",
        "US strikes in the Iran-Israel war",
        "ইরান-ইসরায়েল যুদ্ধে যুক্তরাষ্ট্রের হামলা",
        "The United States struck sites in Iran during the Iran-Israel war.",
        "ইরান-ইসরায়েল যুদ্ধের সময় যুক্তরাষ্ট্র ইরানের কয়েকটি স্থাপনায় হামলা চালায়।",
        True,
    ),
    (
        date(2026, 2, 28),
        "WAR",
        "strikes-on-iran-2026",
        "Strikes on Iran",
        "ইরানে হামলা",
        "Strikes on Iran began. PRD reference: the DSEX fell 4.42% on 8 March 2026.",
        "ইরানে হামলা শুরু হয়। ২০২৬ সালের ৮ মার্চ ডিএসইএক্স ৪.৪২% কমে।",
        True,
    ),
    # PRD: "exact date to curate". Kept unpublished until an admin confirms the date.
    (
        date(2026, 7, 28),
        "ENERGY",
        "maheshkhali-lng-fire-2026",
        "Maheshkhali LNG terminal fire",
        "মহেশখালী এলএনজি টার্মিনালে আগুন",
        "Fire at the Maheshkhali LNG terminal. The exact date still has to be confirmed.",
        "মহেশখালী এলএনজি টার্মিনালে আগুন লাগে। সঠিক তারিখ এখনো নিশ্চিত করা হয়নি।",
        False,
    ),
]

# Market-wide daily shocks after each event start: an initial fall, then a slow recovery.
_SHOCK_PATTERN = [-0.035, -0.022, -0.012] + [0.004] * 14


def _yield_path(day: date) -> float:
    """Shape of the 91-day yield: low in 2021, a peak in mid 2025, easing after."""
    anchors = [
        (date(2021, 11, 1), 2.4),
        (date(2022, 12, 1), 6.9),
        (date(2023, 12, 1), 11.0),
        (date(2025, 6, 1), 11.94),
        (date(2026, 10, 1), 7.65),
        (date(2026, 12, 1), 7.5),
    ]
    for (d0, v0), (d1, v1) in itertools.pairwise(anchors):
        if d0 <= day <= d1:
            return v0 + (v1 - v0) * (day - d0).days / (d1 - d0).days
    return anchors[-1][1]


def _month_starts(start: date, end: date) -> list[date]:
    out, current = [], date(start.year, start.month, 1)
    while current <= end:
        out.append(current)
        current = date(current.year + (current.month == 12), current.month % 12 + 1, 1)
    return out


def _on_or_after(days: list[date], target: date) -> date:
    return next(d for d in days if d >= target)


def seed_demo_market(session: Session, calendar: TradingCalendar) -> dict[str, int]:
    """Insert the synthetic market data set. Does nothing if it is already there."""
    if session.scalar(select(Source).where(Source.name == DEMO_SOURCE)) is not None:
        return {}

    rng = random.Random(20261114)
    now = datetime.now(UTC)
    source = Source(name=DEMO_SOURCE, url=None, fetched_at=now)
    session.add(source)
    session.flush()
    sid = source.id
    days = calendar.trading_days(START, END)
    counts: dict[str, int] = {}

    # --- macro series -------------------------------------------------------------
    macro: list[dict[str, object]] = []

    def add_series(code: str, day: date, value: float, places: str = "0.01") -> None:
        macro.append(
            {
                "series_code": code,
                "date": day,
                "value": D(str(value)).quantize(D(places)),
                "source_id": sid,
            }
        )

    # Auctions on the first session of each DSE week.
    auction_days = sorted(
        {
            min(d for d in days if TradingCalendar.week_start(d) == w)
            for w in {TradingCalendar.week_start(d) for d in days}
        }
    )
    yield_change: dict[date, float] = {}
    previous = None
    for day in auction_days:
        y91 = round(_yield_path(day) + rng.gauss(0, 0.06), 2)
        add_series("TBILL_91D", day, y91)
        add_series("TBILL_182D", day, y91 + 0.32)
        add_series("TBILL_364D", day, y91 + 0.61)
        if previous is not None:
            yield_change[day] = y91 - previous
        previous = y91

    for month in _month_starts(START, END):
        y = _yield_path(month)
        add_series("POLICY_RATE", month, round((y * 0.75 + 1.5) * 4) / 4)
        add_series("CPI_YOY", month, 5.6 + (y - 2.4) * 0.52 + rng.gauss(0, 0.15))
        add_series(
            "REMITTANCE_USD_MN", month, 1750 + (month - START).days * 0.45 + rng.gauss(0, 90), "1"
        )

    event_days = [t0 for t0, *_ in EVENTS]
    brent, bdt, gold, silver = 82.0, 85.8, 5400.0, 96.0
    for day in days:
        brent *= exp(rng.gauss(0, 0.012))
        # Oil jumps when a war or energy event starts.
        if any(0 <= (day - t0).days <= 6 for t0 in event_days):
            brent *= 1.03
        elif brent > 95:
            brent *= 0.996
        bdt = min(bdt * exp(rng.gauss(0.00028, 0.0009)), 123.5)
        gold *= exp(rng.gauss(0.0006, 0.006))
        silver *= exp(rng.gauss(0.0005, 0.009))
        add_series("BRENT_USD", day, brent)
        add_series("BDT_USD", day, bdt)
        add_series("GOLD_22K_BDT_PER_GRAM", day, gold)
        add_series("SILVER_BDT_PER_GRAM", day, silver)
    session.execute(insert(MacroSeries), macro)
    counts["macro_series"] = len(macro)

    # --- market factor and event shocks -------------------------------------------
    index_of = {d: i for i, d in enumerate(days)}
    shock = [0.0] * len(days)
    for t0 in event_days:
        first = index_of[_on_or_after(days, t0)]
        for offset, value in enumerate(_SHOCK_PATTERN):
            if first + offset < len(days):
                shock[first + offset] += value
    market = [rng.gauss(0.00025, 0.0075) for _ in days]

    indices: list[dict[str, object]] = []
    for code, base, beta, noise in (
        ("DSEX", 6900.0, 1.0, 0.0),
        ("DSES", 1480.0, 0.93, 0.002),
        ("DS30", 2620.0, 1.05, 0.002),
    ):
        level = base
        for i, day in enumerate(days):
            level *= exp(beta * market[i] + shock[i] + (rng.gauss(0, noise) if noise else 0.0))
            indices.append(
                {
                    "index_code": code,
                    "date": day,
                    "close": D(str(level)).quantize(Q4),
                    "source_id": sid,
                }
            )
    session.execute(insert(IndexDaily), indices)
    counts["index_daily"] = len(indices)

    # --- companies, corporate actions, prices -------------------------------------
    actions_by_ticker: dict[str, list[Action]] = {
        "DMPHARMA": [
            Action(_on_or_after(days, date(2024, 12, 8)), CorporateActionType.BONUS, D("0.10"))
        ],
        "DMTECH": [Action(_on_or_after(days, date(2025, 3, 9)), CorporateActionType.SPLIT, D("2"))],
        "DMFOOD": [
            Action(_on_or_after(days, date(2023, 11, 12)), CorporateActionType.BONUS, D("0.05"))
        ],
        "DMCEMENT": [
            Action(
                _on_or_after(days, date(2025, 11, 16)),
                CorporateActionType.CASH_DIVIDEND,
                None,
                D("2.50"),
            )
        ],
        "DMTEL": [
            Action(
                _on_or_after(days, date(2026, 4, 12)),
                CorporateActionType.CASH_DIVIDEND,
                None,
                D("12.00"),
            )
        ],
    }
    shariah_version = get_config("shariah").version
    prices: list[dict[str, object]] = []
    average_cap: dict[str, float] = {}

    for co in COMPANIES:
        session.add(
            Company(
                ticker=co.ticker,
                name=co.name,
                sector=co.sector,
                listing_date=date(2012, 1, 1) + timedelta(days=rng.randrange(2500)),
                source_id=sid,
            )
        )
    session.flush()
    for co in COMPANIES:
        session.add(
            BusinessClassification(
                ticker=co.ticker,
                stage1_pass=co.excluded_activity is None,
                activity=co.excluded_activity,
                reason=co.stage1_reason,
                method_version=shariah_version,
            )
        )
    session.flush()

    for co in COMPANIES:
        actions = actions_by_ticker.get(co.ticker, [])
        factor_on = {
            a.ex_date: a
            for a in actions
            if a.type in (CorporateActionType.BONUS, CorporateActionType.SPLIT)
        }
        for action in actions:
            session.add(
                CorporateAction(
                    ticker=co.ticker,
                    ex_date=action.ex_date,
                    type=action.type.value,
                    ratio=action.ratio,
                    amount=action.amount,
                    source_id=sid,
                )
            )

        close = co.base_price
        raw: list[tuple[date, Decimal]] = []
        rows: list[dict[str, object]] = []
        for i, day in enumerate(days):
            move = co.market_beta * market[i] + rng.gauss(0, 0.011) + co.shock_mult * shock[i]
            move += co.rate_beta * yield_change.get(day, 0.0) / 100
            # The DSE limits a normal day's move to about 10%.
            move = max(-0.092, min(0.092, move))
            close *= exp(move)
            if day in factor_on:
                action = factor_on[day]
                assert action.ratio is not None
                close /= (
                    float(action.ratio)
                    if action.type is CorporateActionType.SPLIT
                    else 1 + float(action.ratio)
                )
            close_d = D(str(close)).quantize(D("0.1"))
            spread = abs(rng.gauss(0, 0.008)) + 0.002
            raw.append((day, close_d))
            rows.append(
                {
                    "ticker": co.ticker,
                    "date": day,
                    "open": (close_d * D(str(1 - spread / 2))).quantize(D("0.1")),
                    "high": (close_d * D(str(1 + spread))).quantize(D("0.1")),
                    "low": (close_d * D(str(1 - spread))).quantize(D("0.1")),
                    "close": close_d,
                    "volume": int(rng.lognormvariate(12.2, 0.7)),
                    "source_id": sid,
                }
            )
        for row, (_, adjusted) in zip(rows, back_adjust(raw, actions), strict=True):
            row["adj_close"] = adjusted
        prices.extend(rows)
        last_year = [float(c) for d, c in raw if d >= date(2025, 7, 1)]
        average_cap[co.ticker] = sum(last_year) / len(last_year) * co.shares

    for start in range(0, len(prices), 2000):
        session.execute(insert(PriceDaily), prices[start : start + 2000])
    counts["price_daily"] = len(prices)
    counts["company"] = len(COMPANIES)

    # --- financial statements (annual, year ending 30 June) -----------------------
    n_fin = 0
    for co in COMPANIES:
        if co.excluded_activity is not None:
            continue  # Stage 1 fails; ratios are not needed.
        cap = average_cap[co.ticker]
        revenue = cap * 0.55
        for year, scale in ((2024, 0.86), (2025, 0.93), (2026, 1.0)):

            def amount(pct: float | None, base: float, scale: float = scale) -> Decimal | None:
                return None if pct is None else D(str(base * pct / 100 * scale)).quantize(Q2)

            session.add(
                Financials(
                    ticker=co.ticker,
                    period_end=date(year, 6, 30),
                    period_type="ANNUAL",
                    total_debt_interest_bearing=amount(co.debt_pct, cap),
                    cash_and_interest_securities=amount(co.cash_pct, cap),
                    receivables=amount(co.recv_pct, cap),
                    total_revenue=D(str(revenue * scale)).quantize(Q2),
                    non_permissible_income=amount(co.npi_pct, revenue),
                    zakatable_assets=D(str(cap * 0.38 * scale)).quantize(Q2),
                    shares_outstanding=co.shares,
                    source_id=sid,
                    source_page=rng.randrange(40, 120),
                    reviewed_at=now,
                )
            )
            n_fin += 1
    counts["financials"] = n_fin

    # --- events -------------------------------------------------------------------
    for t0, kind, slug, title_en, title_bn, desc_en, desc_bn, published in EVENTS:
        session.add(
            Event(
                slug=slug,
                type=kind,
                t0=t0,
                title_en=title_en,
                title_bn=title_bn,
                description_en=desc_en,
                description_bn=desc_bn,
                source_links=[],
                published=published,
            )
        )
    counts["event"] = len(EVENTS)

    # --- sukuk, Islamic bank products, bank flags ---------------------------------
    session.add_all(
        [
            # From the PRD's example (F26). Issue and maturity dates must be confirmed.
            SukukIssue(
                code="IRIDPNFL",
                name="Bangladesh Government Investment Sukuk (IRIDPNFL)",
                issuer="Government of Bangladesh",
                structure="IJARAH",
                is_government=True,
                rate_pct=D("9.60"),
                payment_frequency="HALF_YEARLY",
                min_investment=D("10000"),
                source_id=sid,
            ),
            SukukIssue(
                code="DEMO-GOVT-SUKUK-2026",
                name="Demo Government Sukuk 2026 (upcoming auction)",
                issuer="Government of Bangladesh",
                structure="IJARAH",
                is_government=True,
                rate_pct=D("9.10"),
                payment_frequency="HALF_YEARLY",
                min_investment=D("10000"),
                auction_date=date(2026, 12, 10),
                individual_quota_pct=D("10"),
                source_id=sid,
            ),
            SukukIssue(
                code="DMSUKUK1",
                name="Demo Green Sukuk Al Istisna'a",
                issuer="Demo Power Generation Ltd.",
                structure="ISTISNA",
                is_government=False,
                ticker="DMSUKUK1",
                issue_date=date(2023, 12, 20),
                maturity_date=date(2029, 12, 20),
                rate_pct=D("9.00"),
                payment_frequency="HALF_YEARLY",
                min_investment=D("5000"),
                source_id=sid,
            ),
        ]
    )
    as_of = date(2026, 11, 1)
    products = [
        (
            "Demo Islami Bank PLC",
            "MUDARABA_TERM_DEPOSIT",
            "Mudaraba Term Deposit",
            3,
            "8.50",
            "25000",
        ),
        (
            "Demo Islami Bank PLC",
            "MUDARABA_TERM_DEPOSIT",
            "Mudaraba Term Deposit",
            12,
            "9.25",
            "25000",
        ),
        (
            "Demo Islami Bank PLC",
            "MUDARABA_TERM_DEPOSIT",
            "Mudaraba Term Deposit",
            36,
            "9.75",
            "25000",
        ),
        (
            "Demo Islami Bank PLC",
            "MUDARABA_SAVINGS",
            "Mudaraba Savings Account",
            None,
            "4.00",
            "500",
        ),
        (
            "Demo Islami Bank PLC",
            "MONTHLY_PROFIT_SCHEME",
            "Mudaraba Monthly Profit Scheme",
            36,
            "9.40",
            "100000",
        ),
        (
            "Demo Islami Bank PLC",
            "MUDARABA_SAVINGS_SCHEME",
            "Mudaraba Monthly Savings Scheme",
            60,
            "9.60",
            "1000",
        ),
        ("Demo Islami Bank PLC", "HAJJ_SAVINGS", "Mudaraba Hajj Savings", 60, "9.00", "1000"),
        (
            "Demo Shariah Bank PLC",
            "MUDARABA_TERM_DEPOSIT",
            "Mudaraba Term Deposit",
            12,
            "10.25",
            "10000",
        ),
        ("Demo Shariah Bank PLC", "CASH_WAQF", "Mudaraba Cash Waqf Deposit", None, "9.00", "1000"),
        (
            "Demo Shariah Bank PLC",
            "MUDARABA_PERPETUAL_BOND",
            "Mudaraba Perpetual Bond",
            None,
            "10.00",
            "5000",
        ),
    ]
    for bank, kind, name, tenor, rate, minimum in products:
        session.add(
            IslamicProduct(
                bank=bank,
                product_type=kind,
                name=name,
                tenor_months=tenor,
                expected_rate_pct=D(rate),
                min_amount=D(minimum),
                as_of=as_of,
                source_id=sid,
            )
        )
    counts["islamic_product"] = len(products)
    session.add(
        BankFlag(
            bank="Demo Shariah Bank PLC",
            status="RESTRICTED",
            note_en="Demo notice: this fictional bank is under restructuring and limits large withdrawals.",
            note_bn="নমুনা নোটিশ: এই কাল্পনিক ব্যাংকটি পুনর্গঠনের আওতায় আছে এবং বড় অঙ্কের টাকা তোলায় সীমা রয়েছে।",
            source_links=[],
        )
    )
    session.flush()
    return counts
