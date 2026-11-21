"""Households (F24) and daily costs (F12) through the API, on the demo household."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditLog, Expense, HouseholdMember, OwnerShare, User
from app.services import costs
from tests.personal_helpers import API, add_user, base, login, member

D = Decimal


# --- F24 households -------------------------------------------------------------------


def test_owner_sees_their_household_fr24(demo_client: TestClient, demo_session: Session) -> None:
    rows = demo_client.get(f"{API}/households", headers=login(demo_client)).json()
    assert [(r["name"], r["role"]) for r in rows] == [("Rahman family", "OWNER")]
    members = demo_client.get(f"{base(demo_session)}/members", headers=login(demo_client)).json()
    assert {(m["display_name"], m["role"], m["has_login"]) for m in members} == {
        ("Karim Rahman", "OWNER", True),
        ("Ayesha Rahman", "EDITOR", False),
    }
    assert sum(m["is_you"] for m in members) == 1


@pytest.mark.parametrize(
    "path",
    [
        "/members",
        "/expenses",
        "/costs/summary",
        "/accounts",
        "/portfolio/summary",
        "/portfolio/performance",
        "/portfolio/allocation",
        "/alt-assets",
        "/sukuk/holdings",
        "/sukuk/bank-safety",
        "/zakat/snapshots",
        "/tax/snapshots",
        "/fire/plans",
        "/goals",
        "/costs/export.csv",
    ],
)
def test_no_access_to_another_household(
    demo_client: TestClient, demo_session: Session, path: str
) -> None:
    """PRD section 15: no cross-household access. An outsider gets 404, not 403, so the
    household's existence is not revealed."""
    add_user(demo_session, "outsider@example.com")
    outsider = login(demo_client, "outsider@example.com")
    response = demo_client.get(f"{base(demo_session)}{path}", headers=outsider)
    assert response.status_code == 404
    assert response.json() == {"detail": "HOUSEHOLD_NOT_FOUND"}
    assert demo_client.get(f"{base(demo_session)}{path}").status_code == 401


def test_roles_limit_what_a_member_can_do_fr24_2(
    demo_client: TestClient, demo_session: Session
) -> None:
    add_user(demo_session, "viewer@example.com", role="VIEWER")
    add_user(demo_session, "editor@example.com", role="EDITOR")
    viewer, editor = (
        login(demo_client, "viewer@example.com"),
        login(demo_client, "editor@example.com"),
    )
    root = base(demo_session)
    category = demo_client.get(f"{root}/categories", headers=viewer).json()[0]["id"]
    cost = {"date": "2026-11-14", "amount": "250.00", "category_id": category}

    assert demo_client.get(f"{root}/portfolio/summary", headers=viewer).status_code == 200
    refused = demo_client.post(f"{root}/expenses", headers=viewer, json=cost)
    assert (refused.status_code, refused.json()["detail"]) == (403, "HOUSEHOLD_ROLE_REQUIRED")
    assert demo_client.post(f"{root}/expenses", headers=editor, json=cost).status_code == 201
    # Members and roles are the owner's to change.
    new = {"display_name": "Grandmother", "role": "VIEWER"}
    assert demo_client.post(f"{root}/members", headers=editor, json=new).status_code == 403
    assert demo_client.delete(root, headers=editor).status_code == 403


def test_members_can_be_added_linked_and_removed_fr24_1(
    demo_client: TestClient, demo_session: Session
) -> None:
    owner, root = login(demo_client), base(demo_session)
    add_user(demo_session, "spouse@example.com")

    child = demo_client.post(
        f"{root}/members", headers=owner, json={"display_name": "Child", "birth_year": 2015}
    )
    assert child.status_code == 201 and child.json()["has_login"] is False
    linked = demo_client.post(
        f"{root}/members",
        headers=owner,
        json={"display_name": "Spouse", "role": "EDITOR", "email": "Spouse@Example.com"},
    )
    assert linked.status_code == 201 and linked.json()["has_login"] is True
    again = demo_client.post(
        f"{root}/members", headers=owner, json={"display_name": "X", "email": "spouse@example.com"}
    )
    assert (again.status_code, again.json()["detail"]) == (409, "ALREADY_MEMBER")
    unknown = demo_client.post(
        f"{root}/members", headers=owner, json={"display_name": "X", "email": "nobody@example.com"}
    )
    assert unknown.status_code == 404
    # The linked account now sees the shared household (US9).
    spouse = login(demo_client, "spouse@example.com")
    assert demo_client.get(f"{API}/households", headers=spouse).json()[0]["role"] == "EDITOR"

    removed = demo_client.delete(f"{root}/members/{child.json()['id']}", headers=owner)
    assert removed.status_code == 204
    actions = set(demo_session.scalars(select(AuditLog.action)))
    assert {"HOUSEHOLD_MEMBER_ADDED", "HOUSEHOLD_MEMBER_REMOVED"} <= actions


