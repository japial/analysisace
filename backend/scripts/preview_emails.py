"""Write every email analysisACE sends, in English and Bangla, to HTML and text files for
review (D31). Uses fictional sample values; nothing is sent.

    .venv/Scripts/python scripts/preview_emails.py [output folder]

The default folder is backend/.email-previews (not committed). Open index.html in a browser.
"""

import html
import sys
from pathlib import Path

from app.services import email_templates as templates
from app.services.email import Email
from app.services.email_render import Links

BASE = "https://analysisace.com"
TO = "karim.rahman@example.com"


def _stop(locale: str) -> Links:
    return Links(
        page=f"{BASE}/{locale}/unsubscribe?t=sample-token",
        one_click=f"{BASE}/{locale}/unsubscribe/one-click?t=sample-token",
    )


def samples(locale: str) -> dict[str, Email | None]:
    report = {
        "month": "2026-10",
        "spending": "87390.00",
        "income": "165000.00",
        "savings": "77610.00",
        "net_worth": "18613144.80",
        "zakat_due": "99264.75",
        "fire_progress_pct": "38.40",
    }
    return {
        "password-reset": templates.password_reset_email(
            TO, locale, f"{BASE}/{locale}/reset-password?token=sample-token", 60
        ),
        "verify-email": templates.verification_email(
            TO, locale, f"{BASE}/{locale}/verify-email?token=sample-token", 48
        ),
        "alert-goal": templates.alert_email(
            TO,
            locale,
            "GOAL_REACHED",
            "GOAL_REACHED",
            {"name": "First crore"},
            "/personal/goals",
            BASE,
            _stop(locale),
        ),
        "alert-drift": templates.alert_email(
            TO,
            locale,
            "ALLOCATION_DRIFT",
            "ALLOCATION_DRIFT",
            {"asset_class": "EQUITY", "actual_pct": "38.50", "target_pct": "30", "band_pct": "5"},
            "/personal/allocation",
            BASE,
            _stop(locale),
        ),
        "alert-shariah": templates.alert_email(
            TO,
            locale,
            "SHARIAH_STATUS",
            "SHARIAH_STATUS_CHANGED",
            {"ticker": "DMPHARMA", "from_status": "UNDER_REVIEW", "to_status": "COMPLIANT"},
            "/companies/DMPHARMA",
            BASE,
            _stop(locale),
        ),
        "alert-zakat-date": templates.alert_email(
            TO,
            locale,
            "HAWL_APPROACHING",
            "HAWL_APPROACHING",
            {"name": "Karim Rahman", "date": "2027-02-01", "days": "30"},
            "/personal/zakat",
            BASE,
            _stop(locale),
        ),
        "email-change": templates.email_change_email(
            "karim.new@example.com",
            locale,
            f"{BASE}/{locale}/confirm-email-change?token=sample-token",
            48,
        ),
        "email-changed": templates.email_changed_notice(TO, locale, "karim.new@example.com", BASE),
        "monthly-report": templates.monthly_report_email(TO, locale, report, BASE, _stop(locale)),
        "daily-digest": templates.digest_email(
            TO,
            locale,
            [
                item
                for key, data, link in (
                    ("GOAL_REACHED", {"name": "First crore"}, "/personal/goals"),
                    (
                        "HAWL_APPROACHING",
                        {"name": "Karim Rahman", "date": "2027-02-01", "days": "30"},
                        "/personal/zakat",
                    ),
                    (
                        "MATURITY_DUE",
                        {"name": "Family DPS", "date": "2026-12-15", "days": "18"},
                        "/personal/sukuk",
                    ),
                )
                if (item := templates.digest_item(locale, key, data, link, BASE)) is not None
            ],
            BASE,
            _stop(locale),
        ),
    }


def main() -> None:
    out = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(__file__).resolve().parents[1] / ".email-previews"
    )
    out.mkdir(parents=True, exist_ok=True)
    links: list[str] = []
    for locale in ("en", "bn"):
        for name, email in samples(locale).items():
            if email is None or email.html is None:
                continue
            stem = f"{name}-{locale}"
            (out / f"{stem}.html").write_text(email.html, encoding="utf-8")
            (out / f"{stem}.txt").write_text(
                f"Subject: {email.subject}\n\n{email.body}", encoding="utf-8"
            )
            links.append(
                f'<li><a href="{stem}.html">{html.escape(email.subject)}</a> '
                f'(<a href="{stem}.txt">text</a>)</li>'
            )
    job = templates.job_failed_email(
        "ops@example.com", "market_analytics", "ValueError('sample')", "production", BASE
    )
    (out / "job-failed-en.html").write_text(job.html or "", encoding="utf-8")
    links.append('<li><a href="job-failed-en.html">Job failed (operators)</a></li>')
    page = '<!DOCTYPE html><meta charset="utf-8"><title>Email previews</title>'
    (out / "index.html").write_text(f"{page}<ul>{''.join(links)}</ul>", encoding="utf-8")
    print(f"Wrote {len(links)} previews to {out}")


if __name__ == "__main__":
    main()
