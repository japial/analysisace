"""The emails analysisACE sends, in English and Bangla (D31). Each builds a `Content` and
renders it as HTML and plain text. Wording is descriptive: it says what happened, never
what to do with money.
"""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from app.services.alert_texts import EMAIL_TEXT
from app.services.email import Email
from app.services.email_render import (
    Button,
    Content,
    Item,
    Links,
    label,
    readable,
    render,
)
from app.services.text_format import digits, money, month_text, number

_T: dict[str, dict[str, str]] = {
    "en": {
        "change_subject": "Confirm your new email for analysisACE",
        "change_preheader": "One click to make this your sign-in email.",
        "change_heading": "Confirm your new email",
        "change_body": "Someone signed in to analysisACE asked to use {email} as their sign-in email.",
        "change_button": "Use this email",
        "change_valid": "The link works once, for {hours} hours. Until it is opened, the old email stays in use.",
        "change_ignore": "If this was not you, ignore this email. Nothing changes.",
        "changed_subject": "Your analysisACE sign-in email was changed",
        "changed_preheader": "Your account now uses a different email.",
        "changed_heading": "Your sign-in email was changed",
        "changed_body": "The analysisACE account that used {old} now signs in with {new}. Emails will go there from now on.",
        "changed_warning": "If you did not do this, reset your password from the sign-in page and write to us at once.",
        "changed_button": "Go to sign-in",
        "reset_subject": "Reset your analysisACE password",
        "reset_preheader": "A link to choose a new password, valid for {minutes} minutes.",
        "reset_heading": "Reset your password",
        "reset_body": "Someone asked to reset the password for the analysisACE account {email}.",
        "reset_button": "Choose a new password",
        "reset_valid": "The link works once, for {minutes} minutes.",
        "reset_ignore": "If this was not you, ignore this email. Your password stays the same.",
        "verify_subject": "Confirm your email for analysisACE",
        "verify_preheader": "One click to confirm your address.",
        "verify_heading": "Confirm your email",
        "verify_body": "Welcome to analysisACE. Please confirm that {email} is your address.",
        "verify_button": "Confirm my email",
        "verify_valid": "The link works for {hours} hours.",
        "verify_until": "Until you confirm, reminders and monthly reports are shown in the app but not emailed.",
        "verify_ignore": "If you did not sign up, ignore this email.",
        "open": "Open in analysisACE",
        "alert_reason": 'You get this email because the "{alert}" alert is set to email.',
        "manage": "Change alert settings",
        "unsubscribe": "Stop these emails",
        "report_subject": "Your analysisACE report for {month}",
        "report_preheader": "Spending, savings and net worth for {month}.",
        "report_heading": "Your money in {month}",
        "report_body": "Here is how {month} went for your household, from your own records.",
        "report_spending": "Spending",
        "report_income": "Income",
        "report_saved": "Left after costs",
        "report_net_worth": "Net worth today",
        "report_zakat": "Zakat estimate",
        "report_fire": "Progress to your FIRE number",
        "report_button": "Open My money",
        "report_reason": "You get this email because the monthly report is set to email.",
        "digest_subject": "{count} new notices from analysisACE",
        "digest_subject_one": "1 new notice from analysisACE",
        "digest_preheader": "Your notices since the last digest, in one email.",
        "digest_heading": "Your notices",
        "digest_body": "These came in since your last digest.",
        "digest_more": "And {count} more in the app.",
        "digest_open": "Open",
        "digest_button": "See all notices",
        "digest_reason": "You get one email a day because these alerts are set to arrive once a day.",
        "digest_push_title": "{count} new notices",
        "digest_push_title_one": "1 new notice",
    },
    "bn": {
        "change_subject": "analysisACE-এর জন্য নতুন ইমেইল নিশ্চিত করুন",
        "change_preheader": "এক ক্লিকে এটিকে আপনার প্রবেশের ইমেইল করুন।",
        "change_heading": "নতুন ইমেইল নিশ্চিত করুন",
        "change_body": "analysisACE-এ প্রবেশ করা একজন ব্যবহারকারী {email}-কে প্রবেশের ইমেইল হিসেবে ব্যবহার করতে চেয়েছেন।",
        "change_button": "এই ইমেইল ব্যবহার করুন",
        "change_valid": "লিংকটি একবার, {hours} ঘণ্টার মধ্যে কাজ করবে। খোলার আগ পর্যন্ত আগের ইমেইলই চালু থাকবে।",
        "change_ignore": "আপনি অনুরোধ না করে থাকলে এই ইমেইল উপেক্ষা করুন। কিছুই বদলাবে না।",
        "changed_subject": "আপনার analysisACE প্রবেশের ইমেইল বদলানো হয়েছে",
        "changed_preheader": "আপনার অ্যাকাউন্ট এখন অন্য ইমেইল ব্যবহার করছে।",
        "changed_heading": "প্রবেশের ইমেইল বদলানো হয়েছে",
        "changed_body": "যে analysisACE অ্যাকাউন্ট {old} ব্যবহার করত, সেটি এখন {new} দিয়ে প্রবেশ করে। এখন থেকে ইমেইল সেখানে যাবে।",
        "changed_warning": "এটি আপনি না করে থাকলে প্রবেশের পাতা থেকে পাসওয়ার্ড পরিবর্তন করুন এবং এখনই আমাদের জানান।",
        "changed_button": "প্রবেশের পাতায় যান",
        "reset_subject": "আপনার analysisACE পাসওয়ার্ড পরিবর্তন করুন",
        "reset_preheader": "নতুন পাসওয়ার্ড দেওয়ার লিংক, {minutes} মিনিট কাজ করবে।",
        "reset_heading": "পাসওয়ার্ড পরিবর্তন করুন",
        "reset_body": "analysisACE অ্যাকাউন্ট {email}-এর পাসওয়ার্ড পরিবর্তনের অনুরোধ করা হয়েছে।",
        "reset_button": "নতুন পাসওয়ার্ড দিন",
        "reset_valid": "লিংকটি একবার, {minutes} মিনিটের মধ্যে কাজ করবে।",
        "reset_ignore": "আপনি অনুরোধ না করে থাকলে এই ইমেইল উপেক্ষা করুন। আপনার পাসওয়ার্ড আগের মতোই থাকবে।",
        "verify_subject": "analysisACE-এর জন্য আপনার ইমেইল নিশ্চিত করুন",
        "verify_preheader": "এক ক্লিকে আপনার ঠিকানা নিশ্চিত করুন।",
        "verify_heading": "আপনার ইমেইল নিশ্চিত করুন",
        "verify_body": "analysisACE-এ স্বাগতম। অনুগ্রহ করে নিশ্চিত করুন যে {email} আপনার ঠিকানা।",
        "verify_button": "আমার ইমেইল নিশ্চিত করুন",
        "verify_valid": "লিংকটি {hours} ঘণ্টা কাজ করবে।",
        "verify_until": "নিশ্চিত না করা পর্যন্ত তাগিদ ও মাসিক প্রতিবেদন অ্যাপে দেখা যাবে, ইমেইলে যাবে না।",
        "verify_ignore": "আপনি নিবন্ধন না করে থাকলে এই ইমেইল উপেক্ষা করুন।",
        "open": "analysisACE-এ খুলুন",
        "alert_reason": '"{alert}" সতর্কবার্তা ইমেইলে পাঠানোর জন্য চালু আছে বলে আপনি এই ইমেইল পাচ্ছেন।',
        "manage": "সতর্কবার্তার সেটিংস বদলান",
        "unsubscribe": "এই ইমেইল বন্ধ করুন",
        "report_subject": "{month} মাসের analysisACE প্রতিবেদন",
        "report_preheader": "{month} মাসের খরচ, সঞ্চয় ও নিট সম্পদ।",
        "report_heading": "{month} মাসে আপনার অর্থ",
        "report_body": "আপনার নিজের রেকর্ড থেকে, {month} মাস আপনার পরিবারের জন্য কেমন গেল।",
        "report_spending": "খরচ",
        "report_income": "আয়",
        "report_saved": "খরচের পর বাকি",
        "report_net_worth": "আজকের নিট সম্পদ",
        "report_zakat": "যাকাতের আনুমানিক হিসাব",
        "report_fire": "FIRE অঙ্কের দিকে অগ্রগতি",
        "report_button": "আমার অর্থ খুলুন",
        "report_reason": "মাসিক প্রতিবেদন ইমেইলে পাঠানোর জন্য চালু আছে বলে আপনি এই ইমেইল পাচ্ছেন।",
        "digest_subject": "analysisACE থেকে {count}টি নতুন নোটিশ",
        "digest_subject_one": "analysisACE থেকে ১টি নতুন নোটিশ",
        "digest_preheader": "শেষ সারাংশের পর থেকে আপনার নোটিশ, এক ইমেইলে।",
        "digest_heading": "আপনার নোটিশ",
        "digest_body": "আপনার শেষ সারাংশের পর থেকে এগুলো এসেছে।",
        "digest_more": "অ্যাপে আরও {count}টি আছে।",
        "digest_open": "খুলুন",
        "digest_button": "সব নোটিশ দেখুন",
        "digest_reason": "এই সতর্কবার্তাগুলো দিনে একবার পাঠানোর জন্য ঠিক করা আছে বলে আপনি দিনে একটি ইমেইল পাচ্ছেন।",
        "digest_push_title": "{count}টি নতুন নোটিশ",
        "digest_push_title_one": "১টি নতুন নোটিশ",
    },
}


