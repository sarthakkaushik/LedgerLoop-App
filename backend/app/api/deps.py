from datetime import date
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.db import get_session
from app.core.security import decode_access_token
from app.models.user import User, UserRole
from app.services.llm.base import ExpenseParserProvider
from app.services.llm.provider_factory import get_expense_parser_provider
from app.services.llm.settings_service import (
    get_env_runtime_config,
)
from app.services.llm.types import ParseContext

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


async def get_current_user(
    session: AsyncSession = Depends(get_session),
    token: str = Depends(oauth2_scheme),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
    )
    try:
        payload = decode_access_token(token)
        user_id = UUID(str(payload.get("sub")))
    except (ValueError, TypeError):
        raise unauthorized

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise unauthorized
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only household admin can perform this action",
        )
    return user


async def get_expense_parser(
    user: User = Depends(get_current_user),
) -> ExpenseParserProvider:
    _ = user
    return await get_expense_parser_provider()


async def get_llm_parse_context(
    user: User = Depends(get_current_user),
) -> ParseContext:
    _ = user
    runtime = get_env_runtime_config()
    return ParseContext(
        reference_date=date.today(),
        timezone=runtime.timezone,
        default_currency=runtime.default_currency,
    )
