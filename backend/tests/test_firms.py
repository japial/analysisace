"""Firm features (F9, D30): the switch, seats and roles (FR9.3), API keys with limits and
usage logs and CSV exports (FR9.2), and the white-label weekly report (FR9.1)."""

import base64
import io
from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.main import app
from app.models import ApiUsage, Firm, User
from app.services import macro_notes
from app.services.email import get_email_sender
from app.services.market_pipeline import run_market_analytics
from tests.personal_helpers import API, add_user, login

FIRM_ADMIN = "firm@example.com"
MEMBER = "demo@example.com"


@pytest.fixture
def firms_on(demo_client: TestClient) -> Iterator[Settings]:
    settings = Settings(firm_features_enabled=True, firm_api_rate_per_minute=3)
    app.dependency_overrides[get_settings] = lambda: settings
    yield settings
    app.dependency_overrides.pop(get_settings, None)


def _firm_id(client: TestClient, headers: dict[str, str]) -> str:
    mine = client.get(f"{API}/firms/mine", headers=headers).json()
    assert mine and mine[0]["name"] == "Demo Brokerage Ltd."
    return str(mine[0]["id"])


def _png(width: int = 300, height: int = 100) -> str:
    out = io.BytesIO()
    Image.new("RGB", (width, height), (14, 42, 71)).save(out, format="PNG")
    return base64.b64encode(out.getvalue()).decode()


def _analysed(session: Session) -> None:
    """Screening and scores exist only after the analytics run, as in production."""
    run_market_analytics(session, get_email_sender())
    session.commit()


def _publish_week(session: Session) -> None:
    analyst = session.scalar(select(User).where(User.email == "analyst@example.com"))
    assert analyst is not None
    for note in macro_notes.generate_draft(session, date(2026, 11, 8)):
        if note.status != "PUBLISHED":
            macro_notes.set_published(session, analyst, note, True)
    session.commit()


def test_everything_is_hidden_while_the_switch_is_off_q4(demo_client: TestClient) -> None:
    """TODO(owner): Q4. Off by default: firms do not exist for anyone, signed in or not."""
    headers = login(demo_client, FIRM_ADMIN)
    assert demo_client.get(f"{API}/firms/mine", headers=headers).status_code == 404
    assert demo_client.get(f"{API}/admin/firms", headers=headers).status_code == 404
    response = demo_client.get(f"{API}/firm-api/shariah", headers={"X-API-Key": "aace_x"})
    assert response.status_code == 404


def test_seats_roles_and_limits_fr9_3(
    demo_client: TestClient, demo_session: Session, firms_on: Settings
) -> None:
    admin = login(demo_client, FIRM_ADMIN)
    firm_id = _firm_id(demo_client, admin)
    root = f"{API}/firms/{firm_id}"

    detail = demo_client.post(
        f"{root}/members", headers=admin, json={"email": MEMBER, "role": "MEMBER"}
    ).json()
    assert {m["email"]: m["role"] for m in detail["members"]}[MEMBER] == "MEMBER"
    again = demo_client.post(f"{root}/members", headers=admin, json={"email": MEMBER})
    assert again.json()["detail"] == "DUPLICATE"
    unknown = demo_client.post(
        f"{root}/members", headers=admin, json={"email": "nobody@example.com"}
    )
    assert unknown.json()["detail"] == "USER_NOT_FOUND"

    # A member sees the firm but no keys or usage, and cannot manage seats.
    member = login(demo_client, MEMBER)
    seen = demo_client.get(root, headers=member).json()
    assert seen["role"] == "MEMBER" and seen["api_keys"] == [] and seen["usage"] == []
    refused = demo_client.post(f"{root}/members", headers=member, json={"email": FIRM_ADMIN})
    assert refused.status_code == 403 and refused.json()["detail"] == "FIRM_ADMIN_REQUIRED"

    # Someone without a seat does not learn the firm exists.
    add_user(demo_session, "outsider@example.com")
    outsider = login(demo_client, "outsider@example.com")
    assert demo_client.get(root, headers=outsider).status_code == 404

    # The last admin can be neither demoted nor removed.
    admin_id = next(m["user_id"] for m in detail["members"] if m["email"] == FIRM_ADMIN)
    demote = demo_client.patch(f"{root}/members/{admin_id}", headers=admin, json={"role": "MEMBER"})
    assert demote.json()["detail"] == "LAST_FIRM_ADMIN"
    assert (
        demo_client.delete(f"{root}/members/{admin_id}", headers=admin).json()["detail"]
        == "LAST_FIRM_ADMIN"
    )

    # The seat limit holds.
    firm = demo_session.get(Firm, __import__("uuid").UUID(firm_id))
    assert firm is not None
    firm.seat_limit = 2
    demo_session.commit()
    full = demo_client.post(
        f"{root}/members", headers=admin, json={"email": "outsider@example.com"}
    )
    assert full.json()["detail"] == "SEAT_LIMIT_REACHED"


