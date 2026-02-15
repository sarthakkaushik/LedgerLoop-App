import pytest
from httpx import AsyncClient

from app.api.analysis import HOUSEHOLD_CTE, _safe_sql


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


@pytest.mark.asyncio
async def test_analysis_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/analysis/ask", json={"text": "How much this month?"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_analysis_returns_simple_agent_response_shape(client: AsyncClient) -> None:
    token = await register_user(client, "analysis-shape@example.com", "Family Shape")
    response = await client.post(
        "/analysis/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": "How much did we spend this month?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "analytics"
    assert payload["route"] == "agent"
    assert payload["tool"] == "sql_chat_agent"
    assert isinstance(payload["answer"], str)
    assert payload["chart"] is None
    assert payload["table"] is None
    assert payload["sql"] is None
    assert isinstance(payload["tool_trace"], list)


def test_safe_sql_blocks_dangerous_statements() -> None:
    ok, _ = _safe_sql("DELETE FROM household_expenses")
    assert ok is False

    ok, _ = _safe_sql("SELECT * FROM users")
    assert ok is False

    ok, _ = _safe_sql("SELECT category, SUM(amount) FROM household_expenses GROUP BY category")
    assert ok is True


def test_household_cte_casts_status_to_text() -> None:
    assert "CAST(e.status AS TEXT) AS status" in HOUSEHOLD_CTE
