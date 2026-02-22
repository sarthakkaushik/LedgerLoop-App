from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from app.api.deps import get_expense_parser
from app.services.llm.base import ExpenseParserProvider
from app.services.llm.types import ParseContext, ParseResult, ParsedExpense


async def register_and_get_token(
    client: AsyncClient,
    email: str,
    *,
    full_name: str = "Test User",
) -> str:
    payload = {
        "email": email,
        "password": "testpass123",
        "full_name": full_name,
        "household_name": "Test Family",
    }
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 201
    return response.json()["token"]["access_token"]


class FakeParser(ExpenseParserProvider):
    async def parse_expenses(self, text: str, context: ParseContext) -> ParseResult:
        if "no amount" in text:
            return ParseResult(
                expenses=[],
                mode="expense",
                needs_clarification=True,
                clarification_questions=["Please provide the amount spent."],
            )

        return ParseResult(
            expenses=[
                ParsedExpense(
                    amount=500.0,
                    currency=context.default_currency,
                    category="Groceries",
                    description="Groceries purchase",
                    merchant_or_item="groceries",
                    date_incurred=str(context.reference_date - timedelta(days=1)),
                    is_recurring=False,
                    confidence=0.95,
                )
            ],
            mode="expense",
            needs_clarification=False,
            clarification_questions=[],
        )


class FakeChatParser(ExpenseParserProvider):
    async def parse_expenses(self, text: str, context: ParseContext) -> ParseResult:
        return ParseResult(
            mode="chat",
            assistant_message="Hello. Ask me to log expenses or answer budget questions.",
            expenses=[],
            needs_clarification=False,
            clarification_questions=[],
        )


class FakeParserWithMemberHint(ExpenseParserProvider):
    async def parse_expenses(self, text: str, context: ParseContext) -> ParseResult:
        return ParseResult(
            expenses=[
                ParsedExpense(
                    amount=250.0,
                    currency=context.default_currency,
                    attributed_family_member_name="Pooja",
                    category="Food",
                    description="Lunch",
                    merchant_or_item="Cafe",
                    date_incurred=str(context.reference_date),
                    is_recurring=False,
                    confidence=0.93,
                )
            ],
            mode="expense",
            needs_clarification=False,
            clarification_questions=[],
        )


@pytest.mark.asyncio
async def test_expense_log_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/expenses/log", json={"text": "spent 200 on food"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_expense_log_parses_draft_and_persists(client: AsyncClient) -> None:
    from app.main import app

    app.dependency_overrides[get_expense_parser] = lambda: FakeParser()
    token = await register_and_get_token(client, "draftuser@example.com")
    try:
        response = await client.post(
            "/expenses/log",
            json={"text": "Bought groceries for 500 yesterday"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["mode"] == "expense"
        assert payload["needs_clarification"] is False
        assert len(payload["expenses"]) == 1
        assert payload["expenses"][0]["id"] is not None
        assert payload["expenses"][0]["amount"] == 500.0
        assert payload["expenses"][0]["category"] == "Groceries"
        assert payload["expenses"][0]["date_incurred"] == str(
            date.today() - timedelta(days=1)
        )
    finally:
        app.dependency_overrides.pop(get_expense_parser, None)


@pytest.mark.asyncio
async def test_expense_log_clarification_flow(client: AsyncClient) -> None:
    from app.main import app

    app.dependency_overrides[get_expense_parser] = lambda: FakeParser()
    token = await register_and_get_token(client, "clarifyuser@example.com")
    try:
        response = await client.post(
            "/expenses/log",
            json={"text": "no amount here"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["mode"] == "expense"
        assert payload["needs_clarification"] is True
        assert payload["expenses"] == []
        assert len(payload["clarification_questions"]) == 1
    finally:
        app.dependency_overrides.pop(get_expense_parser, None)


@pytest.mark.asyncio
async def test_expense_log_general_chat_response(client: AsyncClient) -> None:
    from app.main import app

    app.dependency_overrides[get_expense_parser] = lambda: FakeChatParser()
    token = await register_and_get_token(client, "chatuser@example.com")
    try:
        response = await client.post(
            "/expenses/log",
            json={"text": "Hi there, what can you do?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["mode"] == "chat"
        assert payload["assistant_message"] is not None
        assert payload["expenses"] == []
        assert payload["needs_clarification"] is False
    finally:
        app.dependency_overrides.pop(get_expense_parser, None)


@pytest.mark.asyncio
async def test_expense_log_uses_llm_member_hint_to_assign_belongs_to(client: AsyncClient) -> None:
    from app.main import app

    app.dependency_overrides[get_expense_parser] = lambda: FakeParserWithMemberHint()
    token = await register_and_get_token(
        client,
        "memberhint@example.com",
        full_name="Pooja Sharma",
    )
    try:
        response = await client.post(
            "/expenses/log",
            json={"text": "Pooja spent 250 on lunch"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["mode"] == "expense"
        assert len(payload["expenses"]) == 1
        assert payload["expenses"][0]["attributed_family_member_name"] == "Pooja Sharma"
        assert payload["expenses"][0]["attributed_family_member_type"] == "adult"
    finally:
        app.dependency_overrides.pop(get_expense_parser, None)