def test_the_last_owner_cannot_leave_or_be_demoted(
    demo_client: TestClient, demo_session: Session
) -> None:
    owner, root = login(demo_client), base(demo_session)
    karim = member(demo_session, "Karim")
    demoted = demo_client.patch(
        f"{root}/members/{karim.id}", headers=owner, json={"role": "EDITOR"}
    )
    assert (demoted.status_code, demoted.json()["detail"]) == (409, "LAST_OWNER")
    assert demo_client.delete(f"{root}/members/{karim.id}", headers=owner).status_code == 409


def test_zakat_date_needs_religious_consent_fr23_2(
    demo_client: TestClient, demo_session: Session
) -> None:
    owner, root = login(demo_client), base(demo_session)
    karim = member(demo_session, "Karim")
    change = {"hawl_date": "2027-03-01", "nisab_basis": "SILVER"}
    ok = demo_client.patch(f"{root}/members/{karim.id}", headers=owner, json=change)
    assert ok.status_code == 200 and ok.json()["nisab_basis"] == "SILVER"

    user = demo_session.scalar(select(User).where(User.email == "demo@example.com"))
    assert user is not None
    user.consents = {**user.consents, "RELIGIOUS_PREFERENCES": {"granted": False, "at": "x"}}
    demo_session.commit()
    refused = demo_client.patch(f"{root}/members/{karim.id}", headers=owner, json=change)
    assert (refused.status_code, refused.json()["detail"]) == (403, "CONSENT_REQUIRED")
    # Other details can still be changed.
    plain = demo_client.patch(
        f"{root}/members/{karim.id}", headers=owner, json={"birth_year": 1987}
    )
    assert plain.status_code == 200


def test_owner_shares_are_validated_and_replaced_fr24_1(
    demo_client: TestClient, demo_session: Session
) -> None:
    owner, root = login(demo_client), base(demo_session)
    karim, ayesha = member(demo_session, "Karim"), member(demo_session, "Ayesha")
    summary = demo_client.get(f"{root}/portfolio/summary", headers=owner).json()["data"]
    cash = next(p for p in summary["positions"] if p["name"] == "Cash at home")
    url = f"{root}/owners/HOLDING/{cash['id']}"

    too_much = [
        {"member_id": str(karim.id), "pct": "70"},
        {"member_id": str(ayesha.id), "pct": "40"},
    ]
    refused = demo_client.put(url, headers=owner, json={"owners": too_much})
    assert (refused.status_code, refused.json()["detail"]) == (422, "OWNER_SHARES_INVALID")
    both = [{"member_id": str(karim.id), "pct": "50"}, {"external_name": "Uncle", "pct": "20"}]
    saved = demo_client.put(url, headers=owner, json={"owners": both})
    assert saved.status_code == 200
    assert sorted(o["pct"] for o in demo_client.get(url, headers=owner).json()) == [
        "20.0000",
        "50.0000",
    ]
    rows = demo_session.scalars(
        select(OwnerShare).where(OwnerShare.asset_id == uuid.UUID(cash["id"]))
    ).all()
    assert len(rows) == 2
    # An outsider's part is not the household's.
    after = demo_client.get(f"{root}/portfolio/summary", headers=owner).json()["data"]
    updated = next(p for p in after["positions"] if p["id"] == cash["id"])
    assert (D(updated["household_pct"]), updated["household_value"]) == (80, "68000.00")


def test_a_new_user_creates_and_deletes_a_household(
    demo_client: TestClient, demo_session: Session
) -> None:
    add_user(demo_session, "new@example.com")
    headers = login(demo_client, "new@example.com")
    assert demo_client.get(f"{API}/households", headers=headers).json() == []
    created = demo_client.post(f"{API}/households", headers=headers, json={"name": " My family "})
    assert created.status_code == 201 and created.json()["name"] == "My family"
    root = f"{API}/households/{created.json()['id']}"
    empty = demo_client.get(f"{root}/portfolio/summary", headers=headers).json()["data"]
    assert (empty["net_worth"], empty["positions"]) == ("0.00", [])
    assert demo_client.delete(root, headers=headers).status_code == 204
    assert demo_client.get(f"{root}/members", headers=headers).status_code == 404
    assert demo_session.scalar(select(func.count()).select_from(HouseholdMember)) == 2


# --- F12 daily costs ------------------------------------------------------------------


