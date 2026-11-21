"""PDF statements for Zakat and tax snapshots (F13)."""

import json
from decimal import Decimal
from pathlib import Path

import pypdfium2 as pdfium
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services import statements
from app.services.statement_labels import ENUM_LABELS
from tests.personal_helpers import add_user, base, login, member

MESSAGES = Path(__file__).resolve().parents[2] / "frontend" / "packages" / "i18n" / "messages"


def _text(content: bytes) -> str:
    doc = pdfium.PdfDocument(content)
    return "\n".join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))


def _snapshots(client: TestClient, session: Session) -> tuple[dict[str, str], str, dict, dict]:
    owner, root = login(client), base(session)
    karim = member(session, "Karim")
    zakat = client.post(f"{root}/zakat/snapshots", headers=owner, json={"member_id": str(karim.id)})
    assert zakat.status_code == 201, zakat.text
    tax = client.post(
        f"{root}/tax/snapshots",
        headers=owner,
        json={"member_id": str(karim.id), "tax_year": "2025-26", "salary_income": "900000"},
    )
    assert tax.status_code == 201, tax.text
    return owner, root, zakat.json()["data"], tax.json()["data"]


def test_zakat_pdf_repeats_the_snapshot_with_disclaimer_fr13(
    demo_client: TestClient, demo_session: Session
) -> None:
    owner, root, zakat, _ = _snapshots(demo_client, demo_session)
    response = demo_client.get(f"{root}/zakat/snapshots/{zakat['id']}/statement.pdf", headers=owner)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")

    text = _text(response.content)
    assert "Zakat statement" in text
    assert "Historical analysis for education only. Not investment advice." in text
    # The figures are the stored ones, formatted with lakh and crore grouping.
    assert statements.money(Decimal(zakat["zakat_due"]), "en") in text
    assert statements.money(Decimal(zakat["nisab_value"]), "en") in text
    assert zakat["config_version"] in text
    # Every number is traceable: computation time and market price sources (PRD section 0).
    assert "Computed at" in text
    assert "Demo data (synthetic, not real market data)" in text


def test_bangla_pdf_uses_bangla_digits_and_font(
    demo_client: TestClient, demo_session: Session
) -> None:
    owner, root, zakat, tax = _snapshots(demo_client, demo_session)
    for path in (
        f"{root}/zakat/snapshots/{zakat['id']}/statement.pdf?locale=bn",
        f"{root}/tax/snapshots/{tax['id']}/statement.pdf?locale=bn",
    ):
        response = demo_client.get(path, headers=owner)
        assert response.status_code == 200
        assert b"NotoSansBengali" in response.content
        text = _text(response.content)
        assert "৳" in text
        assert any(digit in text for digit in "০১২৩৪৫৬৭৮৯")
    assert (
        demo_client.get(
            f"{root}/zakat/snapshots/{zakat['id']}/statement.pdf?locale=fr", headers=owner
        ).status_code
        == 422
    )


def test_tax_pdf_has_wealth_income_and_rebate_sections_fr13_5(
    demo_client: TestClient, demo_session: Session
) -> None:
    owner, root, _, tax = _snapshots(demo_client, demo_session)
    response = demo_client.get(f"{root}/tax/snapshots/{tax['id']}/statement.pdf", headers=owner)
    assert response.status_code == 200
    text = _text(response.content)
    for heading in (
        "Tax statement 2025-26",
        "Assets",
        "Income",
        "Tax deducted at source",
        "does not file tax returns",
    ):
        assert heading in text
    assert statements.money(Decimal(tax["items"]["totals"]["net_wealth_cost"]), "en") in text
    assert statements.money(Decimal("900000"), "en") in text  # the salary entered


def test_pdfs_follow_household_access_and_zakat_consent(
    demo_client: TestClient, demo_session: Session
) -> None:
    _, root, zakat, tax = _snapshots(demo_client, demo_session)
    add_user(demo_session, "outsider@example.com")
    outsider = login(demo_client, "outsider@example.com")
    assert (
        demo_client.get(
            f"{root}/zakat/snapshots/{zakat['id']}/statement.pdf", headers=outsider
        ).status_code
        == 404
    )
    assert (
        demo_client.get(
            f"{root}/tax/snapshots/{tax['id']}/statement.pdf", headers=outsider
        ).status_code
        == 404
    )
    assert demo_client.get(f"{root}/tax/snapshots/{tax['id']}/statement.pdf").status_code == 401


@pytest.mark.parametrize("locale", ["en", "bn"])
def test_pdf_labels_match_the_web_messages(locale: str) -> None:
    """The PDF must read like the web page, so its labels are the same text."""
    path = MESSAGES / f"{locale}.json"
    if not path.exists():
        pytest.skip("frontend messages are not in this checkout")
    enum = json.loads(path.read_text(encoding="utf-8"))["personal"]["enum"]
    for group, labels in ENUM_LABELS[locale].items():
        assert labels == enum[group], group
    common = json.loads(path.read_text(encoding="utf-8"))["common"]
    assert statements.TEXT[locale]["disclaimer"] == common["disclaimer"]


def test_formatting_worked_examples() -> None:
    assert statements.money(Decimal("1234567.5"), "en") == "Tk 12,34,567.50"
    assert statements.money(Decimal("1234567.5"), "bn") == "৳১২,৩৪,৫৬৭.৫০"
    assert statements.date_text("2026-11-21", "en") == "21 November 2026"
    assert statements.date_text("2026-11-21", "bn") == "২১ নভেম্বর ২০২৬"
    assert statements.pct("33.333", "bn") == "৩৩%"
    assert statements.label("treatment", "FULL", "en") == "Full value"
    assert statements.label("treatment", "NEW_RULE", "en") == "NEW_RULE"
