from datetime import UTC, date, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ExpenseStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"


class Expense(SQLModel, table=True):
    __tablename__ = "expenses"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    household_id: UUID = Field(foreign_key="households.id", nullable=False, index=True)
    logged_by_user_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
    )
    attributed_family_member_id: UUID | None = Field(
        default=None,
        foreign_key="family_members.id",
        index=True,
    )
    amount: float | None = Field(default=None)
    currency: str = Field(sa_column=Column(String(8), nullable=False, default="INR"))
    category: str | None = Field(default=None, max_length=80)
    subcategory: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=255)
    merchant_or_item: str | None = Field(default=None, max_length=255)
    date_incurred: date = Field(nullable=False)
    is_recurring: bool = Field(default=False, nullable=False)
    confidence: float = Field(default=0.0, nullable=False)
    status: ExpenseStatus = Field(default=ExpenseStatus.DRAFT, nullable=False, index=True)
    source_text: str | None = Field(default=None, max_length=2000)
    idempotency_key: str | None = Field(
        sa_column=Column(String(120), nullable=True, index=True)
    )
    created_at: datetime = Field(default_factory=utc_now_naive, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now_naive, nullable=False)
