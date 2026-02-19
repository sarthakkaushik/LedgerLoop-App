from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


DEFAULT_MONTHLY_BUDGET = 50000.0


class Household(SQLModel, table=True):
    __tablename__ = "households"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    name: str = Field(max_length=120, nullable=False)
    invite_code: str = Field(index=True, unique=True, nullable=False, max_length=32)
    monthly_budget: float = Field(default=DEFAULT_MONTHLY_BUDGET, nullable=False)
    created_at: datetime = Field(
        default_factory=utc_now_naive,
        nullable=False,
    )
