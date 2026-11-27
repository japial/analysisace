"""Branded email in HTML and plain text from one content model (D31).

Every email is sent as multipart/alternative: an HTML part for mail apps, and a plain-text
part with the same words for old clients, screen readers and spam filters. Both come from
one `Content`, so they cannot say different things.

The HTML follows what survives Gmail, Outlook and phone mail apps: tables for layout,
inline styles only, no web fonts or images that must load, a "bulletproof" button that is a
coloured table cell, and a 600 px width that shrinks on a phone. Every value that comes
from data is escaped. Every email ends with the disclaimer (hard rule, PRD section 0).
"""

import html
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.services.email import Email
from app.services.email_labels import EMAIL_LABELS
from app.services.statement_labels import ENUM_LABELS
from app.services.text_format import date_text, money, month_text, number

# Brand (D14). Deep teal is the text-safe teal on white (5.5:1).
NAVY = "#0B1F3A"
TEAL = "#2DD4BF"
TEAL_DEEP = "#0F766E"
INK = "#1F2A37"
MUTED = "#5B6675"
LINE = "#E3E8EE"
PAGE = "#F4F6F8"

FONTS = {
    "en": "Inter, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    "bn": "'Noto Sans Bengali', 'Hind Siliguri', 'Nirmala UI', Vrinda, Arial, sans-serif",
}

DISCLAIMER = {
    # The same words as the web pages and PDFs (common.disclaimer); a test checks.
    "en": "Historical analysis for education only. Not investment advice.",
    "bn": "ঐতিহাসিক বিশ্লেষণ শুধু শিক্ষার উদ্দেশ্যে। এটি বিনিয়োগ পরামর্শ নয়।",
}

CHROME = {
    "en": {
        "fallback": "If the button does not work, copy this address into your browser:",
        "footer": "analysisACE · Personal finance for families in Bangladesh",
    },
    "bn": {
        "fallback": "বোতামটি কাজ না করলে এই ঠিকানাটি ব্রাউজারে কপি করুন:",
        "footer": "analysisACE · বাংলাদেশের পরিবারের জন্য ব্যক্তিগত অর্থ ব্যবস্থাপনা",
    },
}


@dataclass(frozen=True)
class Button:
    label: str
    url: str


@dataclass(frozen=True)
class Content:
    """What an email says. Every string is plain text; the renderer escapes it for HTML."""

    locale: str
    to: str
    subject: str
    # Shown after the subject in the inbox list.
    preheader: str
    heading: str
    paragraphs: Sequence[str] = ()
    # Label and value pairs, for figures.
    facts: Sequence[tuple[str, str]] = ()
    button: Button | None = None
    # Smaller notes after the button, such as how long a link works.
    notes: Sequence[str] = ()
    # Why the person gets this email, and where to change it.
    reason: str | None = None
    manage: Button | None = None
    headers: Mapping[str, str] = field(default_factory=dict)


def _e(text: str) -> str:
    return html.escape(text, quote=True)


def _text(content: Content) -> str:
    chrome = CHROME[content.locale]
    lines = [content.heading, ""]
    for paragraph in content.paragraphs:
        lines += [paragraph, ""]
    if content.facts:
        lines += [f"{label}: {value}" for label, value in content.facts] + [""]
    if content.button:
        lines += [f"{content.button.label}:", content.button.url, ""]
    for note in content.notes:
        lines += [note, ""]
    if content.reason:
        lines.append(content.reason)
    if content.manage:
        lines += [f"{content.manage.label}: {content.manage.url}"]
    if content.reason or content.manage:
        lines.append("")
    lines += ["--", DISCLAIMER[content.locale], chrome["footer"]]
    return "\n".join(lines).strip() + "\n"


