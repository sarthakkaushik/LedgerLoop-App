from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class HouseholdCategory(SQLModel, table=True):
    __tablename__ = "household_categories"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "normalized_name",
            name="uq_household_category_normalized_name",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    household_id: UUID = Field(foreign_key="households.id", nullable=False, index=True)
    name: str = Field(sa_column=Column(String(80), nullable=False))
    normalized_name: str = Field(sa_column=Column(String(80), nullable=False, index=True))
    is_active: bool = Field(default=True, nullable=False, index=True)
    sort_order: int = Field(default=0, nullable=False)
    created_by_user_id: UUID | None = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
        index=True,
    )
    created_at: datetime = Field(default_factory=utc_now_naive, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now_naive, nullable=False)
