from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import EmailStr
from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel


class UserRole(str, Enum):
    ADMIN = "admin"
    MEMBER = "member"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    email: EmailStr = Field(
        sa_column=Column(String(320), unique=True, index=True, nullable=False)
    )
    hashed_password: str = Field(nullable=False, max_length=255)
    full_name: str = Field(nullable=False, max_length=120)
    household_id: UUID = Field(foreign_key="households.id", nullable=False, index=True)
    role: UserRole = Field(default=UserRole.MEMBER, nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        nullable=False,
    )
