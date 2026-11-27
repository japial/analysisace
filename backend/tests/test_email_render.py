"""Branded HTML and plain-text emails (D31): same words in both parts, values as people
read them, labels and disclaimer as on the web, escaping, links and message structure."""

import json
import re
import string
from email.message import EmailMessage
from pathlib import Path

import pytest

from app.services import email_templates as templates
from app.services.alert_texts import EMAIL_TEXT
from app.services.email import Email, SmtpEmailSender
from app.services.email_labels import EMAIL_LABELS
from app.services.email_render import DISCLAIMER, readable
from app.services.statement_labels import ENUM_LABELS

MESSAGES = Path(__file__).resolve().parents[2] / "frontend" / "packages" / "i18n" / "messages"
BASE = "https://analysisace.com"
LOCALES = ("en", "bn")

# A plausible stored value for every placeholder the alert texts use.
SAMPLE = {
    "asset_class": "EQUITY",
    "actual_pct": "38.50",
    "target_pct": "30",
    "band_pct": "5",
    "volatility_pct": "27.25",
    "limit_pct": "25",
    "name": "Family DPS",
    "date": "2026-12-01",
    "days": "14",
    "months": "13",
    "ticker": "DMPHARMA",
    "from_status": "NON_COMPLIANT",
    "to_status": "COMPLIANT",
    "previous": "TIGHTENING|HIGH|CALM",
    "label": "EASING|MODERATE|CALM",
    "title_en": "Iran war shock",
    "title_bn": "ইরান যুদ্ধের ধাক্কা",
}
RAW = ["EQUITY", "NON_COMPLIANT", "COMPLIANT", "TIGHTENING", "EASING", "2026-12-01"]


def _placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def _visible(html: str) -> str:
    """The HTML's visible text, roughly: tags removed, entities kept."""
    return re.sub(r"<[^>]+>", " ", html)


@pytest.mark.parametrize("locale", LOCALES)
def test_labels_and_disclaimer_match_the_web_messages_d31(locale: str) -> None:
    path = MESSAGES / f"{locale}.json"
    if not path.exists():
        pytest.skip("frontend messages are not in this checkout")
    messages = json.loads(path.read_text(encoding="utf-8"))
    market, enum = messages["market"], messages["personal"]["enum"]
    labels = EMAIL_LABELS[locale]
    assert labels["shariahStatus"] == market["status"]
    assert labels["regimeRate"] == market["regime"]["rate"]
    assert labels["regimeInflation"] == market["regime"]["inflation"]
    assert labels["regimeOil"] == market["regime"]["oil"]
    assert labels["alertType"] == enum["alertType"]
    assert DISCLAIMER[locale] == messages["common"]["disclaimer"]


@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("message_key", sorted(EMAIL_TEXT))
def test_every_alert_reads_as_words_in_both_parts_d31(locale: str, message_key: str) -> None:
    subject, body = EMAIL_TEXT[message_key][locale]
    data = {k: SAMPLE[k] for k in _placeholders(subject) | _placeholders(body)}
    email = templates.alert_email(
        "karim@example.com", locale, "GOAL_REACHED", message_key, data, "/personal/goals", BASE
    )
    assert email is not None and email.html
    for part in (email.subject, email.body, _visible(email.html)):
        assert "{" not in part, part
        for raw in RAW:
            assert raw not in part.replace("analysisACE", ""), (raw, part)
    # The same sentence, the link and the disclaimer are in both parts.
    first_line = email.body.splitlines()[0]
    assert first_line in email.html or first_line.replace('"', "&quot;") in email.html
    assert f"{BASE}/{locale}/personal/goals" in email.body
    assert f'href="{BASE}/{locale}/personal/goals"' in email.html
    assert DISCLAIMER[locale] in email.body and DISCLAIMER[locale] in email.html
    assert email.headers["List-Unsubscribe"] == f"<{BASE}/{locale}/personal/alerts>"


