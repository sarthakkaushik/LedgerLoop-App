from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.household_category import HouseholdCategory
from app.models.household_subcategory import HouseholdSubcategory

DEFAULT_CATEGORY_NAMES = [
    "Groceries",
    "Food",
    "Dining",
    "Transport",
    "Fuel",
    "Shopping",
    "Utilities",
    "Rent",
    "EMI",
    "Healthcare",
    "Education",
    "Entertainment",
    "Travel",
    "Bills",
    "Gift",
    "Other",
]


def normalize_taxonomy_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def clean_taxonomy_name(name: str) -> str:
    return " ".join(name.strip().split())


async def seed_default_household_taxonomy(
    session: AsyncSession,
    *,
    household_id: UUID,
    created_by_user_id: UUID | None = None,
) -> None:
    existing_result = await session.execute(
        select(HouseholdCategory.normalized_name).where(
            HouseholdCategory.household_id == household_id
        )
    )
    existing_normalized = {value for value in existing_result.scalars().all() if value}
    now = datetime.now(UTC).replace(tzinfo=None)

    for order, category_name in enumerate(DEFAULT_CATEGORY_NAMES):
        normalized = normalize_taxonomy_name(category_name)
        if normalized in existing_normalized:
            continue
        session.add(
            HouseholdCategory(
                household_id=household_id,
                name=category_name,
                normalized_name=normalized,
                is_active=True,
                sort_order=order,
                created_by_user_id=created_by_user_id,
                created_at=now,
                updated_at=now,
            )
        )


async def load_household_taxonomy(
    session: AsyncSession,
    *,
    household_id: UUID,
    include_inactive: bool = False,
) -> tuple[list[HouseholdCategory], dict[UUID, list[HouseholdSubcategory]]]:
    category_stmt = select(HouseholdCategory).where(HouseholdCategory.household_id == household_id)
    if not include_inactive:
        category_stmt = category_stmt.where(HouseholdCategory.is_active.is_(True))
    category_stmt = category_stmt.order_by(HouseholdCategory.sort_order.asc(), HouseholdCategory.name.asc())
    categories_result = await session.execute(category_stmt)
    categories = categories_result.scalars().all()
    if not categories:
        return [], {}

    category_ids = [category.id for category in categories]
    sub_stmt = select(HouseholdSubcategory).where(
        HouseholdSubcategory.household_category_id.in_(category_ids)
    )
    if not include_inactive:
        sub_stmt = sub_stmt.where(HouseholdSubcategory.is_active.is_(True))
    sub_stmt = sub_stmt.order_by(
        HouseholdSubcategory.sort_order.asc(),
        HouseholdSubcategory.name.asc(),
    )
    subcategories_result = await session.execute(sub_stmt)
    subcategories = subcategories_result.scalars().all()

    grouped: dict[UUID, list[HouseholdSubcategory]] = defaultdict(list)
    for subcategory in subcategories:
        grouped[subcategory.household_category_id].append(subcategory)
    return categories, dict(grouped)


async def build_household_taxonomy_map(
    session: AsyncSession,
    *,
    household_id: UUID,
) -> tuple[list[str], dict[str, list[str]]]:
    categories, grouped_subcategories = await load_household_taxonomy(
        session, household_id=household_id
    )
    category_names: list[str] = []
    taxonomy: dict[str, list[str]] = {}
    for category in categories:
        cleaned = clean_taxonomy_name(category.name)
        if not cleaned:
            continue
        category_names.append(cleaned)
        taxonomy[cleaned] = [
            clean_taxonomy_name(subcategory.name)
            for subcategory in grouped_subcategories.get(category.id, [])
            if clean_taxonomy_name(subcategory.name)
        ]
    return category_names, taxonomy
