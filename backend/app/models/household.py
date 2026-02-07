from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class Household(SQLModel, table=True):
    __tablename__ = "households"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    name: str = Field(max_length=120, nullable=False)
    invite_code: str = Field(index=True, unique=True, nullable=False, max_length=32)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        nullable=False,
    )
