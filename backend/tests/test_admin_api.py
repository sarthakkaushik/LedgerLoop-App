import csv
from datetime import date
import io
import zipfile

import pytest
from httpx import AsyncClient

from app.api.deps import get_expense_parser
from app.services.llm.base import ExpenseParserProvider
from app.services.llm.types import ParseContext, ParseResult, ParsedExpense

SUPER_ADMIN_EMAIL = "sarthak.kaushik.17@gmail.com"


class _SingleExpenseParser(ExpenseParserProvider):
    async def parse_expenses(self, text: str, context: ParseContext) -> ParseResult:
        return ParseResult(
            mode="expense",
            expenses=[
                ParsedExpense(
                    amount=100.0,
                    currency=context.default_currency,
                    category="Other",
                    description=text,
                    merchant_or_item="Test Item",
                    date_incurred=str(context.reference_date),
                    is_recurring=False,
                    confidence=0.92,
                )
            ],
            needs_clarification=False,
            clarification_questions=[],
        )


async def register_user(
    client: AsyncClient,
    *,
    email: str,
    household_name: str,
) -> dict:
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
    return response.json()


async def join_user(
    client: AsyncClient,
    *,
    invite_code: str,
    email: str,
) -> dict:
    response = await client.post(
        "/auth/join",
        json={
            "email": email,
            "password": "testpass123",
            "full_name": email.split("@")[0],
            "invite_code": invite_code,
        },
    )
    assert response.status_code == 201
    return response.json()


async def log_and_confirm(
    client: AsyncClient,
    *,
    token: str,
    amount: float,
    idempotency_key: str,
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    log_response = await client.post(
        "/expenses/log",
        json={"text": "Lunch expense"},
        headers=headers,
    )
    assert log_response.status_code == 200
    draft_id = log_response.json()["expenses"][0]["id"]

    confirm_response = await client.post(
        "/expenses/confirm",
        headers=headers,
        json={
            "idempotency_key": idempotency_key,
            "expenses": [
                {
                    "draft_id": draft_id,
                    "amount": amount,
                    "category": "Food",
                    "date_incurred": str(date.today()),
                }
            ],
        },
    )
    assert confirm_response.status_code == 200


@pytest.mark.asyncio
async def test_admin_endpoints_are_email_restricted(client: AsyncClient) -> None:
    blocked_user = await register_user(
        client,
        email="blocked.user@example.com",
        household_name="Blocked Home",
    )
    blocked_token = blocked_user["token"]["access_token"]

    overview_response = await client.get(
        "/admin/overview",
        headers={"Authorization": f"Bearer {blocked_token}"},
    )
    assert overview_response.status_code == 403

    export_response = await client.get(
        "/admin/export/all.zip",
        headers={"Authorization": f"Bearer {blocked_token}"},
    )
    assert export_response.status_code == 403


@pytest.mark.asyncio
async def test_admin_overview_schema_and_export(client: AsyncClient) -> None:
    from app.main import app

    app.dependency_overrides[get_expense_parser] = lambda: _SingleExpenseParser()
    try:
        admin = await register_user(
            client,
            email=SUPER_ADMIN_EMAIL,
            household_name="Admin Home",
        )
        admin_token = admin["token"]["access_token"]

        invite_response = await client.post(
            "/auth/invite",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert invite_response.status_code == 200
        invite_code = invite_response.json()["invite_code"]

        member = await join_user(
            client,
            invite_code=invite_code,
            email="member.analytics@example.com",
        )
        member_token = member["token"]["access_token"]

        member_login = await client.post(
            "/auth/login",
            json={
                "email": "member.analytics@example.com",
                "password": "testpass123",
            },
        )
        assert member_login.status_code == 200

        await register_user(
            client,
            email="other.household@example.com",
            household_name="Other Home",
        )

        await log_and_confirm(
            client,
            token=admin_token,
            amount=120.0,
            idempotency_key="admin-expense-1",
        )
        await log_and_confirm(
            client,
            token=member_token,
            amount=80.0,
            idempotency_key="member-expense-1",
        )
        await log_and_confirm(
            client,
            token=member_token,
            amount=45.0,
            idempotency_key="member-expense-2",
        )

        overview_response = await client.get(
            "/admin/overview",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert overview_response.status_code == 200
        overview = overview_response.json()

        assert overview["total_users"] == 3
        assert overview["total_households"] == 2
        assert overview["total_expenses"] == 3
        assert overview["total_family_members"] >= 2

        users_by_email = {row["email"]: row for row in overview["users"]}
        assert users_by_email[SUPER_ADMIN_EMAIL]["expense_entries_count"] == 1
        assert users_by_email["member.analytics@example.com"]["expense_entries_count"] == 2
        assert users_by_email["other.household@example.com"]["expense_entries_count"] == 0
        assert users_by_email[SUPER_ADMIN_EMAIL]["last_login_at"]
        assert users_by_email["member.analytics@example.com"]["last_login_at"]

        table_rows = {row["table_name"]: row["row_count"] for row in overview["tables"]}
        assert table_rows["users"] == 3
        assert table_rows["expenses"] == 3
        assert table_rows["user_login_events"] >= 4

        schema_response = await client.get(
            "/admin/schema",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert schema_response.status_code == 200
        schema_payload = schema_response.json()
        relation_pairs = {
            (
                relation["from_table"],
                relation["from_column"],
                relation["to_table"],
                relation["to_column"],
            )
            for relation in schema_payload["relations"]
        }
        assert ("expenses", "logged_by_user_id", "users", "id") in relation_pairs
        assert ("users", "household_id", "households", "id") in relation_pairs

        export_all_response = await client.get(
            "/admin/export/all.zip",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert export_all_response.status_code == 200
        archive = zipfile.ZipFile(io.BytesIO(export_all_response.content))
        names = set(archive.namelist())
        assert "users.csv" in names
        assert "expenses.csv" in names
        assert "households.csv" in names

        users_csv = archive.read("users.csv").decode("utf-8")
        users_rows = list(csv.DictReader(io.StringIO(users_csv)))
        assert len(users_rows) == 3
        assert {row["email"] for row in users_rows} == {
            SUPER_ADMIN_EMAIL,
            "member.analytics@example.com",
            "other.household@example.com",
        }

        export_single_response = await client.get(
            "/admin/export/users.csv",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert export_single_response.status_code == 200
        single_rows = list(csv.DictReader(io.StringIO(export_single_response.text)))
        assert len(single_rows) == 3
    finally:
        app.dependency_overrides.pop(get_expense_parser, None)
