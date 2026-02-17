from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.deps import get_current_admin, get_current_user
from app.core.db import get_session
from app.models.household_category import HouseholdCategory
from app.models.household_subcategory import HouseholdSubcategory
from app.models.user import User
from app.schemas.taxonomy import (
    CategoryCreateRequest,
    CategoryUpdateRequest,
    SubcategoryCreateRequest,
    SubcategoryUpdateRequest,
    TaxonomyCategoryItem,
    TaxonomyListResponse,
    TaxonomySubcategoryItem,
)
from app.services.taxonomy_service import (
    clean_taxonomy_name,
    load_household_taxonomy,
    normalize_taxonomy_name,
    seed_default_household_taxonomy,
)

router = APIRouter(prefix="/settings/taxonomy", tags=["settings"])


def _to_taxonomy_response(
    categories: list[HouseholdCategory],
    grouped_subcategories: dict[UUID, list[HouseholdSubcategory]],
) -> TaxonomyListResponse:
    return TaxonomyListResponse(
        categories=[
            TaxonomyCategoryItem(
                id=str(category.id),
                name=category.name,
                is_active=category.is_active,
                sort_order=category.sort_order,
                subcategories=[
                    TaxonomySubcategoryItem(
                        id=str(subcategory.id),
                        name=subcategory.name,
                        is_active=subcategory.is_active,
                        sort_order=subcategory.sort_order,
                    )
                    for subcategory in grouped_subcategories.get(category.id, [])
                ],
            )
            for category in categories
        ]
    )


def _parse_uuid(value: str, *, field_name: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {field_name}",
        ) from exc


async def _get_household_category(
    session: AsyncSession,
    *,
    household_id: UUID,
    category_id: UUID,
) -> HouseholdCategory:
    result = await session.execute(
        select(HouseholdCategory).where(
            HouseholdCategory.id == category_id,
            HouseholdCategory.household_id == household_id,
        )
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found for this household.",
        )
    return category


async def _get_household_subcategory(
    session: AsyncSession,
    *,
    household_id: UUID,
    subcategory_id: UUID,
) -> tuple[HouseholdSubcategory, HouseholdCategory]:
    result = await session.execute(
        select(HouseholdSubcategory).where(HouseholdSubcategory.id == subcategory_id)
    )
    subcategory = result.scalar_one_or_none()
    if not subcategory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subcategory not found.",
        )
    category = await _get_household_category(
        session,
        household_id=household_id,
        category_id=subcategory.household_category_id,
    )
    return subcategory, category


async def _next_category_sort_order(session: AsyncSession, household_id: UUID) -> int:
    result = await session.execute(
        select(HouseholdCategory.sort_order).where(HouseholdCategory.household_id == household_id)
    )
    values = [value for value in result.scalars().all() if value is not None]
    if not values:
        return 0
    return max(values) + 1


async def _next_subcategory_sort_order(
    session: AsyncSession, household_category_id: UUID
) -> int:
    result = await session.execute(
        select(HouseholdSubcategory.sort_order).where(
            HouseholdSubcategory.household_category_id == household_category_id
        )
    )
    values = [value for value in result.scalars().all() if value is not None]
    if not values:
        return 0
    return max(values) + 1


async def _fetch_taxonomy_response(
    session: AsyncSession,
    *,
    household_id: UUID,
    seed_if_missing: bool = False,
    seed_user_id: UUID | None = None,
) -> TaxonomyListResponse:
    categories, grouped_subcategories = await load_household_taxonomy(
        session, household_id=household_id
    )
    if not categories and seed_if_missing:
        await seed_default_household_taxonomy(
            session,
            household_id=household_id,
            created_by_user_id=seed_user_id,
        )
        await session.commit()
        categories, grouped_subcategories = await load_household_taxonomy(
            session, household_id=household_id
        )
    return _to_taxonomy_response(categories, grouped_subcategories)


@router.get("", response_model=TaxonomyListResponse)
async def list_taxonomy(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TaxonomyListResponse:
    return await _fetch_taxonomy_response(
        session,
        household_id=user.household_id,
        seed_if_missing=True,
        seed_user_id=user.id,
    )


@router.post("/categories", response_model=TaxonomyListResponse)
async def create_category(
    payload: CategoryCreateRequest,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> TaxonomyListResponse:
    name = clean_taxonomy_name(payload.name)
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Category name cannot be empty.",
        )
    normalized = normalize_taxonomy_name(name)

    existing_result = await session.execute(
        select(HouseholdCategory).where(
            HouseholdCategory.household_id == admin.household_id,
            HouseholdCategory.normalized_name == normalized,
        )
    )
    existing = existing_result.scalar_one_or_none()
    now = datetime.now(UTC).replace(tzinfo=None)

    if existing and existing.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category already exists.",
        )
    if existing and not existing.is_active:
        existing.is_active = True
        existing.name = name
        existing.sort_order = (
            payload.sort_order
            if payload.sort_order is not None
            else await _next_category_sort_order(session, admin.household_id)
        )
        existing.updated_at = now
        session.add(existing)
    else:
        session.add(
            HouseholdCategory(
                household_id=admin.household_id,
                name=name,
                normalized_name=normalized,
                is_active=True,
                sort_order=(
                    payload.sort_order
                    if payload.sort_order is not None
                    else await _next_category_sort_order(session, admin.household_id)
                ),
                created_by_user_id=admin.id,
                created_at=now,
                updated_at=now,
            )
        )
    await session.commit()
    return await _fetch_taxonomy_response(session, household_id=admin.household_id)


