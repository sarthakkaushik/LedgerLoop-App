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


@pytest.mark.asyncio
async def test_family_members_bootstrap_create_and_expense_attribution(client: AsyncClient) -> None:
    from app.main import app

    app.dependency_overrides[get_expense_parser] = lambda: FakeParser()
    try:
        token = await register_user(client, "family.admin@example.com", "Family Profiles Home")
        headers = {"Authorization": f"Bearer {token}"}

        members_res = await client.get("/family-members", headers=headers)
        assert members_res.status_code == 200
        members = members_res.json()["items"]
        assert len(members) == 1
        assert members[0]["member_type"] == "adult"
        assert members[0]["linked_user_id"] is not None

        create_child_res = await client.post(
            "/family-members",
            headers=headers,
            json={
                "full_name": "Aarav",
                "member_type": "child",
            },
        )
        assert create_child_res.status_code == 201
        child = create_child_res.json()
        child_id = child["id"]
        assert child["member_type"] == "child"

        log_res = await client.post(
            "/expenses/log",
            headers=headers,
            json={"text": "Bought school books"},
        )
        assert log_res.status_code == 200
        draft_id = log_res.json()["expenses"][0]["id"]
        assert draft_id

        confirm_res = await client.post(
            "/expenses/confirm",
            headers=headers,
            json={
                "idempotency_key": "family-member-attribution-001",
                "expenses": [
                    {
                        "draft_id": draft_id,
                        "amount": 420.0,
                        "category": "Education",
                        "date_incurred": str(date.today()),
                        "attributed_family_member_id": child_id,
                    }
                ],
            },
        )
        assert confirm_res.status_code == 200
        confirm_payload = confirm_res.json()
        assert confirm_payload["confirmed_count"] == 1
        assert confirm_payload["expenses"][0]["attributed_family_member_id"] == child_id
        assert confirm_payload["expenses"][0]["attributed_family_member_name"] == "Aarav"

        list_res = await client.get("/expenses/list?status=confirmed", headers=headers)
        assert list_res.status_code == 200
        listed_item = list_res.json()["items"][0]
        assert listed_item["attributed_family_member_id"] == child_id
        assert listed_item["attributed_family_member_name"] == "Aarav"
        assert listed_item["attributed_family_member_type"] == "child"

        dashboard_res = await client.get("/expenses/dashboard?months_back=1", headers=headers)
        assert dashboard_res.status_code == 200
        family_split = dashboard_res.json()["family_member_split"]
        assert len(family_split) >= 1
        assert family_split[0]["family_member_name"] == "Aarav"
        assert family_split[0]["total"] == 420.0

        deactivate_res = await client.delete(f"/family-members/{child_id}", headers=headers)
        assert deactivate_res.status_code == 200

        update_res = await client.patch(
            f"/expenses/{listed_item['id']}",
            headers=headers,
            json={
                "amount": 421.0,
                "attributed_family_member_id": child_id,
            },
        )
        assert update_res.status_code == 422
    finally:
        app.dependency_overrides.pop(get_expense_parser, None)