def _lang(locale: str) -> str:
    return "bn" if locale == "bn" else "en"


def _url(base: str, locale: str, path: str) -> str:
    return f"{base.rstrip('/')}/{locale}/{path.lstrip('/')}"


def password_reset_email(to: str, locale: str, link: str, minutes: int) -> Email:
    lang = _lang(locale)
    t = _T[lang]
    shown = digits(str(minutes), lang)
    return render(
        Content(
            locale=lang,
            to=to,
            subject=t["reset_subject"],
            preheader=t["reset_preheader"].format(minutes=shown),
            heading=t["reset_heading"],
            paragraphs=[t["reset_body"].format(email=to)],
            button=Button(t["reset_button"], link),
            notes=[t["reset_valid"].format(minutes=shown), t["reset_ignore"]],
        )
    )


def mask_email(address: str) -> str:
    """ "rahim@example.com" -> "r•••@example.com": enough to recognise, not to read."""
    local, _, domain = address.partition("@")
    return f"{local[:1]}\u2022\u2022\u2022@{domain}" if domain else address


def email_change_email(to: str, locale: str, link: str, hours: int) -> Email:
    """D39: sent to the new address; the change happens only when the link is opened."""
    lang = _lang(locale)
    t = _T[lang]
    return render(
        Content(
            locale=lang,
            to=to,
            subject=t["change_subject"],
            preheader=t["change_preheader"],
            heading=t["change_heading"],
            paragraphs=[t["change_body"].format(email=to)],
            button=Button(t["change_button"], link),
            notes=[
                t["change_valid"].format(hours=digits(str(hours), lang)),
                t["change_ignore"],
            ],
        )
    )


