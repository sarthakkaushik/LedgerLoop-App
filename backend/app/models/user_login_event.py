from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class UserLoginEvent(SQLModel, table=True):
    __tablename__ = "user_login_events"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    user_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)
    household_id: UUID = Field(foreign_key="households.id", nullable=False, index=True)
    auth_method: str = Field(
        default="login",
        sa_column=Column(String(24), nullable=False, default="login"),
    )
    login_at: datetime = Field(default_factory=utc_now_naive, nullable=False, index=True)
