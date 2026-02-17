from datetime import date
import json

import pytest

from app.services.llm.cerebras_provider import (
    CerebrasExpenseParserProvider,
    _normalize_message_content,
)
from app.services.llm.types import ParseContext


def test_normalize_message_content_from_text_blocks() -> None:
    payload = {
        "expenses": [],
        "mode": "expense",
        "needs_clarification": False,
        "clarification_questions": [],
    }
    content = [{"type": "text", "text": json.dumps(payload)}]
    assert _normalize_message_content(content) == json.dumps(payload)


def test_normalize_message_content_from_dict_payload() -> None:
    content = {
        "expenses": [],
        "mode": "expense",
        "needs_clarification": False,
        "clarification_questions": [],
    }
    normalized = _normalize_message_content(content)
    assert normalized.startswith("{")
    assert '"expenses"' in normalized


@pytest.mark.asyncio
async def test_parse_expenses_handles_structured_content_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "expenses": [],
        "mode": "expense",
        "needs_clarification": False,
        "clarification_questions": [],
    }

    class DummyResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": [{"type": "text", "text": json.dumps(payload)}],
                        }
                    }
                ]
            }

    class DummyClient:
        async def __aenter__(self) -> "DummyClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def post(self, url: str, **kwargs: object) -> DummyResponse:
            return DummyResponse()

    monkeypatch.setattr(
        "app.services.llm.cerebras_provider.httpx.AsyncClient",
        lambda *args, **kwargs: DummyClient(),
    )

    provider = CerebrasExpenseParserProvider(api_key="test-key", model="test-model")
    context = ParseContext(
        reference_date=date(2026, 2, 17),
        timezone="UTC",
        default_currency="USD",
    )

    result = await provider.parse_expenses("coffee 5 usd", context)
    assert result.mode == "expense"
    assert result.expenses == []
    assert result.needs_clarification is False
