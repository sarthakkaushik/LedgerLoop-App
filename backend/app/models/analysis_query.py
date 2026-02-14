from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class AnalysisQuery(SQLModel, table=True):
    __tablename__ = "analysis_queries"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    household_id: UUID = Field(foreign_key="households.id", nullable=False, index=True)
    user_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)
    provider: str = Field(
        default="mock",
        sa_column=Column(String(40), nullable=False, index=True),
    )
    model: str = Field(default="", sa_column=Column(String(120), nullable=False))
    question: str = Field(default="", sa_column=Column(String(2000), nullable=False))
    mode: str = Field(default="analytics", sa_column=Column(String(24), nullable=False))
    route: str = Field(default="agent", sa_column=Column(String(24), nullable=False))
    tool: str = Field(default="adhoc_sql", sa_column=Column(String(80), nullable=False))
    status: str = Field(
        default="running",
        sa_column=Column(String(24), nullable=False, index=True),
    )
    attempt_count: int = Field(default=0, nullable=False)
    final_sql: str | None = Field(default=None, sa_column=Column(String(20000)))
    final_answer: str | None = Field(default=None, sa_column=Column(String(12000)))
    failure_reason: str | None = Field(default=None, sa_column=Column(String(4000)))
    created_at: datetime = Field(default_factory=utc_now_naive, nullable=False, index=True)
    updated_at: datetime = Field(default_factory=utc_now_naive, nullable=False, index=True)

