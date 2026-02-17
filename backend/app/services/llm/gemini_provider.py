import httpx

from app.services.llm.base import ExpenseParserProvider
from app.services.llm.parser_utils import parse_result_from_text
from app.services.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from app.services.llm.types import ParseContext, ParseResult


class GeminiExpenseParserProvider(ExpenseParserProvider):
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
            household_taxonomy=context.household_taxonomy,
            household_members=context.household_members,
        )
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": f"{SYSTEM_PROMPT}\n\n{user_prompt}"}]}
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        }
        timeout = httpx.Timeout(30.0, connect=10.0)
        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            f"?key={self.api_key}"
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            return parse_result_from_text(content)
