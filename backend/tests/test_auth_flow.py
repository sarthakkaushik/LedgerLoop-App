from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.api.deps import get_expense_parser
from app.services.llm.base import ExpenseParserProvider
from app.services.llm.types import ParseContext, ParseResult, ParsedExpense


class _SingleExpenseParser(ExpenseParserProvider):
    async def parse_expenses(self, text: str, context: ParseContext) -> ParseResult:
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


@pytest.mark.asyncio
async def test_register_invite_join_login_me_flow(client: AsyncClient) -> None:
    register_payload = {
        "email": "admin@example.com",
        "password": "testpass123",
        "full_name": "Admin User",
        "household_name": "Sharma Family",
    }
    register_res = await client.post("/auth/register", json=register_payload)
    assert register_res.status_code == 201
    admin_token = register_res.json()["token"]["access_token"]

    invite_res = await client.post(
        "/auth/invite",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert invite_res.status_code == 200
    invite_code = invite_res.json()["invite_code"]

    join_payload = {
        "email": "spouse@example.com",
        "password": "testpass123",
        "full_name": "Spouse User",
        "invite_code": invite_code,
    }
    join_res = await client.post("/auth/join", json=join_payload)
    assert join_res.status_code == 201
    join_data = join_res.json()
    member_token = join_data["token"]["access_token"]
    member_id = join_data["user"]["id"]

    login_payload = {"email": "spouse@example.com", "password": "testpass123"}
    login_res = await client.post("/auth/login", json=login_payload)
    assert login_res.status_code == 200
    assert login_res.json()["user"]["role"] == "member"

    token_res = await client.post(
        "/auth/token",
        data={"username": "spouse@example.com", "password": "testpass123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert token_res.status_code == 200
    assert "access_token" in token_res.json()
    oauth_token = token_res.json()["access_token"]

    me_res = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {oauth_token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "spouse@example.com"

    household_admin_res = await client.get(
        "/auth/household",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert household_admin_res.status_code == 200
    admin_household = household_admin_res.json()
    assert admin_household["household_name"] == "Sharma Family"
    assert admin_household["invite_code"]
    assert len(admin_household["members"]) == 2

    household_member_res = await client.get(
        "/auth/household",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert household_member_res.status_code == 200
    member_household = household_member_res.json()
    assert member_household["invite_code"] is None
    assert len(member_household["members"]) == 2

    delete_res = await client.delete(
        f"/auth/members/{member_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert delete_res.status_code == 200
    assert delete_res.json()["member_id"] == member_id

    household_after_delete_res = await client.get(
        "/auth/household",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert household_after_delete_res.status_code == 200
    assert len(household_after_delete_res.json()["members"]) == 1

    deleted_member_login_res = await client.post("/auth/login", json=login_payload)
    assert deleted_member_login_res.status_code == 401

    deleted_member_me_res = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert deleted_member_me_res.status_code == 401


@pytest.mark.asyncio
async def test_non_admin_cannot_delete_member(client: AsyncClient) -> None:
    register_res = await client.post(
        "/auth/register",
        json={
            "email": "owner@example.com",
            "password": "testpass123",
            "full_name": "Owner",
            "household_name": "Owner Home",
        },
    )
    assert register_res.status_code == 201
    admin_token = register_res.json()["token"]["access_token"]

    invite_res = await client.post(
        "/auth/invite",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert invite_res.status_code == 200
    invite_code = invite_res.json()["invite_code"]

    member1_res = await client.post(
        "/auth/join",
        json={
            "email": "member1@example.com",
            "password": "testpass123",
            "full_name": "Member One",
            "invite_code": invite_code,
        },
    )
    assert member1_res.status_code == 201
    member1_token = member1_res.json()["token"]["access_token"]

    member2_res = await client.post(
        "/auth/join",
        json={
            "email": "member2@example.com",
            "password": "testpass123",
            "full_name": "Member Two",
            "invite_code": invite_code,
        },
    )
    assert member2_res.status_code == 201
    member2_id = member2_res.json()["user"]["id"]

    delete_res = await client.delete(
        f"/auth/members/{member2_id}",
        headers={"Authorization": f"Bearer {member1_token}"},
    )
    assert delete_res.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_rename_household_and_member_cannot(client: AsyncClient) -> None:
    register_res = await client.post(
        "/auth/register",
        json={
            "email": "rename-owner@example.com",
            "password": "testpass123",
            "full_name": "Rename Owner",
            "household_name": "Starter Home",
        },
    )
    assert register_res.status_code == 201
    admin_token = register_res.json()["token"]["access_token"]

    rename_res = await client.patch(
        "/auth/household/name",
        json={"household_name": "Updated Home"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rename_res.status_code == 200
    assert rename_res.json()["household_name"] == "Updated Home"

    household_res = await client.get(
        "/auth/household",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert household_res.status_code == 200
    assert household_res.json()["household_name"] == "Updated Home"

    invite_res = await client.post(
        "/auth/invite",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert invite_res.status_code == 200
    invite_code = invite_res.json()["invite_code"]

    member_res = await client.post(
        "/auth/join",
        json={
            "email": "rename-member@example.com",
            "password": "testpass123",
            "full_name": "Rename Member",
            "invite_code": invite_code,
        },
    )
    assert member_res.status_code == 201
    member_token = member_res.json()["token"]["access_token"]

    member_rename_res = await client.patch(
        "/auth/household/name",
        json={"household_name": "Member Rename Attempt"},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert member_rename_res.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_deactivate_member_even_with_logged_expenses(client: AsyncClient) -> None:
    from app.main import app

    app.dependency_overrides[get_expense_parser] = lambda: _SingleExpenseParser()
    try:
        register_res = await client.post(
            "/auth/register",
            json={
                "email": "deactivate-owner@example.com",
                "password": "testpass123",
                "full_name": "Deactivate Owner",
                "household_name": "Deactivate Home",
            },
        )
        assert register_res.status_code == 201
        admin_token = register_res.json()["token"]["access_token"]

        invite_res = await client.post(
            "/auth/invite",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert invite_res.status_code == 200
        invite_code = invite_res.json()["invite_code"]

        member_res = await client.post(
            "/auth/join",
            json={
                "email": "deactivate-member@example.com",
                "password": "testpass123",
                "full_name": "Deactivate Member",
                "invite_code": invite_code,
            },
        )
        assert member_res.status_code == 201
        member_token = member_res.json()["token"]["access_token"]
        member_id = member_res.json()["user"]["id"]

        log_res = await client.post(
            "/expenses/log",
            json={"text": "Bought groceries for 500 yesterday"},
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert log_res.status_code == 200

        deactivate_res = await client.delete(
            f"/auth/members/{member_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert deactivate_res.status_code == 200
        assert deactivate_res.json()["member_id"] == member_id

        member_login_res = await client.post(
            "/auth/login",
            json={
                "email": "deactivate-member@example.com",
                "password": "testpass123",
            },
        )
        assert member_login_res.status_code == 401
    finally:
        app.dependency_overrides.pop(get_expense_parser, None)
