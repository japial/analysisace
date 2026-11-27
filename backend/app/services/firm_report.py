"""White-label weekly report (FR9.1, D30): the published weekly macro note as a PDF carrying
the firm's logo, name and disclaimer, as well as analysisACE's own disclaimer.

Nothing is recalculated: the PDF repeats the published note and its figures, with the
sources each figure came from.
"""

import datetime as dt
import io
from decimal import Decimal

from app.core.security import utcnow
from app.models import Firm, MacroNote
from app.services.macro_notes import LABELS
from app.services.statements import MUTED, NAVY, Statement, time_text
from app.services.text_format import date_text

_TEXT = {
    "en": {
        "prepared_for": "Prepared for clients of {firm}",
        "week": "Week of {date}",
        "figures": "The week in figures",
        "indicator": "Indicator",
        "value": "Value",
        "previous": "Previous",
        "change": "Change",
        "as_of": "As of",
        "source": "Source",
        "firm_disclaimer": "From {firm}",
        "made_with": "Analysis by analysisACE. Published {time}.",
    },
    "bn": {
        "prepared_for": "{firm}-এর গ্রাহকদের জন্য প্রস্তুত",
        "week": "{date} থেকে শুরু সপ্তাহ",
        "figures": "সংখ্যায় এই সপ্তাহ",
        "indicator": "সূচক",
        "value": "মান",
        "previous": "আগের",
        "change": "পরিবর্তন",
        "as_of": "তারিখ",
        "source": "উৎস",
        "firm_disclaimer": "{firm}-এর পক্ষ থেকে",
        "made_with": "বিশ্লেষণ: analysisACE। প্রকাশ {time}।",
    },
}

_BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


def _num(value: str | None, locale: str) -> str:
    if value is None:
        return "—"
    text = f"{Decimal(value):,.2f}"
    return text.translate(_BN_DIGITS) if locale == "bn" else text


class WhiteLabelReport(Statement):
    """The statement page with the firm's logo and name on top and both disclaimers below."""

    def __init__(self, locale: str, title: str, firm: Firm, logo: bytes | None) -> None:
        self.firm = firm
        self.logo = logo
        super().__init__(locale, title)
        self.set_creator(f"{firm.name} with analysisACE")
        # Room for the firm's disclaimer above the standard footer.
        self.set_auto_page_break(True, margin=30)

    def header(self) -> None:
        top = self.get_y()
        x = self.l_margin
        if self.logo:
            self.image(io.BytesIO(self.logo), x=x, y=top, h=10, keep_aspect_ratio=True)
            x += 42
        self.set_xy(x, top + 1)
        self.set_font(self.main_font, "B", 12)
        self.set_text_color(*NAVY)
        self.cell(0, 6, self.firm.name, new_x="LMARGIN", new_y="NEXT")
        self.set_xy(x, self.get_y())
        self.set_font(self.main_font, "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 4, _TEXT[self.locale]["prepared_for"].format(firm=self.firm.name))
        self.set_y(top + 13)
        self.set_draw_color(*NAVY)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(5)

    def footer(self) -> None:
        if self.firm.report_disclaimer:
            self.set_y(-28)
            self.set_font(self.main_font, "", 7.5)
            self.set_text_color(*MUTED)
            self.multi_cell(
                0,
                3.6,
                f"{_TEXT[self.locale]['firm_disclaimer'].format(firm=self.firm.name)}: "
                f"{self.firm.report_disclaimer}",
                new_x="LMARGIN",
                new_y="NEXT",
            )
        super().footer()


def weekly_report_pdf(firm: Firm, logo: bytes | None, note: MacroNote, locale: str) -> bytes:
    text = _TEXT[locale]
    pdf = WhiteLabelReport(locale, note.title, firm, logo)
    pdf.add_page()
    pdf.title_block(note.title, text["week"].format(date=date_text(note.week_start, locale)))

    for line in note.body.splitlines():
        stripped = line.strip()
        if not stripped:
            pdf.ln(2)
        elif stripped.startswith("## "):
            pdf.heading(stripped[3:])
        else:
            pdf.set_font(pdf.main_font, "", 10)
            pdf.set_text_color(*NAVY)
            bullet = stripped.startswith("- ")
            content = f"•  {stripped[2:]}" if bullet else stripped
            pdf.multi_cell(0, 5.5, content.replace("**", ""), new_x="LMARGIN", new_y="NEXT")

    pdf.heading(text["figures"])
    rows = []
    for fig in note.figures:
        label = LABELS.get(fig.get("code", ""), {}).get(locale, fig.get("code", ""))
        as_of = fig.get("as_of")
        rows.append(
            (
                label,
                _num(fig.get("value"), locale),
                _num(fig.get("previous"), locale),
                _num(fig.get("change"), locale),
                date_text(dt.date.fromisoformat(as_of), locale) if as_of else "—",
                fig.get("source_name") or "—",
            )
        )
    pdf.grid(
        (
            text["indicator"],
            text["value"],
            text["previous"],
            text["change"],
            text["as_of"],
            text["source"],
        ),
        rows,
        widths=(30, 15, 15, 15, 17, 28),
        align=("LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "LEFT"),
    )
    pdf.ln(2)
    pdf.set_font(pdf.main_font, "", 8.5)
    pdf.set_text_color(*MUTED)
    published = note.published_at or utcnow()
    pdf.multi_cell(
        0,
        4.5,
        text["made_with"].format(time=time_text(published, locale)),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    return pdf.to_bytes()
