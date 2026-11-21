"""PDF statements for Zakat and tax snapshots (F13), in English or Bangla.

A PDF repeats the stored snapshot line by line; nothing is worked out again here. Every PDF
carries the disclaimer on each page, the time the snapshot was computed and the sources of
the market prices behind it (PRD section 0).

Bangla needs text shaping for joined letters, so fpdf2 runs with HarfBuzz shaping and the
Noto fonts in app/assets/fonts (SIL Open Font License, see OFL.txt there).
"""

import datetime as dt
import uuid
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

from fpdf import FPDF
from fpdf.enums import TableCellFillMode
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.models import HouseholdMember, Source, TaxSnapshot, ZakatSnapshot
from app.services.alerts import taka
from app.services.statement_labels import ENUM_LABELS
from app.services.valuation import DHAKA, load_portfolio

FONTS = Path(__file__).resolve().parents[1] / "assets" / "fonts"
_BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
MONTHS = {
    "en": [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ],
    "bn": [
        "জানুয়ারি",
        "ফেব্রুয়ারি",
        "মার্চ",
        "এপ্রিল",
        "মে",
        "জুন",
        "জুলাই",
        "আগস্ট",
        "সেপ্টেম্বর",
        "অক্টোবর",
        "নভেম্বর",
        "ডিসেম্বর",
    ],
}

TEXT: dict[str, dict[str, str]] = {
    "en": {
        "disclaimer": "Historical analysis for education only. Not investment advice.",
        "page": "Page {n} of {total}",
        "zakat_title": "Zakat statement",
        "zakat_for": "{name}, Zakat date {date}",
        "zakat_provisional": "The Zakat rules used here are provisional until a Shariah advisor approves them. Check the result with a scholar you trust.",
        "summary": "Summary",
        "zakat_due": "Zakat due",
        "net_zakatable": "Net zakatable wealth",
        "nisab": "Nisab",
        "nisab_from": "{basis} at {price} a gram",
        "total_zakatable": "Total zakatable",
        "deductions": "Debts deducted",
        "shares_method": "Shares counted at",
        "rules_version": "Rules version",
        "lines": "Line by line",
        "item": "Item",
        "treatment": "Treatment",
        "value": "Value",
        "share": "Share",
        "counts": "Counts",
        "deductions_intro": "Debts due within a year, at this person's share.",
        "debt": "Debt",
        "amount": "Amount",
        "computed": "Computed at {time}",
        "generated": "This PDF was made at {time}",
        "sources": "Market prices from: {names}",
        "no_sources": "No market prices were used; values are as recorded in the household.",
        "tax_title": "Tax statement {year}",
        "tax_for": "{name}, {start} to {end}",
        "tax_note": "Figures to help fill in a return; analysisACE does not file tax returns. Check figures and rebate rules with a tax adviser before filing.",
        "as_of": "Values as of {date}",
        "assets_cost": "Assets at cost",
        "assets_value": "Assets at today's value",
        "liabilities": "Debts",
        "net_wealth": "Net wealth at cost",
        "income_total": "Income in the year",
        "tax_paid": "Tax deducted at source in the year",
        "rebate_total": "Purchases that may qualify for rebate",
        "assets": "Assets",
        "category": "Type",
        "cost": "Cost",
        "outstanding": "Outstanding",
        "income": "Income",
        "tax_deducted": "Tax deducted at source",
        "rebate": "Purchases that may qualify for rebate",
        "none": "None recorded.",
    },
    "bn": {
        "disclaimer": "ঐতিহাসিক বিশ্লেষণ শুধু শিক্ষার উদ্দেশ্যে। এটি বিনিয়োগ পরামর্শ নয়।",
        # The total is filled in by fpdf2 after layout, in Latin digits, so it is left out.
        "page": "পৃষ্ঠা {n}",
        "zakat_title": "যাকাত বিবরণী",
        "zakat_for": "{name}, যাকাতের তারিখ {date}",
        "zakat_provisional": "শরিয়াহ উপদেষ্টার অনুমোদন না পাওয়া পর্যন্ত এখানে ব্যবহৃত যাকাতের নিয়মগুলো অস্থায়ী। আপনার আস্থাভাজন আলেমের সাথে ফলাফল মিলিয়ে নিন।",
        "summary": "সারসংক্ষেপ",
        "zakat_due": "প্রদেয় যাকাত",
        "net_zakatable": "নিট যাকাতযোগ্য সম্পদ",
        "nisab": "নিসাব",
        "nisab_from": "{basis}, প্রতি গ্রাম {price}",
        "total_zakatable": "মোট যাকাতযোগ্য",
        "deductions": "বাদ দেওয়া ঋণ",
        "shares_method": "শেয়ার গণনার পদ্ধতি",
        "rules_version": "নিয়মের সংস্করণ",
        "lines": "প্রতিটি লাইন",
        "item": "বিষয়",
        "treatment": "গণনার ধরন",
        "value": "মূল্য",
        "share": "অংশ",
        "counts": "গণ্য",
        "deductions_intro": "এক বছরের মধ্যে পরিশোধযোগ্য ঋণ, এই ব্যক্তির অংশ অনুযায়ী।",
        "debt": "ঋণ",
        "amount": "পরিমাণ",
        "computed": "হিসাবের সময় {time}",
        "generated": "এই PDF তৈরির সময় {time}",
        "sources": "বাজারদরের উৎস: {names}",
        "no_sources": "কোনো বাজারদর ব্যবহার হয়নি; মূল্য পরিবারের রেকর্ড অনুযায়ী।",
        "tax_title": "কর বিবরণী {year}",
        "tax_for": "{name}, {start} থেকে {end}",
        "tax_note": "রিটার্ন পূরণে সাহায্যের জন্য সংখ্যা; analysisACE কর রিটার্ন জমা দেয় না। জমার আগে কর পরামর্শকের সাথে সংখ্যা ও রেয়াতের নিয়ম মিলিয়ে নিন।",
        "as_of": "{date} তারিখের মূল্য",
        "assets_cost": "ক্রয়মূল্যে সম্পদ",
        "assets_value": "আজকের মূল্যে সম্পদ",
        "liabilities": "ঋণ",
        "net_wealth": "ক্রয়মূল্যে নিট সম্পদ",
        "income_total": "বছরের আয়",
        "tax_paid": "বছরে উৎসে কাটা কর",
        "rebate_total": "রেয়াতযোগ্য হতে পারে এমন কেনাকাটা",
        "assets": "সম্পদ",
        "category": "ধরন",
        "cost": "ক্রয়মূল্য",
        "outstanding": "বাকি",
        "income": "আয়",
        "tax_deducted": "উৎসে কাটা কর",
        "rebate": "রেয়াতযোগ্য হতে পারে এমন কেনাকাটা",
        "none": "কিছু রেকর্ড করা নেই।",
    },
}

