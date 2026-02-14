from datetime import date

import pytest
from httpx import AsyncClient

from app.api.deps import get_expense_parser
from app.api.analysis import HOUSEHOLD_CTE, _safe_sql
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


async def register_user(
    client: AsyncClient,
    email: str,
    household_name: str,
) -> str:
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


async def log_and_confirm_expense(
    client: AsyncClient,
    token: str,
    text: str,
    amount: float,
    category: str,
    date_incurred: date,
    idempotency_key: str,
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
                }
            ],
        },
    )
    assert confirm_res.status_code == 200


@pytest.mark.asyncio
async def test_analysis_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/analysis/ask", json={"text": "How much this month?"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_analysis_chat_mode(client: AsyncClient) -> None:
    token = await register_user(client, "chat-analysis@example.com", "Family Chat")
    response = await client.post(
        "/analysis/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": "Hello there"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "chat"
    assert payload["route"] == "chat"
    assert payload["tool"] == "chat"
    assert payload["table"] is None


@pytest.mark.asyncio
async def test_analysis_general_question_routes_to_chat(client: AsyncClient) -> None:
    token = await register_user(client, "general-chat-analysis@example.com", "Family Chat 2")
    response = await client.post(
        "/analysis/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": "What is compound interest?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "chat"
    assert payload["route"] == "chat"
    assert payload["tool"] == "chat"


@pytest.mark.asyncio
async def test_analysis_summary_is_household_scoped(client: AsyncClient) -> None:
    from app.main import app

    app.dependency_overrides[get_expense_parser] = lambda: FakeParser()
    try:
        token_a = await register_user(client, "housea@example.com", "Family A")
        token_b = await register_user(client, "houseb@example.com", "Family B")
        today = date.today()

        await log_and_confirm_expense(
            client,
            token_a,
            "Spent on groceries",
            amount=325.0,
            category="Groceries",
            date_incurred=today,
            idempotency_key="house-a-1",
        )
        await log_and_confirm_expense(
            client,
            token_b,
            "Other household spend",
            amount=999.0,
            category="Travel",
            date_incurred=today,
            idempotency_key="house-b-1",
        )

        response = await client.post(
            "/analysis/ask",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"text": "How much did we spend this month?"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["mode"] == "analytics"
        assert payload["route"] == "fixed"
        assert payload["tool"] == "summary"
        assert payload["table"]["columns"] == [
            "Period",
            "Confirmed Expenses",
            "Total",
            "Average",
        ]
        assert payload["table"]["rows"][0][1] == 1
        assert payload["table"]["rows"][0][2] == 325.0
    finally:
        app.dependency_overrides.pop(get_expense_parser, None)


@pytest.mark.asyncio
async def test_analysis_monthly_trend_returns_window(client: AsyncClient) -> None:
    from app.main import app

    app.dependency_overrides[get_expense_parser] = lambda: FakeParser()
    try:
        token = await register_user(client, "trend@example.com", "Family Trend")
        today = date.today()

        await log_and_confirm_expense(
            client,
            token,
            "Spent on rent",
            amount=1200.0,
            category="Rent",
            date_incurred=today,
            idempotency_key="trend-001",
        )
        response = await client.post(
            "/analysis/ask",
            headers={"Authorization": f"Bearer {token}"},
            json={"text": "Show monthly trend for last 3 months"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["tool"] == "monthly_trend"
        assert payload["route"] == "fixed"
        assert payload["chart"]["chart_type"] == "line"
        assert len(payload["chart"]["points"]) == 3
    finally:
        app.dependency_overrides.pop(get_expense_parser, None)


@pytest.mark.asyncio
async def test_analysis_top_expenses_respects_word_number(client: AsyncClient) -> None:
    from app.main import app

    app.dependency_overrides[get_expense_parser] = lambda: FakeParser()
    try:
        token = await register_user(client, "top-three@example.com", "Family Top Three")
        today = date.today()
        await log_and_confirm_expense(
            client,
            token,
            "Expense one",
            amount=900.0,
            category="Shopping",
            date_incurred=today,
            idempotency_key="top-three-1",
        )
        await log_and_confirm_expense(
            client,
            token,
            "Expense two",
            amount=700.0,
            category="Groceries",
            date_incurred=today,
            idempotency_key="top-three-2",
        )
        await log_and_confirm_expense(
            client,
            token,
            "Expense three",
            amount=500.0,
            category="Transport",
            date_incurred=today,
            idempotency_key="top-three-3",
        )
        await log_and_confirm_expense(
            client,
            token,
            "Expense four",
            amount=300.0,
            category="Food",
            date_incurred=today,
            idempotency_key="top-three-4",
        )

        response = await client.post(
            "/analysis/ask",
            headers={"Authorization": f"Bearer {token}"},
            json={"text": "Show top three expenses in last one month"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["tool"] == "top_expenses"
        assert payload["route"] == "fixed"
        assert len(payload["table"]["rows"]) == 3, payload
        amounts = [row[1] for row in payload["table"]["rows"]]
        assert amounts == sorted(amounts, reverse=True)
    finally:
        app.dependency_overrides.pop(get_expense_parser, None)


@pytest.mark.asyncio
async def test_analysis_agent_fallback_route(client: AsyncClient) -> None:
    from app.main import app

    app.dependency_overrides[get_expense_parser] = lambda: FakeParser()
    try:
        token = await register_user(client, "agent-route@example.com", "Family Agent")
        today = date.today()
        await log_and_confirm_expense(
            client,
            token,
            "Paid grocery bill",
            amount=450.0,
            category="Groceries",
            date_incurred=today,
            idempotency_key="agent-route-1",
        )
        response = await client.post(
            "/analysis/ask",
            headers={"Authorization": f"Bearer {token}"},
            json={"text": "Are groceries increasing compared to bills?"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["mode"] == "analytics"
        assert payload["route"] == "agent"
        assert payload["tool"] == "adhoc_sql"
        assert payload["sql"] is not None
        assert len(payload["tool_trace"]) >= 1
    finally:
        app.dependency_overrides.pop(get_expense_parser, None)


def test_safe_sql_blocks_dangerous_statements() -> None:
    ok, _ = _safe_sql("DELETE FROM household_expenses")
    assert ok is False

    ok, _ = _safe_sql("SELECT * FROM users")
    assert ok is False

    ok, _ = _safe_sql("SELECT category, SUM(amount) FROM household_expenses GROUP BY category")
    assert ok is True


def test_household_cte_casts_status_to_text() -> None:
    assert "CAST(e.status AS TEXT) AS status" in HOUSEHOLD_CTE
