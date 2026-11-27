"""Numbers, money and dates as people read them, in English and Bangla.

One place for the formatting the PDF statements, the emails and the alert texts share, so a
figure reads the same everywhere. Money uses lakh and crore grouping; Bangla uses Bangla
digits and month names.
"""

import datetime as dt
from decimal import Decimal, InvalidOperation

BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")

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


def digits(text: str, locale: str) -> str:
    return text.translate(BN_DIGITS) if locale == "bn" else text


def taka(amount: Decimal, locale: str) -> str:
    """ "Tk 12,34,567.50" with lakh and crore grouping; "৳১২,৩৪,৫৬৭.৫০" in Bangla."""
    whole, _, cents = f"{abs(amount):.2f}".partition(".")
    head, tail = whole[:-3], whole[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    text = f"{'-' if amount < 0 else ''}{','.join([*groups, tail])}.{cents}"
    return f"৳{text.translate(BN_DIGITS)}" if locale == "bn" else f"Tk {text}"


def money(value: Decimal | str | None, locale: str) -> str:
    if value is None or value == "":
        return "—"
    return taka(Decimal(str(value)), locale)


def pct(value: Decimal | str | None, locale: str, places: int = 0) -> str:
    if value is None or value == "":
        return "—"
    return digits(f"{Decimal(str(value)):.{places}f}%", locale)


def number(value: Decimal | str | int | None, locale: str, max_places: int = 2) -> str:
    """A plain number with at most `max_places` decimals and no trailing zeros: "38.5",
    "12", "৩৮.৫". Text that is not a number is returned as it is."""
    if value is None or value == "":
        return "—"
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)
    text = f"{amount:.{max_places}f}".rstrip("0").rstrip(".") if max_places else f"{amount:.0f}"
    return digits(text, locale)


def date_text(day: dt.date | str, locale: str) -> str:
    if isinstance(day, str):
        day = dt.date.fromisoformat(day[:10])
    return digits(f"{day.day} {MONTHS[locale][day.month - 1]} {day.year}", locale)


def month_text(month: dt.date | str, locale: str) -> str:
    """ "2026-10" or a date in October 2026 -> "October 2026" / "অক্টোবর ২০২৬"."""
    if isinstance(month, str):
        year, mon = month[:7].split("-")
        month = dt.date(int(year), int(mon), 1)
    return digits(f"{MONTHS[locale][month.month - 1]} {month.year}", locale)