NAVY = (11, 31, 58)
MUTED = (100, 116, 139)
LINE = (226, 232, 240)
NOTE_BG = (254, 249, 231)
ROW_BG = (248, 250, 252)


# --- formatting -----------------------------------------------------------------------


def _digits(text: str, locale: str) -> str:
    return text.translate(_BN_DIGITS) if locale == "bn" else text


def money(value: Decimal | str | None, locale: str) -> str:
    if value is None or value == "":
        return "—"
    return taka(Decimal(str(value)), locale)


def pct(value: Decimal | str | None, locale: str, places: int = 0) -> str:
    if value is None or value == "":
        return "—"
    return _digits(f"{Decimal(str(value)):.{places}f}%", locale)


def date_text(day: dt.date | str, locale: str) -> str:
    if isinstance(day, str):
        day = dt.date.fromisoformat(day)
    return _digits(f"{day.day} {MONTHS[locale][day.month - 1]} {day.year}", locale)


def time_text(moment: dt.datetime, locale: str) -> str:
    local = (moment if moment.tzinfo else moment.replace(tzinfo=dt.UTC)).astimezone(DHAKA)
    return f"{date_text(local.date(), locale)}, {_digits(local.strftime('%H:%M'), locale)}"


def label(group: str, value: str | None, locale: str) -> str:
    if not value:
        return "—"
    return ENUM_LABELS[locale].get(group, {}).get(value, value)


# --- document -------------------------------------------------------------------------


