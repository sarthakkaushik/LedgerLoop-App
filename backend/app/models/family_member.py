from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class FamilyMemberType(str, Enum):
    ADULT = "adult"
    CHILD = "child"
    OTHER = "other"


class FamilyMember(SQLModel, table=True):
    __tablename__ = "family_members"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    household_id: UUID = Field(foreign_key="households.id", nullable=False, index=True)
    full_name: str = Field(nullable=False, max_length=120)
    normalized_name: str = Field(nullable=False, max_length=120, index=True)
    member_type: FamilyMemberType = Field(default=FamilyMemberType.OTHER, nullable=False)
    linked_user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    is_active: bool = Field(default=True, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now_naive, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now_naive, nullable=False)
