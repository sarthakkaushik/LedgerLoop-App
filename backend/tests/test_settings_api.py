import pytest
from httpx import AsyncClient

from app.services.llm import settings_service


async def register_admin_and_get_token(client: AsyncClient, email: str) -> str:
    payload = {
        "email": email,
        "password": "testpass123",
        "full_name": "Admin User",
        "household_name": "Settings Family",
    }
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 201
    return response.json()["token"]["access_token"]


@pytest.mark.asyncio
async def test_llm_settings_get_and_update_blocked(client: AsyncClient) -> None:
    token = await register_admin_and_get_token(client, "settings-admin@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    runtime = settings_service.get_env_runtime_config()

    get_res = await client.get("/settings/llm", headers=headers)
    assert get_res.status_code == 200
    payload = get_res.json()
    assert payload["provider"] == runtime.provider.value
    assert payload["model"] == runtime.model
    assert payload["default_currency"] == runtime.default_currency
    assert payload["timezone"] == runtime.timezone
    assert payload["has_api_key"] is bool(runtime.api_key)

    put_res = await client.put(
        "/settings/llm",
        json={
            "provider": "openai",
            "model": "gpt-4o-mini",
            "default_currency": "INR",
            "timezone": "Asia/Kolkata",
            "api_key": "sk-test-key-12345678",
        },
        headers=headers,
    )
    assert put_res.status_code == 409
    assert "managed by server environment variables" in put_res.json()["detail"]


@pytest.mark.asyncio
async def test_llm_settings_test_mock_provider(client: AsyncClient) -> None:
    token = await register_admin_and_get_token(client, "settings-mock@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    settings = settings_service.settings
    original_provider = settings.llm_provider
    original_model = settings.llm_model
    original_openai_key = settings.openai_api_key
    original_openai_model = settings.openai_model
    original_gemini_key = settings.gemini_api_key
    original_gemini_model = settings.gemini_model

    settings.llm_provider = "mock"
    settings.llm_model = "mock-expense-parser-v1"
    settings.openai_api_key = None
    settings.openai_model = "gpt-4o-mini"
    settings.gemini_api_key = None
    settings.gemini_model = "gemini-2.0-flash"
    try:
        test_res = await client.post("/settings/llm/test", headers=headers)
        assert test_res.status_code == 200
        assert test_res.json()["success"] is True
        assert test_res.json()["provider"] == "mock"
    finally:
        settings.llm_provider = original_provider
        settings.llm_model = original_model
        settings.openai_api_key = original_openai_key
        settings.openai_model = original_openai_model
        settings.gemini_api_key = original_gemini_key
        settings.gemini_model = original_gemini_model