def email_changed_notice(to: str, locale: str, new_email: str, base: str) -> Email:
    """D39: sent to the old address once the change is made, so a takeover is noticed."""
    lang = _lang(locale)
    t = _T[lang]
    return render(
        Content(
            locale=lang,
            to=to,
            subject=t["changed_subject"],
            preheader=t["changed_preheader"],
            heading=t["changed_heading"],
            paragraphs=[t["changed_body"].format(old=to, new=mask_email(new_email))],
            button=Button(t["changed_button"], _url(base, lang, "/signin")),
            notes=[t["changed_warning"]],
        )
    )


def verification_email(to: str, locale: str, link: str, hours: int) -> Email:
    lang = _lang(locale)
    t = _T[lang]
    return render(
        Content(
            locale=lang,
            to=to,
            subject=t["verify_subject"],
            preheader=t["verify_preheader"],
            heading=t["verify_heading"],
            paragraphs=[t["verify_body"].format(email=to)],
            button=Button(t["verify_button"], link),
            notes=[
                t["verify_valid"].format(hours=digits(str(hours), lang)),
                t["verify_until"],
                t["verify_ignore"],
            ],
        )
    )


def _manage(
    base: str, lang: str, unsubscribe: Links | None
) -> tuple[Button, Button | None, dict[str, str]]:
    """The footer links and the List-Unsubscribe headers (D34). With a person's links, mail
    apps show their own "unsubscribe" button and post to the one-click address (RFC 8058);
    without them, the header points to the alert settings page."""
    settings = _url(base, lang, "/personal/alerts")
    manage = Button(_T[lang]["manage"], settings)
    if unsubscribe is None:
        return manage, None, {"List-Unsubscribe": f"<{settings}>"}
    return (
        manage,
        Button(_T[lang]["unsubscribe"], unsubscribe.page),
        {
            "List-Unsubscribe": f"<{unsubscribe.one_click}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    )


def alert_email(
    to: str,
    locale: str,
    alert_type: str,
    message_key: str,
    data: Mapping[str, Any],
    link: str,
    base: str,
    unsubscribe: Links | None = None,
) -> Email | None:
    """An alert notice (FR7, FR20.1) with its values as words and local numbers. None when
    the notice has no email text."""
    template = EMAIL_TEXT.get(message_key)
    if template is None:
        return None
    lang = _lang(locale)
    t = _T[lang]
    subject, body = template[lang]
    values = readable(data, lang)
    text = body.format(**values)
    manage, stop, headers = _manage(base, lang, unsubscribe)
    return render(
        Content(
            locale=lang,
            to=to,
            subject=subject.format(**values),
            preheader=text,
            heading=subject.format(**values),
            paragraphs=[text],
            button=Button(t["open"], _url(base, lang, link)),
            reason=t["alert_reason"].format(alert=label("alertType", alert_type, lang)),
            manage=manage,
            unsubscribe=stop,
            headers=headers,
        )
    )


def monthly_report_email(
    to: str,
    locale: str,
    figures: Mapping[str, Any],
    base: str,
    unsubscribe: Links | None = None,
) -> Email:
    """The monthly report (FR20.2): last month's spending, income and savings, today's net
    worth, a Zakat estimate and FIRE progress, each only when there is a figure."""
    lang = _lang(locale)
    t = _T[lang]
    month = month_text(str(figures["month"]), lang)
    facts: list[tuple[str, str]] = [(t["report_spending"], money(figures["spending"], lang))]
    if figures.get("income") is not None:
        facts.append((t["report_income"], money(figures["income"], lang)))
        facts.append((t["report_saved"], money(figures["savings"], lang)))
    facts.append((t["report_net_worth"], money(figures["net_worth"], lang)))
    if figures.get("zakat_due") is not None:
        facts.append((t["report_zakat"], money(figures["zakat_due"], lang)))
    if figures.get("fire_progress_pct") is not None:
        progress = number(Decimal(str(figures["fire_progress_pct"])), lang, max_places=0)
        facts.append((t["report_fire"], f"{progress}%"))
    manage, stop, headers = _manage(base, lang, unsubscribe)
    return render(
        Content(
            locale=lang,
            to=to,
            subject=t["report_subject"].format(month=month),
            preheader=t["report_preheader"].format(month=month),
            heading=t["report_heading"].format(month=month),
            paragraphs=[t["report_body"].format(month=month)],
            facts=facts,
            button=Button(t["report_button"], _url(base, lang, "/personal")),
            reason=t["report_reason"],
            manage=manage,
            unsubscribe=stop,
            headers=headers,
        )
    )


DIGEST_LIMIT = 20


def digest_item(
    locale: str, message_key: str, data: Mapping[str, Any], link: str, base: str
) -> Item | None:
    """One notice as a digest entry: its subject, its sentence and its link."""
    template = EMAIL_TEXT.get(message_key)
    if template is None:
        return None
    lang = _lang(locale)
    subject, body = template[lang]
    values = readable(data, lang)
    return Item(
        title=subject.format(**values),
        text=body.format(**values),
        url=_url(base, lang, link),
        link_label=_T[lang]["digest_open"],
    )


def digest_email(
    to: str, locale: str, items: list[Item], base: str, unsubscribe: Links | None = None
) -> Email:
    """The daily digest (FR7.3, D32): every notice waiting since the last one, newest last,
    shown up to DIGEST_LIMIT with the rest counted."""
    lang = _lang(locale)
    t = _T[lang]
    count = len(items)
    shown = items[:DIGEST_LIMIT]
    notes = (
        [t["digest_more"].format(count=digits(str(count - len(shown)), lang))]
        if count > len(shown)
        else []
    )
    subject = (
        t["digest_subject_one"]
        if count == 1
        else t["digest_subject"].format(count=digits(str(count), lang))
    )
    manage, stop, headers = _manage(base, lang, unsubscribe)
    return render(
        Content(
            locale=lang,
            to=to,
            subject=subject,
            preheader=t["digest_preheader"],
            heading=t["digest_heading"],
            paragraphs=[t["digest_body"]],
            items=shown,
            notes=notes,
            button=Button(t["digest_button"], _url(base, lang, "/personal/alerts")),
            reason=t["digest_reason"],
            manage=manage,
            unsubscribe=stop,
            headers=headers,
        )
    )


def digest_push_title(locale: str, count: int) -> str:
    lang = _lang(locale)
    t = _T[lang]
    return (
        t["digest_push_title_one"]
        if count == 1
        else t["digest_push_title"].format(count=digits(str(count), lang))
    )


def job_failed_email(to: str, job: str, error: str, environment: str, base: str) -> Email:
    """For operators (M1: alert on failed jobs). English only: it goes to the team."""
    return render(
        Content(
            locale="en",
            to=to,
            subject=f"[analysisACE {environment}] Job failed: {job}",
            preheader=f"The scheduled job '{job}' failed.",
            heading="A scheduled job failed",
            paragraphs=[
                f"The scheduled job '{job}' failed in {environment}.",
                f"Error: {error[:500]}",
            ],
            button=Button("Open the job runs", _url(base, "en", "/admin/audit")),
            reason="You get this email because your address is in OPS_ALERT_EMAILS.",
        )
    )