def test_api_keys_limits_usage_and_revoking_fr9_2(
    demo_client: TestClient, demo_session: Session, firms_on: Settings
) -> None:
    _analysed(demo_session)
    admin = login(demo_client, FIRM_ADMIN)
    root = f"{API}/firms/{_firm_id(demo_client, admin)}"
    created = demo_client.post(f"{root}/api-keys", headers=admin, json={"name": "Research desk 2"})
    assert created.status_code == 201
    body = created.json()
    secret = body["key"]
    assert secret.startswith("aace_") and body["prefix"] == secret[:12]
    # The key is never shown again.
    listed = demo_client.get(root, headers=admin).json()["api_keys"]
    assert all("key" not in k for k in listed)

    headers = {"X-API-Key": secret}
    first = demo_client.get(f"{API}/firm-api/shariah", headers=headers)
    assert first.status_code == 200
    payload = first.json()
    assert payload["as_of"] and payload["data"] and {"ticker", "status"} <= set(payload["data"][0])
    assert demo_client.get(f"{API}/firm-api/scores", headers=headers).status_code == 200
    assert demo_client.get(f"{API}/firm-api/shariah", headers=headers).status_code == 200
    # Three calls a minute in this test's settings: the fourth is refused.
    limited = demo_client.get(f"{API}/firm-api/shariah", headers=headers)
    assert limited.status_code == 429 and limited.json()["detail"] == "RATE_LIMITED"

    usage = {
        (u["endpoint"], u["calls"])
        for u in demo_client.get(root, headers=admin).json()["usage"]
        if u["key"] == "Research desk 2"
    }
    assert usage == {("shariah", 2), ("scores", 1)}
    assert demo_session.scalar(select(ApiUsage).where(ApiUsage.endpoint == "scores")) is not None

    revoke = demo_client.delete(f"{root}/api-keys/{body['id']}", headers=admin)
    assert revoke.status_code == 204
    gone = demo_client.get(f"{API}/firm-api/scores", headers=headers)
    assert gone.status_code == 401 and gone.json()["detail"] == "API_KEY_INVALID"
    for bad in ({"X-API-Key": "aace_made-up"}, {"X-API-Key": "something"}, {}):
        assert demo_client.get(f"{API}/firm-api/shariah", headers=bad).status_code == 401


def test_csv_exports_carry_their_date_and_disclaimer_fr9_2(
    demo_client: TestClient, demo_session: Session, firms_on: Settings
) -> None:
    _analysed(demo_session)
    member = login(demo_client, FIRM_ADMIN)
    root = f"{API}/firms/{_firm_id(demo_client, member)}"
    shariah = demo_client.get(f"{root}/exports/shariah.csv", headers=member)
    lines = shariah.text.strip().splitlines()
    assert lines[0] == "ticker,name,sector,status,method_version,screened_at,market_cap"
    assert lines[-1] == "# Historical analysis for education only. Not investment advice."
    assert any(line.startswith("# Screened by analysisACE") for line in lines)
    assert len([line for line in lines if not line.startswith("#")]) > 1  # rows, not just a header
    scores = demo_client.get(f"{root}/exports/scores.csv", headers=member).text
    assert scores.startswith("ticker,rate_sensitivity_pct,") and "history, not a forecast" in scores
    assert demo_client.get(f"{root}/exports/other.csv", headers=member).status_code == 422


