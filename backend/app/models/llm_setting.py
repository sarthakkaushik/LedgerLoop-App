from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class LLMProvider(str, Enum):
    MOCK = "mock"
    OPENAI = "openai"
    GEMINI = "gemini"
    CEREBRAS = "cerebras"


class LLMSetting(SQLModel, table=True):
    __tablename__ = "llm_settings"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    household_id: UUID = Field(
        foreign_key="households.id",
        nullable=False,
        index=True,
        unique=True,
    )
    provider: LLMProvider = Field(default=LLMProvider.MOCK, nullable=False)
    model: str = Field(nullable=False, max_length=120)
    default_currency: str = Field(
        sa_column=Column(String(8), nullable=False, default="INR")
    )
    timezone: str = Field(sa_column=Column(String(64), nullable=False, default="UTC"))
    api_key_encrypted: str | None = Field(default=None, max_length=1024)
    created_at: datetime = Field(default_factory=utc_now_naive, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now_naive, nullable=False)
