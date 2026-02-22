from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.deps import get_current_user
from app.core.db import get_session
from app.models.family_member import FamilyMember, FamilyMemberType
from app.models.user import User
from app.schemas.family_member import (
    FamilyMemberBootstrapResponse,
    FamilyMemberCreateRequest,
    FamilyMemberDeleteResponse,
    FamilyMemberListResponse,
    FamilyMemberResponse,
    FamilyMemberUpdateRequest,
)
from app.services.family_member_service import (
    clean_family_member_name,
    ensure_linked_family_members_for_household,
    get_family_member_by_id,
    is_family_member_name_taken,
    list_household_family_members,
    normalize_family_member_name,
)

router = APIRouter(prefix="/family-members", tags=["family-members"])


def _current_time() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _to_family_member_response(
    member: FamilyMember,
    linked_user_names: dict[UUID, str],
) -> FamilyMemberResponse:
    return FamilyMemberResponse(
        id=str(member.id),
        household_id=str(member.household_id),
        full_name=member.full_name,
        normalized_name=member.normalized_name,
        member_type=member.member_type.value if hasattr(member.member_type, "value") else str(member.member_type),
        linked_user_id=str(member.linked_user_id) if member.linked_user_id else None,
        linked_user_name=linked_user_names.get(member.linked_user_id) if member.linked_user_id else None,
        is_active=bool(member.is_active),
        created_at=member.created_at.isoformat(),
        updated_at=member.updated_at.isoformat(),
    )


def _parse_optional_uuid(raw_value: str | None, field_name: str) -> UUID | None:
    value = str(raw_value or "").strip()
    if not value:
        return None
    try:
        return UUID(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {field_name}",
        ) from exc


async def _resolve_linked_user_name_map(
    session: AsyncSession,
    members: list[FamilyMember],
) -> dict[UUID, str]:
    user_ids = {member.linked_user_id for member in members if member.linked_user_id}
    if not user_ids:
        return {}
    result = await session.execute(select(User).where(User.id.in_(list(user_ids))))
    return {user.id: user.full_name for user in result.scalars().all()}


async def _validate_linked_user(
    session: AsyncSession,
    *,
    household_id: UUID,
    linked_user_id: UUID,
    exclude_family_member_id: UUID | None = None,
) -> None:
    user_result = await session.execute(
        select(User).where(
            User.id == linked_user_id,
            User.household_id == household_id,
            User.is_active.is_(True),
        )
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="linked_user_id must reference an active household user.",
        )

    stmt = select(FamilyMember).where(
        FamilyMember.household_id == household_id,
        FamilyMember.linked_user_id == linked_user_id,
        FamilyMember.is_active.is_(True),
    )
    if exclude_family_member_id:
        stmt = stmt.where(FamilyMember.id != exclude_family_member_id)
    conflict_result = await session.execute(stmt)
    conflict = conflict_result.scalar_one_or_none()
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This household user is already linked to another active family profile.",
        )


