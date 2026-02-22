import csv
from datetime import date
import io

import pytest
from httpx import AsyncClient

from app.api.deps import get_expense_parser
from app.services.llm.base import ExpenseParserProvider
from app.services.llm.types import ParseContext, ParseResult, ParsedExpense


class FakeParser(ExpenseParserProvider):
    async def parse_expenses(self, text: str, context: ParseContext) -> ParseResult:
        return ParseResult(
            mode="expense",
            expenses=[
                ParsedExpense(
                    amount=100.0,
                    currency=context.default_currency,
                    category="Other",
                    description=text,
                    merchant_or_item="Item",
                    date_incurred=str(context.reference_date),
                    is_recurring=False,
                    confidence=0.9,
                )
            ],
            needs_clarification=False,
            clarification_questions=[],
        )


async def register_user(client: AsyncClient, email: str, household_name: str) -> str:
    response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "testpass123",
            "full_name": email.split("@")[0],
            "household_name": household_name,
        },
    )
    assert response.status_code == 201
    return response.json()["token"]["access_token"]


async def join_household(client: AsyncClient, invite_code: str, email: str) -> str:
    response = await client.post(
        "/auth/join",
        json={
            "email": email,
            "password": "testpass123",
            "full_name": "spouse",
            "invite_code": invite_code,
        },
    )
    assert response.status_code == 201
    return response.json()["token"]["access_token"]


