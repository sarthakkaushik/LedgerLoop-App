from typing import Literal

from pydantic import BaseModel, Field


class ExpenseLogRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class ExpenseDraft(BaseModel):
    id: str | None = None
    amount: float | None = None
    currency: str | None = None
    category: str | None = None
    description: str | None = None
    merchant_or_item: str | None = None
    date_incurred: str | None = None
    is_recurring: bool = False
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class ExpenseLogResponse(BaseModel):
    mode: Literal["expense", "chat"] = "expense"
    assistant_message: str | None = None
    expenses: list[ExpenseDraft]
    needs_clarification: bool
    clarification_questions: list[str]


class ExpenseConfirmEdit(BaseModel):
    draft_id: str = Field(min_length=1)
    amount: float | None = Field(default=None, gt=0)
    currency: str | None = None
    category: str | None = None
    description: str | None = None
    merchant_or_item: str | None = None
    date_incurred: str | None = None
    is_recurring: bool | None = None


class ExpenseConfirmRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=120)
    expenses: list[ExpenseConfirmEdit] = Field(min_length=1, max_length=100)


class ExpenseConfirmResponse(BaseModel):
    confirmed_count: int
    idempotent_replay: bool
    expenses: list[ExpenseDraft]


class ExpenseFeedItem(BaseModel):
    id: str
    amount: float | None = None
    currency: str
    category: str | None = None
    description: str | None = None
    merchant_or_item: str | None = None
    date_incurred: str
    is_recurring: bool = False
    status: str
    logged_by_user_id: str
    logged_by_name: str
    created_at: str
    updated_at: str


class ExpenseFeedResponse(BaseModel):
    items: list[ExpenseFeedItem]
    total_count: int


class ExpenseDeleteResponse(BaseModel):
    expense_id: str
    message: str


class DashboardDailyPoint(BaseModel):
    day: str
    total: float


class DashboardCategoryPoint(BaseModel):
    category: str
    total: float
    count: int


class DashboardUserPoint(BaseModel):
    user_id: str
    user_name: str
    total: float
    count: int


class DashboardMonthlyPoint(BaseModel):
    month: str
    total: float


class ExpenseDashboardResponse(BaseModel):
    period_month: str
    period_start: str
    period_end: str
    total_spend: float
    expense_count: int
    daily_burn: list[DashboardDailyPoint]
    category_split: list[DashboardCategoryPoint]
    user_split: list[DashboardUserPoint]
    monthly_trend: list[DashboardMonthlyPoint]
