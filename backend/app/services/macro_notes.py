"""Weekly macro note (F4).

`generate_draft` builds a Bangla and an English draft for a DSE week from stored series only
(FR4 AC): each figure carries the source it came from, and a series with no stored value is
left out rather than guessed. An editor changes the text and publishes (FR4.2). A published
note is never overwritten by the job.
"""

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.app_config import get_config
from app.core.security import utcnow
from app.core.trading_calendar import TradingCalendar
from app.models import IndexDaily, MacroNote, MacroSeries, Source, User
from app.models.enums import NoteStatus
from app.services.auth import AuthError, audit

LOCALES = ("en", "bn")
_BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")

LABELS: dict[str, dict[str, str]] = {
    "TBILL_91D": {"en": "91-day T-bill yield", "bn": "৯১ দিনের ট্রেজারি বিলের সুদহার"},
    "TBILL_182D": {"en": "182-day T-bill yield", "bn": "১৮২ দিনের ট্রেজারি বিলের সুদহার"},
    "TBILL_364D": {"en": "364-day T-bill yield", "bn": "৩৬৪ দিনের ট্রেজারি বিলের সুদহার"},
    "POLICY_RATE": {"en": "Policy rate", "bn": "নীতি সুদহার"},
    "CPI_YOY": {"en": "CPI inflation (year on year)", "bn": "মূল্যস্ফীতি (বছরওয়ারি)"},
    "BDT_USD": {"en": "Taka per US dollar", "bn": "ডলারপ্রতি টাকা"},
    "REMITTANCE_USD_MN": {
        "en": "Remittance (USD million, month)",
        "bn": "রেমিট্যান্স (মাসিক, মিলিয়ন ডলার)",
    },
    "BRENT_USD": {"en": "Brent crude (USD a barrel)", "bn": "ব্রেন্ট অপরিশোধিত তেল (ব্যারেলপ্রতি ডলার)"},
    "DSEX": {"en": "DSEX", "bn": "ডিএসইএক্স"},
    "DSES": {"en": "DSES", "bn": "ডিএসইএস"},
}
TEXT = {
    "en": {
        "title": "Macro note: week of {week}",
        "intro": "Figures for the DSE week starting {week}, from stored data. Each figure shows its source and date.",
        "changed": "What changed",
        "nothing": "No figure moved beyond the usual range this week.",
        "up": "{label} rose from {previous} to {value}.",
        "down": "{label} fell from {previous} to {value}.",
        "idx_up": "{label} rose {change}% to {value}.",
        "idx_down": "{label} fell {change}% to {value}.",
        "outro": "Historical analysis for education only. Not investment advice.",
    },
    "bn": {
        "title": "সামষ্টিক অর্থনীতি নোট: {week} থেকে শুরু সপ্তাহ",
        "intro": "{week} থেকে শুরু ডিএসই সপ্তাহের সংরক্ষিত তথ্য। প্রতিটি সংখ্যার পাশে উৎস ও তারিখ দেওয়া আছে।",
        "changed": "কী বদলেছে",
        "nothing": "এই সপ্তাহে কোনো সংখ্যা স্বাভাবিক সীমার বাইরে নড়েনি।",
        "up": "{label} {previous} থেকে বেড়ে {value} হয়েছে।",
        "down": "{label} {previous} থেকে কমে {value} হয়েছে।",
        "idx_up": "{label} {change}% বেড়ে {value} হয়েছে।",
        "idx_down": "{label} {change}% কমে {value} হয়েছে।",
        "outro": "শুধুমাত্র শিক্ষামূলক ঐতিহাসিক বিশ্লেষণ। এটি বিনিয়োগ পরামর্শ নয়।",
    },
}


def _fmt(value: Decimal, locale: str) -> str:
    text = f"{value:,.2f}"
    return text.translate(_BN_DIGITS) if locale == "bn" else text


def _point(
    db: Session, code: str, kind: str, on_or_before: dt.date
) -> tuple[Any, Decimal, Any] | None:
    if kind == "index":
        row: Any = db.scalar(
            select(IndexDaily)
            .where(IndexDaily.index_code == code, IndexDaily.date <= on_or_before)
            .order_by(IndexDaily.date.desc())
            .limit(1)
        )
        return None if row is None else (row.date, row.close, row.source_id)
    row = db.scalar(
        select(MacroSeries)
        .where(MacroSeries.series_code == code, MacroSeries.date <= on_or_before)
        .order_by(MacroSeries.date.desc())
        .limit(1)
    )
    return None if row is None else (row.date, row.value, row.source_id)


def build_figures(db: Session, week_start: dt.date) -> list[dict[str, Any]]:
    """The note's figures: value at the end of the week and at the end of the week before."""
    cfg = get_config("market").data["macro_note"]
    week_end = week_start + dt.timedelta(days=6)
    prev_end = week_start - dt.timedelta(days=1)
    figures: list[dict[str, Any]] = []
    for spec in cfg["figures"]:
        code, kind, unit = spec["code"], spec["kind"], spec["unit"]
        now = _point(db, code, kind, week_end)
        if now is None:
            continue
        before = _point(db, code, kind, prev_end)
        source = db.get(Source, now[2])
        previous = before[1] if before else None
        change = None if previous is None else (now[1] - previous)
        change_pct = None if previous is None or previous == 0 else ((now[1] / previous - 1) * 100)
        figures.append(
            {
                "code": code,
                "kind": kind,
                "unit": unit,
                "value": str(now[1]),
                "previous": None if previous is None else str(previous),
                "change": None if change is None else str(change.quantize(Decimal("0.01"))),
                "change_pct": None
                if change_pct is None
                else str(change_pct.quantize(Decimal("0.01"))),
                "as_of": now[0].isoformat(),
                "source_id": str(now[2]),
                "source_name": source.name if source else None,
                "source_url": source.url if source else None,
            }
        )
    return figures