async def log_and_confirm_expense(
    client: AsyncClient,
    token: str,
    text: str,
    amount: float,
    category: str,
    date_incurred: date,
    idempotency_key: str,
    is_recurring: bool = False,
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    log_res = await client.post("/expenses/log", json={"text": text}, headers=headers)
    assert log_res.status_code == 200
    draft_id = log_res.json()["expenses"][0]["id"]
    confirm_res = await client.post(
        "/expenses/confirm",
        headers=headers,
        json={
            "idempotency_key": idempotency_key,
            "expenses": [
                {
                    "draft_id": draft_id,
                    "amount": amount,
                    "category": category,
                    "date_incurred": str(date_incurred),
                    "is_recurring": is_recurring,
                }
            ],
        },
    )
    assert confirm_res.status_code == 200


@pytest.mark.asyncio
async def test_expense_list_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/expenses/list")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_expense_export_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/expenses/export.csv")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_expense_list_is_household_scoped_with_logged_by(client: AsyncClient) -> None:
    from app.main import app

    app.dependency_overrides[get_expense_parser] = lambda: FakeParser()
    try:
        admin_token = await register_user(client, "admin.list@example.com", "Family A")
        invite_res = await client.post(
            "/auth/invite",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert invite_res.status_code == 200
        spouse_token = await join_household(
            client,
            invite_code=invite_res.json()["invite_code"],
            email="spouse.list@example.com",
        )
        other_token = await register_user(client, "other.list@example.com", "Family B")

        today = date.today()
        await log_and_confirm_expense(
            client,
            admin_token,
            "Admin groceries",
            amount=300.0,
            category="Groceries",
            date_incurred=today,
            idempotency_key="list-admin-1",
        )
        await log_and_confirm_expense(
            client,
            spouse_token,
            "Spouse bills",
            amount=500.0,
            category="Bills",
            date_incurred=today,
            idempotency_key="list-spouse-1",
        )
        await log_and_confirm_expense(
            client,
            other_token,
            "Other family expense",
            amount=999.0,
            category="Travel",
            date_incurred=today,
            idempotency_key="list-other-1",
        )

        response = await client.get(
            "/expenses/list?status=confirmed",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["total_count"] == 2
        assert len(payload["items"]) == 2

        names = {item["logged_by_name"] for item in payload["items"]}
        assert "admin.list" in names
        assert "spouse" in names
        assert "other.list" not in names
        assert all(item["attributed_family_member_name"] for item in payload["items"])
        assert all(item["status"] == "confirmed" for item in payload["items"])
    finally:
        app.dependency_overrides.pop(get_expense_parser, None)


@pytest.mark.asyncio
async def test_expense_export_csv_respects_filter_and_household(client: AsyncClient) -> None:
    from app.main import app

    app.dependency_overrides[get_expense_parser] = lambda: FakeParser()
    try:
        admin_token = await register_user(client, "admin.csv@example.com", "Family CSV A")
        invite_res = await client.post(
            "/auth/invite",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert invite_res.status_code == 200
        spouse_token = await join_household(
            client,
            invite_code=invite_res.json()["invite_code"],
            email="spouse.csv@example.com",
        )
        other_token = await register_user(client, "other.csv@example.com", "Family CSV B")

        today = date.today()
        await log_and_confirm_expense(
            client,
            admin_token,
            "Admin csv groceries",
            amount=300.0,
            category="Groceries",
            date_incurred=today,
            idempotency_key="csv-admin-1",
        )
        await log_and_confirm_expense(
            client,
            spouse_token,
            "Spouse csv bills",
            amount=500.0,
            category="Bills",
            date_incurred=today,
            idempotency_key="csv-spouse-1",
        )
        await log_and_confirm_expense(
            client,
            other_token,
            "Other csv travel",
            amount=999.0,
            category="Travel",
            date_incurred=today,
            idempotency_key="csv-other-1",
        )
        draft_res = await client.post(
            "/expenses/log",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"text": "Draft csv expense"},
        )
        assert draft_res.status_code == 200

        confirmed_export = await client.get(
            "/expenses/export.csv?status=confirmed",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert confirmed_export.status_code == 200
        assert "text/csv" in confirmed_export.headers.get("content-type", "")
        assert "attachment;" in confirmed_export.headers.get("content-disposition", "")
        confirmed_rows = list(csv.DictReader(io.StringIO(confirmed_export.text)))
        assert len(confirmed_rows) == 2
        assert {row["status"] for row in confirmed_rows} == {"confirmed"}
        assert "other.csv" not in {row["logged_by"] for row in confirmed_rows}

        all_export = await client.get(
            "/expenses/export.csv?status=all",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert all_export.status_code == 200
        all_rows = list(csv.DictReader(io.StringIO(all_export.text)))
        assert len(all_rows) == 3
        assert {row["status"] for row in all_rows} == {"confirmed", "draft"}
    finally:
        app.dependency_overrides.pop(get_expense_parser, None)


@pytest.mark.asyncio
async def test_expense_list_all_status_includes_drafts(client: AsyncClient) -> None:
    from app.main import app

    app.dependency_overrides[get_expense_parser] = lambda: FakeParser()
    try:
        token = await register_user(client, "status.list@example.com", "Family Status")
        today = date.today()
        await log_and_confirm_expense(
            client,
            token,
            "Confirmed expense",
            amount=111.0,
            category="Groceries",
            date_incurred=today,
            idempotency_key="status-confirmed-1",
        )
        log_only_res = await client.post(
            "/expenses/log",
            headers={"Authorization": f"Bearer {token}"},
            json={"text": "Draft-only expense"},
        )
        assert log_only_res.status_code == 200

        confirmed_res = await client.get(
            "/expenses/list?status=confirmed",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert confirmed_res.status_code == 200
        assert confirmed_res.json()["total_count"] == 1

        all_res = await client.get(
            "/expenses/list?status=all",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert all_res.status_code == 200
        all_payload = all_res.json()
        assert all_payload["total_count"] == 2
        statuses = {item["status"] for item in all_payload["items"]}
        assert "confirmed" in statuses
        assert "draft" in statuses
    finally:
        app.dependency_overrides.pop(get_expense_parser, None)


@pytest.mark.asyncio
async def test_expense_list_recurring_only_filter(client: AsyncClient) -> None:
    from app.main import app

    app.dependency_overrides[get_expense_parser] = lambda: FakeParser()
    try:
        token = await register_user(client, "recurring.list@example.com", "Family Recurring")
        today = date.today()

        await log_and_confirm_expense(
            client,
            token,
            "One-time groceries",
            amount=250.0,
            category="Groceries",
            date_incurred=today,
            idempotency_key="recurring-filter-1",
            is_recurring=False,
        )
        await log_and_confirm_expense(
            client,
            token,
            "Monthly rent",
            amount=1800.0,
            category="Bills",
            date_incurred=today,
            idempotency_key="recurring-filter-2",
            is_recurring=True,
        )

        recurring_res = await client.get(
            "/expenses/list?status=confirmed&recurring_only=true",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert recurring_res.status_code == 200
        payload = recurring_res.json()
        assert payload["total_count"] == 1
        assert len(payload["items"]) == 1
        assert payload["items"][0]["is_recurring"] is True
    finally:
        app.dependency_overrides.pop(get_expense_parser, None)


@pytest.mark.asyncio
async def test_create_recurring_expense_endpoint(client: AsyncClient) -> None:
    token = await register_user(client, "recurring.create@example.com", "Family Recurring Create")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = await client.post(
        "/expenses/recurring",
        headers=headers,
        json={
            "amount": 2200.0,
            "currency": "INR",
            "category": "Bills",
            "description": "School fee",
            "merchant_or_item": "School",
            "date_incurred": str(date.today()),
        },
    )
    assert create_res.status_code == 201
    created_payload = create_res.json()
    item = created_payload["item"]
    assert item["is_recurring"] is True
    assert item["status"] == "confirmed"
    assert item["amount"] == 2200.0

    list_res = await client.get(
        "/expenses/list?status=confirmed&recurring_only=true",
        headers=headers,
    )
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == item["id"]


@pytest.mark.asyncio
async def test_update_expense_recurring_flag(client: AsyncClient) -> None:
    from app.main import app

    app.dependency_overrides[get_expense_parser] = lambda: FakeParser()
    try:
        token = await register_user(client, "recurring.toggle@example.com", "Family Recurring Toggle")
        headers = {"Authorization": f"Bearer {token}"}
        today = date.today()

        await log_and_confirm_expense(
            client,
            token,
            "Water bill",
            amount=600.0,
            category="Bills",
            date_incurred=today,
            idempotency_key="recurring-toggle-1",
            is_recurring=False,
        )

        list_res = await client.get("/expenses/list?status=confirmed", headers=headers)
        assert list_res.status_code == 200
        expense_id = list_res.json()["items"][0]["id"]

        patch_res = await client.patch(
            f"/expenses/{expense_id}/recurring",
            headers=headers,
            json={"is_recurring": True},
        )
        assert patch_res.status_code == 200
        patched_item = patch_res.json()["item"]
        assert patched_item["is_recurring"] is True

        recurring_res = await client.get(
            "/expenses/list?status=confirmed&recurring_only=true",
            headers=headers,
        )
        assert recurring_res.status_code == 200
        recurring_items = recurring_res.json()["items"]
        assert len(recurring_items) == 1
        assert recurring_items[0]["id"] == expense_id
    finally:
        app.dependency_overrides.pop(get_expense_parser, None)
