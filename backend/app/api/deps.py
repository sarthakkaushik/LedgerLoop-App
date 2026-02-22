from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.db import get_session
from app.models.expense import Expense
from app.models.family_member import FamilyMember
from app.core.security import decode_access_token
from app.models.user import User, UserRole
from app.services.llm.base import ExpenseParserProvider
from app.services.llm.provider_factory import get_expense_parser_provider
from app.services.llm.settings_service import (
    get_env_runtime_config,
)
from app.services.taxonomy_service import build_household_taxonomy_map
from app.services.family_member_service import ensure_linked_family_members_for_household
from app.services.llm.types import ParseContext

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def _today_for_timezone(timezone_name: str) -> date:
    try:
        return datetime.now(ZoneInfo(timezone_name)).date()
    except Exception:
        return date.today()


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
    session: AsyncSession = Depends(get_session),
) -> ParseContext:
    runtime = get_env_runtime_config()
    await ensure_linked_family_members_for_household(
        session,
        household_id=user.household_id,
    )
    categories, taxonomy = await build_household_taxonomy_map(
        session,
        household_id=user.household_id,
    )

    if not categories:
        cat_result = await session.execute(
            select(Expense.category).where(
                Expense.household_id == user.household_id,
                Expense.category.is_not(None),
            )
        )
        categories = sorted(
            {
                str(value).strip()
                for value in cat_result.scalars().all()
                if value and str(value).strip()
            }
        )[:30]
        if "Other" not in categories:
            categories.append("Other")
        taxonomy = {category: [] for category in categories}

    profile_result = await session.execute(
        select(FamilyMember.full_name).where(
            FamilyMember.household_id == user.household_id,
            FamilyMember.is_active.is_(True),
        )
    )
    profile_members = {
        str(value).strip()
        for value in profile_result.scalars().all()
        if value and str(value).strip()
    }

    user_result = await session.execute(
        select(User.full_name).where(
            User.household_id == user.household_id,
            User.is_active == True,  # noqa: E712
        )
    )
    user_members = {
        str(value).strip()
        for value in user_result.scalars().all()
        if value and str(value).strip()
    }

    members = sorted(profile_members | user_members)[:40]

    return ParseContext(
        reference_date=_today_for_timezone(runtime.timezone),
        timezone=runtime.timezone,
        default_currency=runtime.default_currency,
        household_categories=categories[:60],
        household_taxonomy=taxonomy,
        household_members=members,
    )
