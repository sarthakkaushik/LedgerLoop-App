from datetime import date
from uuid import uuid4

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
            "full_name": "member",
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
    idempotency_key: str,
) -> str:
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
                    "category": "Other",
                    "date_incurred": str(date.today()),
                }
            ],
        },
    )
    assert confirm_res.status_code == 200
    return confirm_res.json()["expenses"][0]["id"]


@pytest.mark.asyncio
async def test_update_expense_requires_auth(client: AsyncClient) -> None:
    response = await client.patch(
        f"/expenses/{uuid4()}",
        json={"amount": 250},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_user_can_update_own_expense(client: AsyncClient) -> None:
    from app.main import app

    app.dependency_overrides[get_expense_parser] = lambda: FakeParser()
    try:
        token = await register_user(client, "update.owner@example.com", "Update Home")
        expense_id = await log_and_confirm_expense(
            client=client,
            token=token,
            text="Owner expense",
            amount=250.0,
            idempotency_key="update-own-1",
        )

        update_res = await client.patch(
            f"/expenses/{expense_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "amount": 399.5,
                "currency": "inr",
                "category": "Other",
                "subcategory": "",
                "description": "Updated note",
                "date_incurred": str(date.today()),
            },
        )
        assert update_res.status_code == 200
        payload = update_res.json()
        assert payload["item"]["id"] == expense_id
        assert payload["item"]["amount"] == 399.5
        assert payload["item"]["currency"] == "INR"
        assert payload["item"]["description"] == "Updated note"
        assert payload["item"]["subcategory"] is None

        list_res = await client.get(
            "/expenses/list?status=all",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert list_res.status_code == 200
        items = list_res.json()["items"]
        matched = next(item for item in items if item["id"] == expense_id)
        assert matched["amount"] == 399.5
        assert matched["description"] == "Updated note"
    finally:
        app.dependency_overrides.pop(get_expense_parser, None)


@pytest.mark.asyncio
async def test_member_cannot_update_other_members_expense(client: AsyncClient) -> None:
    from app.main import app

    app.dependency_overrides[get_expense_parser] = lambda: FakeParser()
    try:
        admin_token = await register_user(client, "update.admin@example.com", "Update Family")
        invite_res = await client.post(
            "/auth/invite",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert invite_res.status_code == 200
        member_token = await join_household(
            client,
            invite_code=invite_res.json()["invite_code"],
            email="update.member@example.com",
        )

        expense_id = await log_and_confirm_expense(
            client=client,
            token=admin_token,
            text="Admin expense",
            amount=300.0,
            idempotency_key="update-forbidden-1",
        )

        update_res = await client.patch(
            f"/expenses/{expense_id}",
            headers={"Authorization": f"Bearer {member_token}"},
            json={"amount": 450},
        )
        assert update_res.status_code == 403
    finally:
        app.dependency_overrides.pop(get_expense_parser, None)


@pytest.mark.asyncio
async def test_admin_can_update_household_member_expense(client: AsyncClient) -> None:
    from app.main import app

    app.dependency_overrides[get_expense_parser] = lambda: FakeParser()
    try:
        admin_token = await register_user(client, "update.admin2@example.com", "Update Family Two")
        invite_res = await client.post(
            "/auth/invite",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert invite_res.status_code == 200
        member_token = await join_household(
            client,
            invite_code=invite_res.json()["invite_code"],
            email="update.member2@example.com",
        )

        expense_id = await log_and_confirm_expense(
            client=client,
            token=member_token,
            text="Member expense",
            amount=450.0,
            idempotency_key="update-admin-1",
        )

        update_res = await client.patch(
            f"/expenses/{expense_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"amount": 520.0, "description": "Admin corrected entry"},
        )
        assert update_res.status_code == 200
        payload = update_res.json()
        assert payload["item"]["id"] == expense_id
        assert payload["item"]["amount"] == 520.0
        assert payload["item"]["description"] == "Admin corrected entry"
    finally:
        app.dependency_overrides.pop(get_expense_parser, None)
