from abc import ABC, abstractmethod

from app.services.llm.types import ParseContext, ParseResult


class ExpenseParserProvider(ABC):
    @abstractmethod
    async def parse_expenses(self, text: str, context: ParseContext) -> ParseResult:
        raise NotImplementedError
