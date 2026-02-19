import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.deps import get_current_admin, get_current_user
from app.core.db import get_session
from app.core.security import create_access_token, hash_password, verify_password
from app.models.household import Household
from app.models.user import User, UserRole
from app.schemas.auth import (
    AuthResponse,
    DeleteMemberResponse,
    HouseholdMemberResponse,
    HouseholdOverviewResponse,
    HouseholdRenameRequest,
    InviteResponse,
    JoinRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.taxonomy_service import seed_default_household_taxonomy

router = APIRouter(prefix="/auth", tags=["auth"])


async def to_user_response(session: AsyncSession, user: User) -> UserResponse:
    household_result = await session.execute(
        select(Household.name).where(Household.id == user.household_id)
    )
    household_name = household_result.scalar_one_or_none()
    if not household_name:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found",
        )
    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        household_id=str(user.household_id),
        household_name=household_name,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
    )


def new_invite_code() -> str:
    return secrets.token_urlsafe(9).replace("-", "").replace("_", "").upper()


async def generate_unique_invite_code(session: AsyncSession) -> str:
    for _ in range(10):
        candidate = new_invite_code()
        result = await session.execute(
            select(Household).where(Household.invite_code == candidate)
        )
        if result.scalar_one_or_none() is None:
            return candidate
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unable to generate invite code. Try again.",
    )


async def authenticate_user(
    session: AsyncSession,
    email: str,
    password: str,
) -> User:
    result = await session.execute(select(User).where(User.email == email.lower().strip()))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    existing = await session.execute(
        select(User).where(User.email == payload.email.lower().strip())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        )

    household = Household(
        name=payload.household_name.strip(),
        invite_code=await generate_unique_invite_code(session),
    )
    session.add(household)
    await session.flush()

    user = User(
        email=payload.email.lower().strip(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        household_id=household.id,
        role=UserRole.ADMIN,
    )
    session.add(user)
    await seed_default_household_taxonomy(
        session,
        household_id=household.id,
        created_by_user_id=user.id,
    )
    await session.commit()
    await session.refresh(user)

    token = create_access_token(str(user.id))
    return AuthResponse(
        token=TokenResponse(access_token=token),
        user=await to_user_response(session, user),
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    user = await authenticate_user(session, payload.email, payload.password)
    token = create_access_token(str(user.id))
    return AuthResponse(
        token=TokenResponse(access_token=token),
        user=await to_user_response(session, user),
    )


@router.post("/token", response_model=TokenResponse)
async def token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    # For OAuth2 password flow, username field is used to carry email.
    user = await authenticate_user(session, form_data.username, form_data.password)
    access_token = create_access_token(str(user.id))
    return TokenResponse(access_token=access_token)


@router.post("/invite", response_model=InviteResponse)
async def create_invite_code(
    current_user: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> InviteResponse:
    result = await session.execute(
        select(Household).where(Household.id == current_user.household_id)
    )
    household = result.scalar_one_or_none()
    if not household:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found",
        )

    household.invite_code = await generate_unique_invite_code(session)
    session.add(household)
    await session.commit()

    return InviteResponse(
        invite_code=household.invite_code,
        message="Share this code with your spouse to join your household.",
    )


@router.post("/join", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def join_household(
    payload: JoinRequest,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    existing = await session.execute(
        select(User).where(User.email == payload.email.lower().strip())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        )

    household_result = await session.execute(
        select(Household).where(
            Household.invite_code == payload.invite_code.upper().strip()
        )
    )
    household = household_result.scalar_one_or_none()
    if not household:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invite code",
        )

    user = User(
        email=payload.email.lower().strip(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        household_id=household.id,
        role=UserRole.MEMBER,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token = create_access_token(str(user.id))
    return AuthResponse(
        token=TokenResponse(access_token=token),
        user=await to_user_response(session, user),
    )


@router.delete("/members/{member_id}", response_model=DeleteMemberResponse)
async def delete_household_member(
    member_id: str,
    current_user: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> DeleteMemberResponse:
    try:
        member_uuid = UUID(member_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid member_id",
        ) from exc

    if member_uuid == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own admin account.",
        )

    member_result = await session.execute(
        select(User).where(
            User.id == member_uuid,
            User.household_id == current_user.household_id,
        )
    )
    member = member_result.scalar_one_or_none()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in your household.",
        )

    if member.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin members cannot be deleted.",
        )
    if not member.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Member is already deactivated.",
        )

    member.is_active = False
    session.add(member)
    await session.commit()

    return DeleteMemberResponse(
        member_id=str(member.id),
        message="Member access removed successfully.",
    )


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    return await to_user_response(session, current_user)


@router.get("/household", response_model=HouseholdOverviewResponse)
async def household_overview(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> HouseholdOverviewResponse:
    household_result = await session.execute(
        select(Household).where(Household.id == current_user.household_id)
    )
    household = household_result.scalar_one_or_none()
    if not household:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found",
        )

    members_result = await session.execute(
        select(User)
        .where(
            User.household_id == current_user.household_id,
            User.is_active.is_(True),
        )
        .order_by(User.created_at.asc())
    )
    members = members_result.scalars().all()

    return HouseholdOverviewResponse(
        household_id=str(household.id),
        household_name=household.name,
        invite_code=household.invite_code if current_user.role == UserRole.ADMIN else None,
        members=[
            HouseholdMemberResponse(
                id=str(member.id),
                email=member.email,
                full_name=member.full_name,
                role=member.role.value if hasattr(member.role, "value") else str(member.role),
                created_at=member.created_at.isoformat(),
            )
            for member in members
        ],
    )


@router.patch("/household/name", response_model=UserResponse)
async def update_household_name(
    payload: HouseholdRenameRequest,
    current_user: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    household_result = await session.execute(
        select(Household).where(Household.id == current_user.household_id)
    )
    household = household_result.scalar_one_or_none()
    if not household:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found",
        )

    next_name = payload.household_name.strip()
    if not next_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Household name cannot be empty",
        )

    household.name = next_name
    session.add(household)
    await session.commit()

    return await to_user_response(session, current_user)
