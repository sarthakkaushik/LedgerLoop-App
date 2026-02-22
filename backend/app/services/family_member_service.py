from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.family_member import FamilyMember, FamilyMemberType
from app.models.user import User


def clean_family_member_name(name: str) -> str:
    return " ".join(str(name or "").strip().split())


def normalize_family_member_name(name: str) -> str:
    return " ".join(str(name or "").strip().lower().split())


def _current_time() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def list_household_family_members(
    session: AsyncSession,
    *,
    household_id: UUID,
    include_inactive: bool = False,
) -> list[FamilyMember]:
    stmt = select(FamilyMember).where(FamilyMember.household_id == household_id)
    if not include_inactive:
        stmt = stmt.where(FamilyMember.is_active.is_(True))
    stmt = stmt.order_by(FamilyMember.created_at.asc(), FamilyMember.full_name.asc())
    result = await session.execute(stmt)
    return result.scalars().all()


async def ensure_linked_family_members_for_household(
    session: AsyncSession,
    *,
    household_id: UUID,
) -> int:
    users_result = await session.execute(
        select(User)
        .where(
            User.household_id == household_id,
            User.is_active.is_(True),
        )
        .order_by(User.created_at.asc())
    )
    users = users_result.scalars().all()
    if not users:
        return 0

    members_result = await session.execute(
        select(FamilyMember).where(FamilyMember.household_id == household_id)
    )
    members = members_result.scalars().all()
    members_by_linked_user = {member.linked_user_id: member for member in members if member.linked_user_id}
    active_name_set = {
        normalize_family_member_name(member.normalized_name or member.full_name)
        for member in members
        if member.is_active
    }
    now = _current_time()
    created_count = 0

    for user in users:
        existing = members_by_linked_user.get(user.id)
        cleaned = clean_family_member_name(user.full_name)
        normalized = normalize_family_member_name(cleaned)
        if existing:
            updated = False
            if cleaned and existing.full_name != cleaned:
                existing.full_name = cleaned
                updated = True
            if normalized and existing.normalized_name != normalized:
                existing.normalized_name = normalized
                updated = True
            if existing.member_type != FamilyMemberType.ADULT:
                existing.member_type = FamilyMemberType.ADULT
                updated = True
            if not existing.is_active:
                existing.is_active = True
                updated = True
            if updated:
                existing.updated_at = now
                session.add(existing)
            continue

        base_name = cleaned or "Household Member"
        candidate_name = base_name
        candidate_normalized = normalize_family_member_name(candidate_name)
        suffix = 2
        while candidate_normalized and candidate_normalized in active_name_set:
            candidate_name = f"{base_name} ({suffix})"
            candidate_normalized = normalize_family_member_name(candidate_name)
            suffix += 1

        new_member = FamilyMember(
            household_id=household_id,
            full_name=candidate_name,
            normalized_name=candidate_normalized or normalize_family_member_name(base_name),
            member_type=FamilyMemberType.ADULT,
            linked_user_id=user.id,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add(new_member)
        members_by_linked_user[user.id] = new_member
        if candidate_normalized:
            active_name_set.add(candidate_normalized)
        created_count += 1

    if created_count:
        await session.flush()

    return created_count


async def resolve_default_family_member_id_for_user(
    session: AsyncSession,
    *,
    user: User,
) -> UUID:
    await ensure_linked_family_members_for_household(
        session,
        household_id=user.household_id,
    )
    members = await list_household_family_members(
        session,
        household_id=user.household_id,
        include_inactive=False,
    )
    linked = next((member for member in members if member.linked_user_id == user.id), None)
    if linked:
        return linked.id

    first_adult = next((member for member in members if member.member_type == FamilyMemberType.ADULT), None)
    if first_adult:
        return first_adult.id
    if members:
        return members[0].id

    now = _current_time()
    cleaned_name = clean_family_member_name(user.full_name) or "Household Member"
    fallback = FamilyMember(
        household_id=user.household_id,
        full_name=cleaned_name,
        normalized_name=normalize_family_member_name(cleaned_name),
        member_type=FamilyMemberType.ADULT,
        linked_user_id=user.id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(fallback)
    await session.flush()
    return fallback.id


async def get_family_member_by_id(
    session: AsyncSession,
    *,
    household_id: UUID,
    family_member_id: UUID,
    active_only: bool = True,
) -> FamilyMember | None:
    stmt = select(FamilyMember).where(
        FamilyMember.id == family_member_id,
        FamilyMember.household_id == household_id,
    )
    if active_only:
        stmt = stmt.where(FamilyMember.is_active.is_(True))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def is_family_member_name_taken(
    session: AsyncSession,
    *,
    household_id: UUID,
    normalized_name: str,
    exclude_member_id: UUID | None = None,
) -> bool:
    stmt = select(FamilyMember.id).where(
        FamilyMember.household_id == household_id,
        FamilyMember.is_active.is_(True),
        FamilyMember.normalized_name == normalized_name,
    )
    if exclude_member_id:
        stmt = stmt.where(FamilyMember.id != exclude_member_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None