def _html(content: Content) -> str:
    locale = content.locale
    font = FONTS[locale]
    chrome = CHROME[locale]
    base = f"font-family:{font};color:{INK};"
    parts: list[str] = []
    for paragraph in content.paragraphs:
        parts.append(
            f'<p style="{base}font-size:16px;line-height:26px;margin:0 0 16px;">{_e(paragraph)}</p>'
        )
    if content.facts:
        rows = "".join(
            f'<tr><td style="{base}font-size:15px;line-height:22px;padding:10px 0;'
            f'border-bottom:1px solid {LINE};color:{MUTED};">{_e(label)}</td>'
            f'<td align="right" style="{base}font-size:15px;line-height:22px;padding:10px 0;'
            f'border-bottom:1px solid {LINE};font-weight:600;">{_e(value)}</td></tr>'
            for label, value in content.facts
        )
        parts.append(
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'border="0" style="border-collapse:collapse;margin:0 0 20px;">{rows}</table>'
        )
    if content.button:
        url = _e(content.button.url)
        parts.append(
            '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
            'style="margin:8px 0 20px;"><tr>'
            f'<td bgcolor="{TEAL_DEEP}" style="border-radius:8px;">'
            f'<a href="{url}" target="_blank" style="display:inline-block;padding:13px 24px;'
            f"font-family:{font};font-size:16px;font-weight:600;line-height:20px;"
            f'color:#FFFFFF;text-decoration:none;border-radius:8px;">{_e(content.button.label)}</a>'
            "</td></tr></table>"
            f'<p style="{base}font-size:13px;line-height:20px;margin:0 0 16px;color:{MUTED};">'
            f'{_e(chrome["fallback"])}<br><a href="{url}" style="color:{TEAL_DEEP};'
            f'word-break:break-all;">{url}</a></p>'
        )
    for note in content.notes:
        parts.append(
            f'<p style="{base}font-size:14px;line-height:22px;margin:0 0 12px;color:{MUTED};">'
            f"{_e(note)}</p>"
        )
    footer: list[str] = []
    if content.reason:
        footer.append(_e(content.reason))
    if content.manage:
        footer.append(
            f'<a href="{_e(content.manage.url)}" style="color:{TEAL_DEEP};">'
            f"{_e(content.manage.label)}</a>"
        )
    reason_block = (
        f'<p style="{base}font-size:13px;line-height:20px;margin:0 0 12px;color:{MUTED};">'
        f"{' '.join(footer)}</p>"
        if footer
        else ""
    )
    # A run of invisible characters keeps the inbox preview from showing the email's body.
    pad = "&#8204;&nbsp;" * 60
    return f"""<!DOCTYPE html>
<html lang="{locale}" dir="ltr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
<meta name="x-apple-disable-message-reformatting">
<title>{_e(content.subject)}</title>
</head>
<body style="margin:0;padding:0;background-color:{PAGE};">
<div style="display:none;font-size:1px;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;mso-hide:all;">{_e(content.preheader)}{pad}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{PAGE}" style="background-color:{PAGE};">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%;">
<tr><td bgcolor="{NAVY}" style="background-color:{NAVY};border-radius:12px 12px 0 0;padding:18px 28px;">
<span style="font-family:'Space Grotesk',{FONTS["en"]};font-size:22px;font-weight:700;letter-spacing:-0.2px;color:#FFFFFF;" lang="en">analysis<span style="color:{TEAL};">ACE</span></span>
</td></tr>
<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:28px 28px 12px;border-left:1px solid {LINE};border-right:1px solid {LINE};">
<h1 style="{base}font-size:22px;line-height:30px;font-weight:700;color:{NAVY};margin:0 0 16px;">{_e(content.heading)}</h1>
{"".join(parts)}
</td></tr>
<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:4px 28px 24px;border:1px solid {LINE};border-top:0;border-radius:0 0 12px 12px;">
{reason_block}
<p style="{base}font-size:13px;line-height:20px;margin:0;padding-top:12px;border-top:1px solid {LINE};color:{MUTED};">{_e(DISCLAIMER[locale])}</p>
</td></tr>
<tr><td align="center" style="padding:16px 8px;">
<p style="font-family:{font};font-size:12px;line-height:18px;margin:0;color:{MUTED};">{_e(chrome["footer"])}</p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>
"""


def render(content: Content) -> Email:
    return Email(
        to=content.to,
        subject=content.subject,
        body=_text(content),
        html=_html(content),
        headers=dict(content.headers),
    )


# --- values as people read them -----------------------------------------------------------

MONEY_KEYS = ("amount", "spending", "net_worth", "zakat_due", "income", "savings")


def label(group: str, value: str, locale: str) -> str:
    return EMAIL_LABELS[locale].get(group, {}).get(value, value)


def regime_label(code: str, locale: str) -> str:
    """ "EASING|HIGH|CALM" -> "Rates easing, Inflation high, Oil calm", as on the web."""
    rate, inflation, oil = ([*code.split("|"), "UNKNOWN", "UNKNOWN", "UNKNOWN"])[:3]
    return ", ".join(
        (
            label("regimeRate", rate, locale),
            label("regimeInflation", inflation, locale),
            label("regimeOil", oil, locale),
        )
    )


def readable(data: Mapping[str, Any], locale: str) -> dict[str, str]:
    """Stored alert values as words and local numbers, matching the web alerts page:
    dates, money and percentages formatted, codes turned into labels."""
    out: dict[str, str] = {}
    for key, value in data.items():
        if value is None:
            out[key] = "—"
        elif key == "date":
            out[key] = date_text(str(value), locale)
        elif key == "month":
            out[key] = month_text(str(value), locale)
        elif key.endswith(MONEY_KEYS):
            out[key] = money(str(value), locale)
        elif key.endswith("_pct") or key in ("days", "months"):
            out[key] = number(value, locale)
        elif key == "asset_class":
            out[key] = ENUM_LABELS[locale]["assetClass"].get(str(value), str(value))
        elif key in ("from_status", "to_status"):
            out[key] = label("shariahStatus", str(value), locale)
        elif key in ("label", "previous"):
            out[key] = regime_label(str(value), locale)
        else:
            out[key] = str(value)
    return out
