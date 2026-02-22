from datetime import date

from pydantic import BaseModel, Field


class ParseContext(BaseModel):
    reference_date: date
    timezone: str
    default_currency: str
    household_categories: list[str] = Field(default_factory=list)
    household_taxonomy: dict[str, list[str]] = Field(default_factory=dict)
    household_members: list[str] = Field(default_factory=list)


class ParsedExpense(BaseModel):
    amount: float | None = None
    currency: str | None = None
    attributed_family_member_name: str | None = None
    category: str | None = None
    subcategory: str | None = None
    description: str | None = None
    merchant_or_item: str | None = None
    date_incurred: str | None = None
    is_recurring: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ParseResult(BaseModel):
    expenses: list[ParsedExpense] = Field(default_factory=list)
    mode: str = "expense"
    assistant_message: str | None = None
    needs_clarification: bool = False
    clarification_questions: list[str] = Field(default_factory=list)