@router.patch("/categories/{category_id}", response_model=TaxonomyListResponse)
async def update_category(
    category_id: str,
    payload: CategoryUpdateRequest,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> TaxonomyListResponse:
    category_uuid = _parse_uuid(category_id, field_name="category_id")
    category = await _get_household_category(
        session, household_id=admin.household_id, category_id=category_uuid
    )

    if payload.name is not None:
        name = clean_taxonomy_name(payload.name)
        if not name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Category name cannot be empty.",
            )
        normalized = normalize_taxonomy_name(name)
        duplicate_result = await session.execute(
            select(HouseholdCategory).where(
                HouseholdCategory.household_id == admin.household_id,
                HouseholdCategory.normalized_name == normalized,
                HouseholdCategory.id != category.id,
            )
        )
        if duplicate_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Category with this name already exists.",
            )
        category.name = name
        category.normalized_name = normalized

    if payload.sort_order is not None:
        category.sort_order = payload.sort_order
    if payload.is_active is not None:
        category.is_active = payload.is_active
        if not payload.is_active:
            subcategories_result = await session.execute(
                select(HouseholdSubcategory).where(
                    HouseholdSubcategory.household_category_id == category.id
                )
            )
            for subcategory in subcategories_result.scalars().all():
                subcategory.is_active = False
                subcategory.updated_at = datetime.now(UTC).replace(tzinfo=None)
                session.add(subcategory)

    category.updated_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(category)
    await session.commit()
    return await _fetch_taxonomy_response(session, household_id=admin.household_id)


@router.delete("/categories/{category_id}", response_model=TaxonomyListResponse)
async def delete_category(
    category_id: str,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> TaxonomyListResponse:
    category_uuid = _parse_uuid(category_id, field_name="category_id")
    category = await _get_household_category(
        session, household_id=admin.household_id, category_id=category_uuid
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    category.is_active = False
    category.updated_at = now
    session.add(category)

    subcategories_result = await session.execute(
        select(HouseholdSubcategory).where(HouseholdSubcategory.household_category_id == category.id)
    )
    for subcategory in subcategories_result.scalars().all():
        subcategory.is_active = False
        subcategory.updated_at = now
        session.add(subcategory)

    await session.commit()
    return await _fetch_taxonomy_response(session, household_id=admin.household_id)


@router.post("/categories/{category_id}/subcategories", response_model=TaxonomyListResponse)
async def create_subcategory(
    category_id: str,
    payload: SubcategoryCreateRequest,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> TaxonomyListResponse:
    category_uuid = _parse_uuid(category_id, field_name="category_id")
    category = await _get_household_category(
        session, household_id=admin.household_id, category_id=category_uuid
    )
    if not category.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot add subcategory to an inactive category.",
        )

    name = clean_taxonomy_name(payload.name)
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Subcategory name cannot be empty.",
        )
    normalized = normalize_taxonomy_name(name)
    now = datetime.now(UTC).replace(tzinfo=None)

    existing_result = await session.execute(
        select(HouseholdSubcategory).where(
            HouseholdSubcategory.household_category_id == category.id,
            HouseholdSubcategory.normalized_name == normalized,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing and existing.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Subcategory already exists for this category.",
        )
    if existing and not existing.is_active:
        existing.is_active = True
        existing.name = name
        existing.sort_order = (
            payload.sort_order
            if payload.sort_order is not None
            else await _next_subcategory_sort_order(session, category.id)
        )
        existing.updated_at = now
        session.add(existing)
    else:
        session.add(
            HouseholdSubcategory(
                household_category_id=category.id,
                name=name,
                normalized_name=normalized,
                is_active=True,
                sort_order=(
                    payload.sort_order
                    if payload.sort_order is not None
                    else await _next_subcategory_sort_order(session, category.id)
                ),
                created_by_user_id=admin.id,
                created_at=now,
                updated_at=now,
            )
        )
    await session.commit()
    return await _fetch_taxonomy_response(session, household_id=admin.household_id)


@router.patch("/subcategories/{subcategory_id}", response_model=TaxonomyListResponse)
async def update_subcategory(
    subcategory_id: str,
    payload: SubcategoryUpdateRequest,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> TaxonomyListResponse:
    subcategory_uuid = _parse_uuid(subcategory_id, field_name="subcategory_id")
    subcategory, category = await _get_household_subcategory(
        session, household_id=admin.household_id, subcategory_id=subcategory_uuid
    )

    if payload.name is not None:
        name = clean_taxonomy_name(payload.name)
        if not name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Subcategory name cannot be empty.",
            )
        normalized = normalize_taxonomy_name(name)
        duplicate_result = await session.execute(
            select(HouseholdSubcategory).where(
                HouseholdSubcategory.household_category_id == category.id,
                HouseholdSubcategory.normalized_name == normalized,
                HouseholdSubcategory.id != subcategory.id,
            )
        )
        if duplicate_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Subcategory with this name already exists in this category.",
            )
        subcategory.name = name
        subcategory.normalized_name = normalized

    if payload.sort_order is not None:
        subcategory.sort_order = payload.sort_order
    if payload.is_active is not None:
        subcategory.is_active = payload.is_active

    subcategory.updated_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(subcategory)
    await session.commit()
    return await _fetch_taxonomy_response(session, household_id=admin.household_id)


@router.delete("/subcategories/{subcategory_id}", response_model=TaxonomyListResponse)
async def delete_subcategory(
    subcategory_id: str,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> TaxonomyListResponse:
    subcategory_uuid = _parse_uuid(subcategory_id, field_name="subcategory_id")
    subcategory, _ = await _get_household_subcategory(
        session, household_id=admin.household_id, subcategory_id=subcategory_uuid
    )
    subcategory.is_active = False
    subcategory.updated_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(subcategory)
    await session.commit()
    return await _fetch_taxonomy_response(session, household_id=admin.household_id)