@router.get("", response_model=FamilyMemberListResponse)
async def list_family_members(
    include_inactive: bool = Query(default=False, alias="include_inactive"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FamilyMemberListResponse:
    await ensure_linked_family_members_for_household(
        session,
        household_id=current_user.household_id,
    )
    members = await list_household_family_members(
        session,
        household_id=current_user.household_id,
        include_inactive=include_inactive,
    )
    linked_user_names = await _resolve_linked_user_name_map(session, members)
    return FamilyMemberListResponse(
        items=[_to_family_member_response(member, linked_user_names) for member in members]
    )


@router.post("", response_model=FamilyMemberResponse, status_code=status.HTTP_201_CREATED)
async def create_family_member(
    payload: FamilyMemberCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FamilyMemberResponse:
    await ensure_linked_family_members_for_household(
        session,
        household_id=current_user.household_id,
    )
    cleaned_name = clean_family_member_name(payload.full_name)
    normalized_name = normalize_family_member_name(cleaned_name)
    if not cleaned_name or not normalized_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="full_name is required.",
        )
    if await is_family_member_name_taken(
        session,
        household_id=current_user.household_id,
        normalized_name=normalized_name,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active family profile with this name already exists.",
        )

    linked_user_uuid = _parse_optional_uuid(payload.linked_user_id, "linked_user_id")
    if linked_user_uuid:
        await _validate_linked_user(
            session,
            household_id=current_user.household_id,
            linked_user_id=linked_user_uuid,
        )

    now = _current_time()
    member = FamilyMember(
        household_id=current_user.household_id,
        full_name=cleaned_name,
        normalized_name=normalized_name,
        member_type=FamilyMemberType.ADULT if linked_user_uuid else payload.member_type,
        linked_user_id=linked_user_uuid,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(member)
    await session.commit()
    await session.refresh(member)

    linked_user_names = await _resolve_linked_user_name_map(session, [member])
    return _to_family_member_response(member, linked_user_names)


@router.patch("/{family_member_id}", response_model=FamilyMemberResponse)
async def update_family_member(
    family_member_id: str,
    payload: FamilyMemberUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FamilyMemberResponse:
    try:
        member_uuid = UUID(family_member_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid family_member_id",
        ) from exc

    await ensure_linked_family_members_for_household(
        session,
        household_id=current_user.household_id,
    )
    member = await get_family_member_by_id(
        session,
        household_id=current_user.household_id,
        family_member_id=member_uuid,
        active_only=False,
    )
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family profile not found in your household.",
        )

    if "full_name" in payload.model_fields_set:
        cleaned_name = clean_family_member_name(payload.full_name or "")
        normalized_name = normalize_family_member_name(cleaned_name)
        if not cleaned_name or not normalized_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="full_name is required.",
            )
        if await is_family_member_name_taken(
            session,
            household_id=current_user.household_id,
            normalized_name=normalized_name,
            exclude_member_id=member.id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An active family profile with this name already exists.",
            )
        member.full_name = cleaned_name
        member.normalized_name = normalized_name

    if "member_type" in payload.model_fields_set and payload.member_type is not None:
        member.member_type = payload.member_type

    if "linked_user_id" in payload.model_fields_set:
        linked_user_uuid = _parse_optional_uuid(payload.linked_user_id, "linked_user_id")
        if linked_user_uuid:
            await _validate_linked_user(
                session,
                household_id=current_user.household_id,
                linked_user_id=linked_user_uuid,
                exclude_family_member_id=member.id,
            )
            member.linked_user_id = linked_user_uuid
            member.member_type = FamilyMemberType.ADULT
        else:
            member.linked_user_id = None

    if "is_active" in payload.model_fields_set and payload.is_active is not None:
        member.is_active = payload.is_active
        if not member.is_active:
            member.linked_user_id = None

    member.updated_at = _current_time()
    session.add(member)
    await session.commit()
    await session.refresh(member)

    linked_user_names = await _resolve_linked_user_name_map(session, [member])
    return _to_family_member_response(member, linked_user_names)


@router.delete("/{family_member_id}", response_model=FamilyMemberDeleteResponse)
async def delete_family_member(
    family_member_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FamilyMemberDeleteResponse:
    try:
        member_uuid = UUID(family_member_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid family_member_id",
        ) from exc

    member = await get_family_member_by_id(
        session,
        household_id=current_user.household_id,
        family_member_id=member_uuid,
        active_only=False,
    )
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family profile not found in your household.",
        )
    if not member.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Family profile is already inactive.",
        )

    member.is_active = False
    member.linked_user_id = None
    member.updated_at = _current_time()
    session.add(member)
    await session.commit()
    return FamilyMemberDeleteResponse(
        family_member_id=str(member.id),
        message="Family profile removed successfully.",
    )


@router.post("/bootstrap", response_model=FamilyMemberBootstrapResponse)
async def bootstrap_family_members(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FamilyMemberBootstrapResponse:
    created_count = await ensure_linked_family_members_for_household(
        session,
        household_id=current_user.household_id,
    )
    await session.commit()

    members = await list_household_family_members(
        session,
        household_id=current_user.household_id,
        include_inactive=False,
    )
    linked_user_names = await _resolve_linked_user_name_map(session, members)
    return FamilyMemberBootstrapResponse(
        created_count=created_count,
        items=[_to_family_member_response(member, linked_user_names) for member in members],
    )
