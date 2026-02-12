from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.models.llm_setting import LLMProvider
from app.services.llm.base import ExpenseParserProvider
from app.services.llm.gemini_provider import GeminiExpenseParserProvider
from app.services.llm.mock_provider import MockExpenseParserProvider
from app.services.llm.openai_provider import OpenAIExpenseParserProvider
from app.services.llm.settings_service import (
    get_env_runtime_config,
)
from app.services.llm.types import ParseContext, ParseResult


class ProviderNotConfiguredError(RuntimeError):
    """Raised when a non-mock provider is selected but not configured."""


class NotImplementedProvider(ExpenseParserProvider):
    def __init__(self, provider_name: str):
        self.provider_name = provider_name

    async def parse_expenses(self, text: str, context: ParseContext) -> ParseResult:
        raise ProviderNotConfiguredError(
            f"LLM provider '{self.provider_name}' is not configured yet."
        )


async def get_expense_parser_provider(
    session: AsyncSession | None = None,
    household_id: UUID | None = None,
) -> ExpenseParserProvider:
    runtime = get_env_runtime_config()

    if runtime.provider == LLMProvider.MOCK:
        return MockExpenseParserProvider()
    if runtime.provider == LLMProvider.OPENAI:
        if not runtime.api_key:
            raise ProviderNotConfiguredError(
                "OpenAI API key is missing. Set OPENAI_API_KEY in backend .env."
            )
        return OpenAIExpenseParserProvider(api_key=runtime.api_key, model=runtime.model)
    if runtime.provider == LLMProvider.GEMINI:
        if not runtime.api_key:
            raise ProviderNotConfiguredError(
                "Gemini API key is missing. Set GEMINI_API_KEY in backend .env."
            )
        return GeminiExpenseParserProvider(api_key=runtime.api_key, model=runtime.model)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Unsupported LLM provider '{runtime.provider}'",
    )
