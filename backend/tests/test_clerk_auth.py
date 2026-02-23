import pytest
from httpx import AsyncClient

import app.api.auth as auth_api
from app.services.auth.clerk import ClerkIdentity


def _mock_clerk_verifier(identity: ClerkIdentity):
    async def _verify(token: str) -> ClerkIdentity:
        assert token == "clerk-test-token"
        return identity

    return _verify


@pytest.mark.asyncio
async def test_clerk_exchange_requires_onboarding_for_new_identity(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        auth_api,
        "verify_clerk_session_token",
        _mock_clerk_verifier(
            ClerkIdentity(
                clerk_user_id="user_clerk_001",
                email="new-clerk-user@example.com",
                full_name="New Clerk User",
            )
        ),
    )

    response = await client.post(
        "/auth/clerk/exchange",
        headers={"Authorization": "Bearer clerk-test-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "needs_onboarding"
    assert data["identity"]["clerk_user_id"] == "user_clerk_001"
    assert data["identity"]["email"] == "new-clerk-user@example.com"


@pytest.mark.asyncio
async def test_clerk_exchange_links_existing_email_user(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register_response = await client.post(
        "/auth/register",
        json={
            "email": "hybrid-user@example.com",
            "password": "testpass123",
            "full_name": "Hybrid User",
            "household_name": "Hybrid Home",
        },
    )
    assert register_response.status_code == 201

    monkeypatch.setattr(
        auth_api,
        "verify_clerk_session_token",
        _mock_clerk_verifier(
            ClerkIdentity(
                clerk_user_id="user_clerk_002",
                email="hybrid-user@example.com",
                full_name="Hybrid User",
            )
        ),
    )

    exchange_response = await client.post(
        "/auth/clerk/exchange",
        headers={"Authorization": "Bearer clerk-test-token"},
    )
    assert exchange_response.status_code == 200
    exchange_data = exchange_response.json()
    assert exchange_data["status"] == "linked"
    assert exchange_data["token"]["access_token"]
    assert exchange_data["user"]["email"] == "hybrid-user@example.com"


@pytest.mark.asyncio
async def test_clerk_onboarding_create_household(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        auth_api,
        "verify_clerk_session_token",
        _mock_clerk_verifier(
            ClerkIdentity(
                clerk_user_id="user_clerk_003",
                email="clerk-create@example.com",
                full_name="Clerk Create",
            )
        ),
    )

    create_response = await client.post(
        "/auth/clerk/onboarding/create",
        headers={"Authorization": "Bearer clerk-test-token"},
        json={
            "full_name": "Clerk Create",
            "household_name": "Clerk Home",
        },
    )
    assert create_response.status_code == 201
    create_data = create_response.json()
    assert create_data["token"]["access_token"]
    assert create_data["user"]["email"] == "clerk-create@example.com"
    assert create_data["user"]["role"] == "admin"

    exchange_response = await client.post(
        "/auth/clerk/exchange",
        headers={"Authorization": "Bearer clerk-test-token"},
    )
    assert exchange_response.status_code == 200
    assert exchange_response.json()["status"] == "linked"


@pytest.mark.asyncio
async def test_clerk_onboarding_join_household(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register_response = await client.post(
        "/auth/register",
        json={
            "email": "clerk-admin@example.com",
            "password": "testpass123",
            "full_name": "Clerk Admin",
            "household_name": "Clerk Shared Home",
        },
    )
    assert register_response.status_code == 201
    admin_token = register_response.json()["token"]["access_token"]
    household_id = register_response.json()["user"]["household_id"]

    invite_response = await client.post(
        "/auth/invite",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert invite_response.status_code == 200
    invite_code = invite_response.json()["invite_code"]

    monkeypatch.setattr(
        auth_api,
        "verify_clerk_session_token",
        _mock_clerk_verifier(
            ClerkIdentity(
                clerk_user_id="user_clerk_004",
                email="clerk-member@example.com",
                full_name="Clerk Member",
            )
        ),
    )

    join_response = await client.post(
        "/auth/clerk/onboarding/join",
        headers={"Authorization": "Bearer clerk-test-token"},
        json={
            "full_name": "Clerk Member",
            "invite_code": invite_code,
        },
    )
    assert join_response.status_code == 201
    join_data = join_response.json()
    assert join_data["token"]["access_token"]
    assert join_data["user"]["role"] == "member"
    assert join_data["user"]["household_id"] == household_id