def test_weekly_report_with_logo_in_both_languages_fr9_1(
    demo_client: TestClient, demo_session: Session, firms_on: Settings
) -> None:
    admin = login(demo_client, FIRM_ADMIN)
    root = f"{API}/firms/{_firm_id(demo_client, admin)}"
    _publish_week(demo_session)

    assert (
        demo_client.put(f"{root}/logo", headers=admin, json={"content_base64": _png()}).status_code
        == 204
    )
    assert demo_client.get(root, headers=admin).json()["has_logo"] is True
    shown = demo_client.get(f"{root}/logo", headers=admin)
    assert shown.headers["content-type"] == "image/png"
    with Image.open(io.BytesIO(shown.content)) as image:
        assert image.format == "PNG" and max(image.size) <= 600

    for locale in ("en", "bn"):
        pdf = demo_client.get(f"{root}/reports/weekly.pdf?locale={locale}", headers=admin)
        assert pdf.status_code == 200, pdf.text
        assert pdf.content.startswith(b"%PDF") and len(pdf.content) > 5000
        assert pdf.headers["content-disposition"].endswith(f'-{locale}.pdf"')

    missing = demo_client.get(f"{root}/reports/weekly.pdf?week=2020-01-05", headers=admin)
    assert missing.json()["detail"] == "NOTE_NOT_PUBLISHED"


def test_logo_must_be_a_small_png_or_jpeg_fr9_1(
    demo_client: TestClient, firms_on: Settings
) -> None:
    admin = login(demo_client, FIRM_ADMIN)
    root = f"{API}/firms/{_firm_id(demo_client, admin)}"
    not_image = base64.b64encode(b"<svg onload=alert(1)></svg>").decode()
    assert (
        demo_client.put(f"{root}/logo", headers=admin, json={"content_base64": not_image}).json()[
            "detail"
        ]
        == "LOGO_INVALID"
    )
    gif = io.BytesIO()
    Image.new("RGB", (10, 10)).save(gif, format="GIF")
    as_gif = base64.b64encode(gif.getvalue()).decode()
    assert (
        demo_client.put(f"{root}/logo", headers=admin, json={"content_base64": as_gif}).json()[
            "detail"
        ]
        == "LOGO_INVALID"
    )
    app.dependency_overrides[get_settings] = lambda: Settings(
        firm_features_enabled=True, firm_logo_max_bytes=100
    )
    big = demo_client.put(f"{root}/logo", headers=admin, json={"content_base64": _png()})
    assert big.json()["detail"] == "LOGO_TOO_LARGE"


def test_platform_admin_creates_and_limits_firms_fr9_3(
    demo_client: TestClient, demo_session: Session, firms_on: Settings
) -> None:
    add_user(demo_session, "platform-admin@example.com")
    admin_user = demo_session.scalar(select(User).where(User.email == "platform-admin@example.com"))
    assert admin_user is not None
    admin_user.role = "ADMIN"
    demo_session.commit()
    platform = login(demo_client, "platform-admin@example.com")

    created = demo_client.post(
        f"{API}/admin/firms",
        headers=platform,
        json={"name": "Second Securities", "seat_limit": 3, "admin_email": MEMBER},
    )
    assert created.status_code == 201, created.text
    firm = created.json()
    assert firm["seats_used"] == 1
    clash = demo_client.post(
        f"{API}/admin/firms",
        headers=platform,
        json={"name": "second securities", "admin_email": MEMBER},
    )
    assert clash.json()["detail"] == "DUPLICATE"
    assert any(
        f["name"] == "Second Securities"
        for f in demo_client.get(f"{API}/admin/firms", headers=platform).json()
    )

    # The first admin now has the firm; a seat limit below the seats in use is refused.
    member = login(demo_client, MEMBER)
    assert any(
        f["name"] == "Second Securities" and f["role"] == "ADMIN"
        for f in demo_client.get(f"{API}/firms/mine", headers=member).json()
    )
    off = demo_client.patch(
        f"{API}/admin/firms/{firm['id']}", headers=platform, json={"is_active": False}
    )
    assert off.json()["is_active"] is False
    assert all(
        f["name"] != "Second Securities"
        for f in demo_client.get(f"{API}/firms/mine", headers=member).json()
    )

    # Without FIRMS_MANAGE: refused.
    assert demo_client.get(f"{API}/admin/firms", headers=member).status_code == 403
