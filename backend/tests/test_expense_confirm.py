import pytest
from httpx import AsyncClient

from app.api.deps import get_expense_parser
from app.services.llm.base import ExpenseParserProvider
from app.services.llm.types import ParseContext, ParseResult, ParsedExpense


async def register_and_get_token(client: AsyncClient, email: str) -> str:
    payload = {
        "email": email,
        "password": "testpass123",
        "full_name": "Test User",
        "household_name": "Test Family",
    }
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 201
    return response.json()["token"]["access_token"]


class FakeParser(ExpenseParserProvider):
    async def parse_expenses(self, text: str, context: ParseContext) -> ParseResult:
        return ParseResult(
            mode="expense",
            expenses=[
                ParsedExpense(
                    amount=800.0,
                    currency="INR",
                    category="Food",
                    description="Dinner",
                    merchant_or_item="Dinner",
                    date_incurred=str(context.reference_date),
                    is_recurring=False,
                    confidence=0.91,
                )
            ],
            needs_clarification=False,
            clarification_questions=[],
        )


@pytest.mark.asyncio
async def test_confirm_expenses_flow_and_idempotency(client: AsyncClient) -> None:
    from app.main import app

    app.dependency_overrides[get_expense_parser] = lambda: FakeParser()
    token = await register_and_get_token(client, "confirmuser@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        log_res = await client.post(
            "/expenses/log",
            json={"text": "Paid 800 for dinner"},
            headers=headers,
        )
        assert log_res.status_code == 200
        draft_id = log_res.json()["expenses"][0]["id"]
        assert draft_id is not None

        confirm_payload = {
            "idempotency_key": "confirm-key-001",
            "expenses": [
                {
                    "draft_id": draft_id,
                    "amount": 750.0,
                    "category": "Dining",
                }
            ],
        }
        confirm_res = await client.post(
            "/expenses/confirm",
            json=confirm_payload,
            headers=headers,
        )
        assert confirm_res.status_code == 200
        confirm_data = confirm_res.json()
        assert confirm_data["idempotent_replay"] is False
        assert confirm_data["confirmed_count"] == 1
        assert confirm_data["expenses"][0]["amount"] == 750.0
        assert confirm_data["expenses"][0]["category"] == "Dining"

        replay_res = await client.post(
            "/expenses/confirm",
            json=confirm_payload,
            headers=headers,
        )
        assert replay_res.status_code == 200
        replay_data = replay_res.json()
        assert replay_data["idempotent_replay"] is True
        assert replay_data["confirmed_count"] == 1
    finally:
        app.dependency_overrides.pop(get_expense_parser, None)
