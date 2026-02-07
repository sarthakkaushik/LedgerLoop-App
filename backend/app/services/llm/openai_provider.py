import httpx

from app.services.llm.base import ExpenseParserProvider
from app.services.llm.parser_utils import parse_result_from_text
from app.services.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from app.services.llm.types import ParseContext, ParseResult


class OpenAIExpenseParserProvider(ExpenseParserProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def parse_expenses(self, text: str, context: ParseContext) -> ParseResult:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_user_prompt(
                        text=text,
                        reference_date=str(context.reference_date),
                        timezone=context.timezone,
                        default_currency=context.default_currency,
                    ),
                },
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        timeout = httpx.Timeout(30.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return parse_result_from_text(content)
