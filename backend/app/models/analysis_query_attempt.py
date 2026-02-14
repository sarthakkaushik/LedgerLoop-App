from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class AnalysisQueryAttempt(SQLModel, table=True):
    __tablename__ = "analysis_query_attempts"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    analysis_query_id: UUID = Field(
        foreign_key="analysis_queries.id",
        nullable=False,
        index=True,
    )
    attempt_number: int = Field(nullable=False, index=True)
    generated_sql: str = Field(default="", sa_column=Column(String(20000), nullable=False))
    llm_reason: str | None = Field(default=None, sa_column=Column(String(4000)))
    validation_ok: bool = Field(default=False, nullable=False)
    validation_reason: str | None = Field(default=None, sa_column=Column(String(2000)))
    execution_ok: bool = Field(default=False, nullable=False)
    db_error: str | None = Field(default=None, sa_column=Column(String(4000)))
    created_at: datetime = Field(default_factory=utc_now_naive, nullable=False, index=True)