class Statement(FPDF):
    """A4 page with the brand line on top and the disclaimer and page number at the bottom."""

    def __init__(self, locale: str, title: str) -> None:
        super().__init__(format="A4")
        self.locale = locale
        self.doc_title = title
        self.text_ = TEXT[locale]
        for family, stem in (("NotoSans", "NotoSans"), ("NotoBengali", "NotoSansBengali")):
            self.add_font(family, "", FONTS / f"{stem}-Regular.ttf")
            self.add_font(family, "B", FONTS / f"{stem}-Bold.ttf")
        self.main_font = "NotoBengali" if locale == "bn" else "NotoSans"
        # Latin names inside Bangla text, and the other way round.
        self.set_fallback_fonts(["NotoSans" if locale == "bn" else "NotoBengali"])
        self.set_text_shaping(True)
        self.set_margins(16, 18, 16)
        self.set_auto_page_break(True, margin=22)
        self.set_title(title)
        self.set_creator("analysisACE")
        self.alias_nb_pages()

    def header(self) -> None:
        self.set_font(self.main_font, "B", 11)
        self.set_text_color(*NAVY)
        self.cell(0, 6, "analysisACE", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*LINE)
        self.line(self.l_margin, self.get_y() + 1, self.w - self.r_margin, self.get_y() + 1)
        self.ln(5)

    def footer(self) -> None:
        self.set_y(-16)
        self.set_font(self.main_font, "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 4, self.text_["disclaimer"], new_x="LMARGIN", new_y="NEXT")
        number = _digits(str(self.page_no()), self.locale)
        self.cell(0, 4, self.text_["page"].format(n=number, total="{nb}"))

    # --- building blocks ---------------------------------------------------------------

    def title_block(self, title: str, subtitle: str) -> None:
        self.set_text_color(*NAVY)
        self.set_font(self.main_font, "B", 18)
        self.multi_cell(0, 9, title, new_x="LMARGIN", new_y="NEXT")
        self.set_font(self.main_font, "", 11)
        self.set_text_color(*MUTED)
        self.multi_cell(0, 6, subtitle, new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

    def note(self, text: str) -> None:
        self.set_fill_color(*NOTE_BG)
        self.set_text_color(*NAVY)
        self.set_font(self.main_font, "", 9)
        self.multi_cell(0, 5, text, fill=True, padding=3, new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

    def heading(self, text: str, intro: str | None = None) -> None:
        self.ln(2)
        self.set_text_color(*NAVY)
        self.set_font(self.main_font, "B", 12)
        self.cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")
        if intro:
            self.set_font(self.main_font, "", 9)
            self.set_text_color(*MUTED)
            self.multi_cell(0, 5, intro, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def _table_style(self) -> None:
        self.set_fill_color(*ROW_BG)
        self.set_draw_color(*LINE)
        self.set_line_width(0.2)

    def facts(self, rows: Sequence[tuple[str, str]]) -> None:
        """Two-column label and value pairs."""
        self._table_style()
        self.set_font(self.main_font, "", 10)
        self.set_text_color(*NAVY)
        with self.table(
            col_widths=(45, 55),
            text_align=("LEFT", "RIGHT"),
            first_row_as_headings=False,
            borders_layout="HORIZONTAL_LINES",
            line_height=6.5,
            padding=1.5,
        ) as table:
            for name, value in rows:
                row = table.row()
                row.cell(name)
                row.cell(value)
        self.ln(2)

    def grid(
        self,
        headings: Sequence[str],
        rows: Sequence[Sequence[str]],
        widths: Sequence[int],
        align: Sequence[str],
        total: Sequence[str] | None = None,
    ) -> None:
        if not rows:
            self.set_font(self.main_font, "", 9)
            self.set_text_color(*MUTED)
            self.cell(0, 6, self.text_["none"], new_x="LMARGIN", new_y="NEXT")
            self.ln(2)
            return
        self._table_style()
        self.set_text_color(*NAVY)
        self.set_font(self.main_font, "", 9)
        with self.table(
            col_widths=tuple(widths),
            text_align=tuple(align),
            borders_layout="HORIZONTAL_LINES",
            cell_fill_color=ROW_BG,
            cell_fill_mode=TableCellFillMode.ROWS,
            line_height=5.5,
            padding=1.5,
        ) as table:
            head = table.row()
            for text in headings:
                head.cell(text)
            for values in rows:
                row = table.row()
                for value in values:
                    row.cell(value)
            if total is not None:
                row = table.row()
                for value in total:
                    row.cell(value)
        self.ln(2)

    def trace(self, computed_at: dt.datetime, sources: Sequence[Source]) -> None:
        """When the numbers were worked out and where the market prices came from."""
        self.ln(2)
        self.set_font(self.main_font, "", 8.5)
        self.set_text_color(*MUTED)
        lines = [self.text_["computed"].format(time=time_text(computed_at, self.locale))]
        names = sorted({s.name for s in sources})
        lines.append(
            self.text_["sources"].format(names="; ".join(names))
            if names
            else self.text_["no_sources"]
        )
        lines.append(self.text_["generated"].format(time=time_text(utcnow(), self.locale)))
        for text in lines:
            self.multi_cell(0, 4.5, text, new_x="LMARGIN", new_y="NEXT")

    def to_bytes(self) -> bytes:
        return bytes(self.output())


def _sources(db: Session, source_ids: set[uuid.UUID]) -> list[Source]:
    if not source_ids:
        return []
    return list(db.scalars(select(Source).where(Source.id.in_(source_ids))))


# --- Zakat ----------------------------------------------------------------------------


def zakat_pdf(
    db: Session,
    household_id: uuid.UUID,
    snapshot: ZakatSnapshot,
    member: HouseholdMember,
    locale: str,
) -> bytes:
    """FR13.1 to FR13.4 as a PDF. Market sources are the prices valid on the Zakat date."""
    t = TEXT[locale]
    doc = Statement(locale, t["zakat_title"])
    doc.add_page()
    doc.title_block(
        t["zakat_title"],
        t["zakat_for"].format(name=member.display_name, date=date_text(snapshot.date, locale)),
    )
    doc.note(t["disclaimer"])
    doc.note(t["zakat_provisional"])

    doc.heading(t["summary"])
    doc.facts(
        [
            (t["zakat_due"], money(snapshot.zakat_due, locale)),
            (t["net_zakatable"], money(snapshot.net_zakatable, locale)),
            (t["total_zakatable"], money(snapshot.total_zakatable, locale)),
            (t["deductions"], money(snapshot.total_deductions, locale)),
            (
                t["nisab"],
                f"{money(snapshot.nisab_value, locale)} ("
                + t["nisab_from"].format(
                    basis=label("nisab", snapshot.nisab_basis, locale),
                    price=money(snapshot.price_per_gram, locale),
                )
                + ")",
            ),
            (t["shares_method"], label("sharesMethod", snapshot.shares_method, locale)),
            (t["rules_version"], snapshot.config_version),
        ]
    )

    assets = [i for i in snapshot.items if i.get("asset_kind") != "LIABILITY"]
    debts = [i for i in snapshot.items if i.get("asset_kind") == "LIABILITY"]
    doc.heading(t["lines"])
    rows = []
    for item in assets:
        name = str(item.get("label", ""))
        flags = [label("zakatFlag", f, locale) for f in item.get("flags") or []]
        if flags:
            name += " (" + ", ".join(flags) + ")"
        rows.append(
            [
                name,
                label("treatment", item.get("treatment"), locale),
                money(item.get("value"), locale),
                pct(item.get("owner_pct"), locale),
                money(item.get("zakatable"), locale),
            ]
        )
    doc.grid(
        [t["item"], t["treatment"], t["value"], t["share"], t["counts"]],
        rows,
        widths=(38, 22, 16, 9, 16),
        align=("LEFT", "LEFT", "RIGHT", "RIGHT", "RIGHT"),
        total=[t["total_zakatable"], "", "", "", money(snapshot.total_zakatable, locale)],
    )
    if debts:
        doc.heading(t["deductions"], t["deductions_intro"])
        doc.grid(
            [t["debt"], t["share"], t["amount"]],
            [
                [
                    str(i.get("label", "")),
                    pct(i.get("owner_pct"), locale),
                    money(i.get("zakatable"), locale),
                ]
                for i in debts
            ],
            widths=(60, 15, 25),
            align=("LEFT", "RIGHT", "RIGHT"),
        )

    portfolio = load_portfolio(db, household_id, snapshot.date, active_only=False)
    doc.trace(snapshot.created_at, _sources(db, portfolio.source_ids))
    return doc.to_bytes()


# --- tax ------------------------------------------------------------------------------


def tax_pdf(
    db: Session,
    household_id: uuid.UUID,
    snapshot: TaxSnapshot,
    member: HouseholdMember,
    locale: str,
) -> bytes:
    """FR13.5 and FR13.6 as a PDF: wealth statement, income, tax deducted, rebate items."""
    t = TEXT[locale]
    items: dict[str, Any] = snapshot.items
    year = _digits(snapshot.tax_year, locale)
    doc = Statement(locale, t["tax_title"].format(year=year))
    doc.add_page()
    period = items.get("period", {})
    doc.title_block(
        t["tax_title"].format(year=year),
        t["tax_for"].format(
            name=member.display_name,
            start=date_text(period.get("start", snapshot.as_of.isoformat()), locale),
            end=date_text(period.get("end", snapshot.as_of.isoformat()), locale),
        )
        + " · "
        + t["as_of"].format(date=date_text(snapshot.as_of, locale)),
    )
    doc.note(t["disclaimer"])
    doc.note(t["tax_note"])

    totals = items.get("totals", {})
    tds = items.get("tax_deducted", {})
    doc.heading(t["summary"])
    doc.facts(
        [
            (t["assets_cost"], money(totals.get("assets_cost"), locale)),
            (t["assets_value"], money(totals.get("assets_value"), locale)),
            (t["liabilities"], money(totals.get("liabilities"), locale)),
            (t["net_wealth"], money(totals.get("net_wealth_cost"), locale)),
            (t["income_total"], money(totals.get("income"), locale)),
            (t["tax_paid"], money(tds.get("in_year"), locale)),
            (t["rebate_total"], money(items.get("rebate_eligible_total"), locale)),
        ]
    )

    doc.heading(t["assets"])
    doc.grid(
        [t["item"], t["category"], t["share"], t["cost"], t["value"]],
        [
            [
                str(a.get("label", "")),
                label("assetClass", a.get("category"), locale),
                pct(a.get("owner_pct"), locale),
                money(a.get("cost"), locale),
                money(a.get("value"), locale),
            ]
            for a in items.get("assets", [])
        ],
        widths=(36, 24, 9, 16, 16),
        align=("LEFT", "LEFT", "RIGHT", "RIGHT", "RIGHT"),
        total=[
            "",
            "",
            "",
            money(totals.get("assets_cost"), locale),
            money(totals.get("assets_value"), locale),
        ],
    )
    doc.heading(t["liabilities"])
    doc.grid(
        [t["debt"], t["category"], t["share"], t["outstanding"]],
        [
            [
                str(x.get("label", "")),
                label("liabilityType", x.get("type"), locale),
                pct(x.get("owner_pct"), locale),
                money(x.get("outstanding"), locale),
            ]
            for x in items.get("liabilities", [])
        ],
        widths=(40, 25, 10, 25),
        align=("LEFT", "LEFT", "RIGHT", "RIGHT"),
    )
    doc.heading(t["income"])
    doc.grid(
        [t["item"], t["amount"]],
        [
            [label("incomeKind", k, locale), money(v, locale)]
            for k, v in items.get("income", {}).items()
        ],
        widths=(70, 30),
        align=("LEFT", "RIGHT"),
        total=[t["income_total"], money(totals.get("income"), locale)],
    )
    doc.heading(t["tax_deducted"])
    doc.grid(
        [t["item"], t["amount"]],
        [[str(x.get("label", "")), money(x.get("amount"), locale)] for x in tds.get("lines", [])],
        widths=(70, 30),
        align=("LEFT", "RIGHT"),
    )
    doc.heading(t["rebate"])
    doc.grid(
        [t["item"], t["category"], t["amount"]],
        [
            [
                str(r.get("label", "")),
                label("instrument", r.get("type"), locale),
                money(r.get("amount"), locale),
            ]
            for r in items.get("rebate_eligible", [])
        ],
        widths=(45, 30, 25),
        align=("LEFT", "LEFT", "RIGHT"),
    )

    portfolio = load_portfolio(db, household_id, snapshot.as_of, active_only=False)
    doc.trace(snapshot.created_at, _sources(db, portfolio.source_ids))
    return doc.to_bytes()
