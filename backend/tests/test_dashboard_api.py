from datetime import date

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
                    currency="INR",
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


async def join_household(
    client: AsyncClient,
    invite_code: str,
    email: str,
) -> str:
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
async def test_dashboard_aggregates_and_household_isolation(client: AsyncClient) -> None:
    from app.main import app

    app.dependency_overrides[get_expense_parser] = lambda: FakeParser()
    try:
        admin_token = await register_user(client, "admin@family.com", "Family A")
        invite_res = await client.post(
            "/auth/invite",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert invite_res.status_code == 200
        spouse_token = await join_household(
            client,
            invite_code=invite_res.json()["invite_code"],
            email="spouse@family.com",
        )

        other_household_token = await register_user(
            client,
            "other@family.com",
            "Family B",
        )

        today = date.today()
        month_start = today.replace(day=1)
        if month_start.month == 1:
            previous_month_day = month_start.replace(
                year=month_start.year - 1, month=12, day=15
            )
        else:
            previous_month_day = month_start.replace(month=month_start.month - 1, day=15)

        await log_and_confirm_expense(
            client,
            admin_token,
            "Paid groceries",
            amount=300.0,
            category="Groceries",
            date_incurred=today,
            idempotency_key="admin-current",
        )
        await log_and_confirm_expense(
            client,
            spouse_token,
            "Paid electricity bill",
            amount=700.0,
            category="Bills",
            date_incurred=today,
            idempotency_key="spouse-current",
        )
        await log_and_confirm_expense(
            client,
            admin_token,
            "Last month outing",
            amount=250.0,
            category="Dining",
            date_incurred=previous_month_day,
            idempotency_key="admin-previous-month",
        )
        await log_and_confirm_expense(
            client,
            other_household_token,
            "Other household spend",
            amount=999.0,
            category="Travel",
            date_incurred=today,
            idempotency_key="other-current",
        )

        dash_res = await client.get(
            "/expenses/dashboard?months_back=3",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert dash_res.status_code == 200
        data = dash_res.json()

        assert data["total_spend"] == 1000.0
        assert data["expense_count"] == 2
        assert len(data["daily_burn"]) >= 1
        assert [item["category"] for item in data["category_split"]] == ["Bills", "Groceries"]
        assert len(data["user_split"]) == 2
        assert len(data["family_member_split"]) == 2
        assert data["monthly_trend"][-1]["total"] == 1000.0
        assert data["monthly_trend"][-2]["total"] == 250.0
    finally:
        app.dependency_overrides.pop(get_expense_parser, None)


@pytest.mark.asyncio
async def test_dashboard_materializes_recurring_expense_for_new_month(client: AsyncClient) -> None:
    token = await register_user(
        client,
        "recurring.materialize@example.com",
        "Family Recurring Materialize",
    )
    headers = {"Authorization": f"Bearer {token}"}

    today = date.today()
    month_start = today.replace(day=1)
    if month_start.month == 1:
        previous_month_date = month_start.replace(
            year=month_start.year - 1, month=12, day=15
        )
    else:
        previous_month_date = month_start.replace(month=month_start.month - 1, day=15)

    recurring_create_res = await client.post(
        "/expenses/recurring",
        headers=headers,
        json={
            "amount": 1800.0,
            "currency": "INR",
            "category": "Bills",
            "description": "Monthly Rent",
            "merchant_or_item": "Landlord",
            "date_incurred": str(previous_month_date),
        },
    )
    assert recurring_create_res.status_code == 201

    dashboard_res = await client.get(
        "/expenses/dashboard?months_back=2",
        headers=headers,
    )
    assert dashboard_res.status_code == 200
    dashboard_payload = dashboard_res.json()
    assert dashboard_payload["total_spend"] == 1800.0
    assert dashboard_payload["expense_count"] == 1
    assert dashboard_payload["monthly_trend"][-1]["total"] == 1800.0
    assert dashboard_payload["monthly_trend"][-2]["total"] == 1800.0

    recurring_list_res = await client.get(
        "/expenses/list?status=confirmed&recurring_only=true",
        headers=headers,
    )
    assert recurring_list_res.status_code == 200
    recurring_items = recurring_list_res.json()["items"]
    assert len(recurring_items) == 2
    assert all(item["is_recurring"] is True for item in recurring_items)