def what_changed(figures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Figures that moved beyond the configured limits (FR4.1 "what changed")."""
    cfg = get_config("market").data["macro_note"]["what_changed"]
    pts, pct = Decimal(str(cfg["level_min_change_pts"])), Decimal(str(cfg["pct_min_change"]))
    out = []
    for fig in figures:
        if fig["change"] is None:
            continue
        if fig["unit"] == "pct":
            if abs(Decimal(fig["change"])) >= pts:
                out.append(fig)
        elif fig["change_pct"] is not None and abs(Decimal(fig["change_pct"])) >= pct:
            out.append(fig)
    return out


def draft_text(figures: list[dict[str, Any]], week_start: dt.date, locale: str) -> tuple[str, str]:
    text = TEXT[locale]
    week = week_start.isoformat()
    if locale == "bn":
        week = week.translate(_BN_DIGITS)
    lines = [text["intro"].format(week=week), "", f"## {text['changed']}"]
    changed = what_changed(figures)
    if not changed:
        lines.append(text["nothing"])
    for fig in changed:
        label = LABELS.get(fig["code"], {}).get(locale, fig["code"])
        value = _fmt(Decimal(fig["value"]), locale)
        if fig["kind"] == "index":
            pct = Decimal(fig["change_pct"])
            key = "idx_up" if pct >= 0 else "idx_down"
            lines.append(
                "- " + text[key].format(label=label, change=_fmt(abs(pct), locale), value=value)
            )
        else:
            key = "up" if Decimal(fig["change"]) >= 0 else "down"
            previous = _fmt(Decimal(fig["previous"]), locale)
            lines.append("- " + text[key].format(label=label, previous=previous, value=value))
    lines += ["", text["outro"]]
    return text["title"].format(week=week), "\n".join(lines)


def generate_draft(
    db: Session, week_start: dt.date, *, replace_draft: bool = False
) -> list[MacroNote]:
    """Create the week's drafts. Existing drafts are kept unless `replace_draft`; published
    notes are never touched."""
    week_start = TradingCalendar.week_start(week_start)
    figures = build_figures(db, week_start)
    out: list[MacroNote] = []
    for locale in LOCALES:
        note = db.scalar(
            select(MacroNote).where(MacroNote.week_start == week_start, MacroNote.locale == locale)
        )
        if note is not None and (note.status == NoteStatus.PUBLISHED.value or not replace_draft):
            out.append(note)
            continue
        title, body = draft_text(figures, week_start, locale)
        if note is None:
            note = MacroNote(
                week_start=week_start, locale=locale, title=title, body=body, figures=figures
            )
            db.add(note)
        note.title, note.body, note.figures = title, body, figures
        note.status = NoteStatus.DRAFT.value
        out.append(note)
    db.flush()
    return out


def list_notes(db: Session, *, published_only: bool, locale: str | None = None) -> list[MacroNote]:
    statement = select(MacroNote)
    if published_only:
        statement = statement.where(MacroNote.status == NoteStatus.PUBLISHED.value)
    if locale:
        statement = statement.where(MacroNote.locale == locale)
    return list(db.scalars(statement.order_by(MacroNote.week_start.desc(), MacroNote.locale)))


def get_note(db: Session, week_start: dt.date, locale: str, *, published_only: bool) -> MacroNote:
    note = db.scalar(
        select(MacroNote).where(
            MacroNote.week_start == TradingCalendar.week_start(week_start),
            MacroNote.locale == locale,
        )
    )
    if note is None or (published_only and note.status != NoteStatus.PUBLISHED.value):
        raise AuthError("NOT_FOUND", 404)
    return note


def get_note_by_id(db: Session, note_id: uuid.UUID) -> MacroNote:
    note = db.get(MacroNote, note_id)
    if note is None:
        raise AuthError("NOT_FOUND", 404)
    return note


def edit_note(db: Session, actor: User, note: MacroNote, *, title: str, body: str) -> MacroNote:
    if not title.strip() or not body.strip():
        raise AuthError("VALIDATION", 422)
    note.title, note.body = title.strip(), body.strip()
    db.flush()
    audit(db, str(actor.id), "macro_note.edit", "macro_note", str(note.id))
    return note


def set_published(db: Session, actor: User, note: MacroNote, published: bool) -> MacroNote:
    if published:
        if any(not f.get("source_id") for f in note.figures):
            raise AuthError("FIGURE_WITHOUT_SOURCE", 422)
        note.status = NoteStatus.PUBLISHED.value
        note.published_by, note.published_at = actor.id, utcnow()
    else:
        note.status = NoteStatus.DRAFT.value
        note.published_by, note.published_at = None, None
    db.flush()
    audit(
        db,
        str(actor.id),
        "macro_note.publish" if published else "macro_note.unpublish",
        "macro_note",
        str(note.id),
    )
    return note