def test_values_are_formatted_like_the_web_d31() -> None:
    en, bn = readable(SAMPLE, "en"), readable(SAMPLE, "bn")
    assert en["date"] == "1 December 2026" and bn["date"] == "১ ডিসেম্বর ২০২৬"
    assert en["actual_pct"] == "38.5" and bn["actual_pct"] == "৩৮.৫"
    assert en["from_status"] == "Not compliant" and en["to_status"] == "Shariah compliant"
    assert en["asset_class"] == ENUM_LABELS["en"]["assetClass"]["EQUITY"]
    assert bn["asset_class"] == ENUM_LABELS["bn"]["assetClass"]["EQUITY"]
    assert en["label"].count(",") == 2 and "EASING" not in en["label"]
    assert readable({"spending": "85000"}, "bn")["spending"] == "৳৮৫,০০০.০০"
    assert readable({"month": "2026-10"}, "en")["month"] == "October 2026"
    assert readable({"name": None}, "en")["name"] == "—"


def test_data_is_escaped_in_html_and_kept_in_text_d31() -> None:
    name = '<script>alert("x")</script> & Sons'
    email = templates.alert_email(
        "a@example.com", "en", "GOAL_REACHED", "GOAL_REACHED", {"name": name}, "/x", BASE
    )
    assert email is not None and email.html
    assert "<script>" not in email.html
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; Sons" in email.html
    assert name in email.body


def test_password_reset_and_verification_d31() -> None:
    link = f"{BASE}/bn/reset-password?token=abc_123"
    reset = templates.password_reset_email("rahim@example.com", "bn", link, 60)
    assert reset.html and link in reset.body and f'href="{link}"' in reset.html
    assert "৬০" in reset.body and "rahim@example.com" in reset.body
    assert "List-Unsubscribe" not in reset.headers  # account email, not a subscription
    verify = templates.verification_email(
        "rahim@example.com", "en", f"{BASE}/en/verify-email?token=t", 48
    )
    assert "48 hours" in verify.body and "Confirm my email" in verify.html
    # The preheader is hidden but present, and the page is marked as Bangla or English.
    assert '<html lang="bn"' in reset.html and "display:none" in reset.html


def test_monthly_report_lists_only_the_figures_it_has_fr20_2_d31() -> None:
    figures = {
        "month": "2026-10",
        "spending": "62800.00",
        "income": None,
        "savings": None,
        "net_worth": "18613144.80",
        "zakat_due": None,
        "fire_progress_pct": "38.40",
    }
    email = templates.monthly_report_email("k@example.com", "en", figures, BASE)
    assert email.subject == "Your analysisACE report for October 2026"
    assert "Tk 62,800.00" in email.body and "Tk 1,86,13,144.80" in email.body
    assert "Income" not in email.body and "Zakat estimate" not in email.body
    assert "Progress to your FIRE number: 38%" in email.body
    figures |= {"income": "165000.00", "savings": "102200.00", "zakat_due": "99264.75"}
    bn = templates.monthly_report_email("k@example.com", "bn", figures, BASE)
    assert "অক্টোবর ২০২৬" in bn.subject and "৳১,৬৫,০০০.০০" in bn.body and "৳৯৯,২৬৪.৭৫" in bn.body
    assert f"{BASE}/bn/personal" in bn.body


def test_smtp_message_is_text_then_html_with_headers_d31() -> None:
    email = templates.alert_email(
        "k@example.com",
        "bn",
        "GOAL_REACHED",
        "GOAL_REACHED",
        {"name": "প্রথম কোটি"},
        "/personal/goals",
        BASE,
    )
    assert isinstance(email, Email)
    sender = SmtpEmailSender(
        host="smtp.gmail.com", port=587, security="starttls", sender="a <a@b.com>"
    )
    message: EmailMessage = sender.message(email)
    assert message.get_content_type() == "multipart/alternative"
    parts = list(message.iter_parts())
    assert [p.get_content_type() for p in parts] == ["text/plain", "text/html"]
    assert all(p.get_content_charset() == "utf-8" for p in parts)
    assert "প্রথম কোটি" in parts[0].get_content() and "প্রথম কোটি" in parts[1].get_content()
    assert message["List-Unsubscribe"] == f"<{BASE}/bn/personal/alerts>"


def test_plain_email_without_html_stays_single_part_d31() -> None:
    sender = SmtpEmailSender(host="h", port=587, security="starttls", sender="a <a@b.com>")
    message = sender.message(Email(to="x@y.com", subject="s", body="text only"))
    assert message.get_content_type() == "text/plain"