def test_default_categories_in_both_languages_fr12_1(
    demo_client: TestClient, demo_session: Session
) -> None:
    rows = demo_client.get(f"{base(demo_session)}/categories", headers=login(demo_client)).json()
    assert len(rows) == 9 and all(r["is_default"] for r in rows)
    assert rows[0] == {**rows[0], "key": "food_bazar", "name_en": "Food and bazar"}
    assert all(r["name_bn"] and r["name_bn"] != r["name_en"] for r in rows)


def test_totals_match_the_sum_of_entries_fr12_ac(
    demo_client: TestClient, demo_session: Session
) -> None:
    owner, root = login(demo_client), base(demo_session)
    summary = demo_client.get(f"{root}/costs/summary?months=24", headers=owner).json()
    data = summary["data"]
    stored = demo_session.scalar(select(func.sum(Expense.amount)))
    assert sum(D(m["total"]) for m in data["months"]) == stored
    assert sum(D(y["total"]) for y in data["years"]) == stored
    for month in data["months"]:
        assert sum(D(v) for v in month["by_category"].values()) == D(month["total"])
    # FR12.4: the trailing 12 months, 16 Nov 2025 to 15 Nov 2026.
    expected = demo_session.scalar(
        select(func.sum(Expense.amount)).where(
            Expense.date > date(2025, 11, 15), Expense.date <= date(2026, 11, 15)
        )
    )
    assert D(data["trailing_12_months"]) == expected
    assert sum(D(c["total"]) for c in data["by_category"]) == expected
    # FR12.3: restated in the latest month's prices, with the CPI source named.
    assert data["price_base_month"] == "2026-11-01"
    first, last = data["months"][0], data["months"][-1]
    assert D(first["real_total"]) > D(first["total"])  # older money bought more
    assert D(last["real_total"]) == D(last["total"])
    assert "Demo data" in summary["sources"][0]["name"] and summary["as_of"]
    assert isinstance(data["months"][0]["total"], str)  # money is never a float


def test_fast_entry_edit_and_delete_fr12_1(demo_client: TestClient, demo_session: Session) -> None:
    owner, root = login(demo_client), base(demo_session)
    rent = next(
        c for c in demo_client.get(f"{root}/categories", headers=owner).json() if c["key"] == "rent"
    )
    before = D(
        demo_client.get(f"{root}/costs/summary", headers=owner).json()["data"]["trailing_12_months"]
    )
    body = {
        "date": "2026-11-14",
        "amount": "1250.50",
        "category_id": rent["id"],
        "note": " Repair ",
    }
    created = demo_client.post(f"{root}/expenses", headers=owner, json=body).json()
    assert (created["amount"], created["note"]) == ("1250.50", "Repair")
    assert created["member_id"] == str(member(demo_session, "Karim").id)  # the person entering it

    def trailing() -> Decimal:
        data = demo_client.get(f"{root}/costs/summary", headers=owner).json()["data"]
        return D(data["trailing_12_months"])

    assert trailing() == before + D("1250.50")
    edited = demo_client.patch(
        f"{root}/expenses/{created['id']}", headers=owner, json={"amount": "1000"}
    )
    assert edited.json()["amount"] == "1000.00" and trailing() == before + 1000
    page = demo_client.get(f"{root}/expenses?start=2026-11-14&end=2026-11-14", headers=owner).json()
    assert created["id"] in {e["id"] for e in page["items"]}
    assert demo_client.delete(f"{root}/expenses/{created['id']}", headers=owner).status_code == 204
    assert trailing() == before

    for bad in ({**body, "amount": "0"}, {**body, "amount": "-5"}, {**body, "amount": "1.999"}):
        assert demo_client.post(f"{root}/expenses", headers=owner, json=bad).status_code == 422
    missing = {**body, "category_id": "00000000-0000-0000-0000-000000000000"}
    assert demo_client.post(f"{root}/expenses", headers=owner, json=missing).status_code == 404


