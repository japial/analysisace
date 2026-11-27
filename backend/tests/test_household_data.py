"""Export and deletion cover the personal finance tables (FR23.4)."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.trading_calendar import TradingCalendar
from app.models import (
    Account,
    AltAsset,
    Company,
    Expense,
    Holding,
    Household,
    HouseholdMember,
    OwnerShare,
    PriceDaily,
    User,
    Valuation,
    Watchlist,
)
from app.seed.demo_market import seed_demo_market
from app.seed.demo_personal import DEMO_EMAIL, seed_demo_personal
from app.services.auth import register_user

PASSWORD = "demo-pass-1234"


def seed(session: Session, calendar: TradingCalendar) -> None:
    seed_demo_market(session, calendar)
    seed_demo_personal(session, PASSWORD)
    session.commit()


def headers(client: TestClient, email: str = DEMO_EMAIL) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_export_includes_household_data_without_secrets(
    client: TestClient, session: Session, calendar: TradingCalendar
) -> None:
    seed(session, calendar)
    account = session.scalar(select(Account).where(Account.type == "BO"))
    assert account is not None
    account.encrypted_number = "ciphertext-must-not-leak"
    session.commit()

    response = client.get("/api/v1/me/export", headers=headers(client))
    assert response.status_code == 200
    data = response.json()
    household = data["households"][0]
    assert household["household"]["name"] == "Rahman family"
    assert len(household["holding"]) == 14
    assert len(household["alt_asset"]) == 6
    assert len(household["expense"]) > 700
    assert len(household["owner_share"]) > 14
    assert data["watchlist"] == ["DMFOOD", "DMSTEEL"]
    assert "ciphertext-must-not-leak" not in response.text
    assert "encrypted_number" not in response.text


def test_deleting_the_only_login_removes_the_household_and_keeps_market_data(
    client: TestClient, session: Session, calendar: TradingCalendar
) -> None:
    seed(session, calendar)
    prices_before = count(session, PriceDaily)

    response = client.request(
        "DELETE", "/api/v1/me", headers=headers(client), json={"password": PASSWORD}
    )
    assert response.status_code == 204
    session.expire_all()

    for model in (Household, HouseholdMember, Account, Holding, AltAsset, Expense, Watchlist):
        assert count(session, model) == 0, model.__name__
    # Rows without a foreign key are cleaned up too.
    assert count(session, OwnerShare) == 0
    assert count(session, Valuation) == 0
    # Shared market data and other users are untouched.
    assert count(session, PriceDaily) == prices_before
    assert count(session, Company) == 13
    assert count(session, User) == 2


def test_a_household_shared_with_another_login_survives(
    client: TestClient, session: Session, calendar: TradingCalendar
) -> None:
    seed(session, calendar)
    spouse_user = register_user(
        session,
        email="ayesha@example.com",
        password=PASSWORD,
        full_name="Ayesha Rahman",
        locale="bn",
        accept_terms=True,
    )
    spouse = session.scalar(
        select(HouseholdMember).where(HouseholdMember.display_name == "Ayesha Rahman")
    )
    assert spouse is not None
    spouse.user_id = spouse_user.id
    session.commit()

    response = client.request(
        "DELETE", "/api/v1/me", headers=headers(client), json={"password": PASSWORD}
    )
    assert response.status_code == 204
    session.expire_all()

    assert count(session, Household) == 1
    assert count(session, Holding) == 14
    members = session.scalars(select(HouseholdMember.display_name)).all()
    assert members == ["Ayesha Rahman"]  # the leaver's membership is gone
    # D33: the household is not left without an owner; Ayesha, the remaining login, owns it.
    assert session.scalars(select(HouseholdMember.role)).all() == ["OWNER"]
