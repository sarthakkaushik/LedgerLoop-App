import json

import httpx

from app.services.llm.base import ExpenseParserProvider
from app.services.llm.parser_utils import parse_result_from_text
from app.services.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from app.services.llm.types import ParseContext, ParseResult


def _normalize_message_content(content: object) -> str:
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    if isinstance(content, list):
        chunks: list[str] = []
        for block in content:
            if isinstance(block, str):
                chunks.append(block)
                continue
            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    chunks.append(text)
                    continue
            chunks.append(json.dumps(block))
        return "\n".join(chunks)
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            return text
        return json.dumps(content)
    return str(content)


class CerebrasExpenseParserProvider(ExpenseParserProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def parse_expenses(self, text: str, context: ParseContext) -> ParseResult:
        user_prompt = build_user_prompt(
            text=text,
            reference_date=str(context.reference_date),
            timezone=context.timezone,
            default_currency=context.default_currency,
            household_categories=context.household_categories,
            household_members=context.household_members,
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        timeout = httpx.Timeout(30.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://api.cerebras.ai/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return parse_result_from_text(_normalize_message_content(content))