def test_recurring_entries_generate_on_schedule_without_duplicates_fr12_ac(
    demo_client: TestClient, demo_session: Session
) -> None:
    owner, root = login(demo_client), base(demo_session)
    utilities = next(
        c
        for c in demo_client.get(f"{root}/categories", headers=owner).json()
        if c["key"] == "utilities"
    )
    rule = demo_client.post(
        f"{root}/recurring",
        headers=owner,
        json={
            "category_id": utilities["id"],
            "amount": "1500",
            "frequency": "MONTHLY",
            "start_date": "2026-08-31",
            "note": "Internet",
        },
    )
    assert rule.status_code == 201

    def generated() -> list[date]:
        return sorted(
            demo_session.scalars(
                select(Expense.date).where(Expense.recurring_id == uuid.UUID(rule.json()["id"]))
            )
        )

    # Due on 31 Aug, 30 Sep and 31 Oct; 30 Nov is still ahead of "today" (15 Nov).
    assert generated() == [date(2026, 8, 31), date(2026, 9, 30), date(2026, 10, 31)]
    # The daily job running again, any number of times, adds nothing.
    assert costs.generate_recurring(demo_session, date(2026, 11, 15)) == 0
    assert costs.generate_recurring(demo_session, date(2026, 11, 15)) == 0
    assert (
        costs.generate_recurring(demo_session, date(2026, 12, 1)) == 4
    )  # Nov entry + 3 demo rules
    assert generated()[-1] == date(2026, 11, 30)

    stopped = demo_client.patch(
        f"{root}/recurring/{rule.json()['id']}", headers=owner, json={"is_active": False}
    )
    assert stopped.json()["is_active"] is False
    costs.generate_recurring(demo_session, date(2027, 6, 1))
    assert generated()[-1] == date(2026, 11, 30)
    assert len(demo_client.get(f"{root}/recurring", headers=owner).json()) == 4
    bad = {
        "category_id": utilities["id"],
        "amount": "1",
        "frequency": "AT_MATURITY",
        "start_date": "2026-01-01",
    }
    assert demo_client.post(f"{root}/recurring", headers=owner, json=bad).status_code == 422


def test_own_categories_fr12_1(demo_client: TestClient, demo_session: Session) -> None:
    owner, root = login(demo_client), base(demo_session)
    made = demo_client.post(f"{root}/categories", headers=owner, json={"name": "পোষা প্রাণী"})
    assert made.status_code == 201 and made.json()["is_default"] is False
    duplicate = demo_client.post(f"{root}/categories", headers=owner, json={"name": "Rent"})
    assert (duplicate.status_code, duplicate.json()["detail"]) == (409, "CATEGORY_EXISTS")
    demo_client.post(
        f"{root}/expenses",
        headers=owner,
        json={"date": "2026-11-10", "amount": "300", "category_id": made.json()["id"]},
    )
    in_use = demo_client.delete(f"{root}/categories/{made.json()['id']}", headers=owner)
    assert (in_use.status_code, in_use.json()["detail"]) == (409, "CATEGORY_IN_USE")
    defaults = demo_client.get(f"{root}/categories", headers=owner).json()
    assert (
        demo_client.delete(f"{root}/categories/{defaults[0]['id']}", headers=owner).status_code
        == 404
    )


def test_csv_export_and_import_fr12_5(demo_client: TestClient, demo_session: Session) -> None:
    owner, root = login(demo_client), base(demo_session)
    exported = demo_client.get(f"{root}/costs/export.csv", headers=owner)
    assert exported.headers["content-type"].startswith("text/csv")
    lines = exported.text.strip().split("\n")
    assert lines[0] == "date,amount,category,note,member"
    assert len(lines) - 1 == demo_session.scalar(select(func.count()).select_from(Expense))

    before = demo_session.scalar(select(func.count()).select_from(Expense))
    text = (
        "Date,Amount,Category,Note\n"
        '2026-11-01,"1,200.50",food_bazar,Weekly bazar\n'
        "02/11/2026,300,Transport,\n"
        "2026-11-03,abc,rent,bad amount\n"
        "not a date,10,rent,\n"
        "2026-11-04,10,holidays,unknown category\n"
        "2026-11-05,75,স্বাস্থ্য,Bangla category name\n"
    )
    result = demo_client.post(f"{root}/imports/expenses", headers=owner, json={"csv": text}).json()
    assert result["imported"] == 3
    assert result["errors"] == [
        {"row": 4, "code": "BAD_AMOUNT"},
        {"row": 5, "code": "BAD_DATE"},
        {"row": 6, "code": "UNKNOWN_CATEGORY"},
    ]
    assert demo_session.scalar(select(func.count()).select_from(Expense)) == before + 3
    no_header = demo_client.post(
        f"{root}/imports/expenses", headers=owner, json={"csv": "a,b\n1,2"}
    )
    assert (no_header.status_code, no_header.json()["detail"]) == (422, "CSV_HEADER_INVALID")
    # A note that looks like a spreadsheet formula is exported as text.
    food = demo_client.get(f"{root}/categories", headers=owner).json()[0]["id"]
    demo_client.post(
        f"{root}/expenses",
        headers=owner,
        json={"date": "2026-11-06", "amount": "5", "category_id": food, "note": "=HYPERLINK(1)"},
    )
    assert "'=HYPERLINK(1)" in demo_client.get(f"{root}/costs/export.csv", headers=owner).text
