from __future__ import annotations

from dataclasses import dataclass, field
from sqlalchemy import inspect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID


@dataclass(slots=True)
class HouseholdPromptContext:
    categories: list[str] = field(default_factory=list)
    members: list[str] = field(default_factory=list)
    merchants: list[str] = field(default_factory=list)

    def to_prompt_text(self) -> str:
        return (
            f"Known categories in this household: {', '.join(self.categories) if self.categories else 'none'}\n"
            f"Known household member names: {', '.join(self.members) if self.members else 'none'}\n"
            f"Known merchant_or_item values: {', '.join(self.merchants) if self.merchants else 'none'}"
        )


async def load_live_schema_text(
    session: AsyncSession,
    *,
    include_tables: tuple[str, ...] = ("expenses", "users"),
) -> str:
    """Load current DB table/column schema as prompt-ready text."""
    conn = await session.connection()

    def _read_schema(sync_conn) -> str:
        insp = inspect(sync_conn)
        available = set(insp.get_table_names())
        lines: list[str] = []
        for table in include_tables:
            if table not in available:
                continue
            cols = insp.get_columns(table)
            if not cols:
                continue
            col_parts = [
                f"{col['name']} {str(col.get('type', 'unknown'))}"
                for col in cols
            ]
            lines.append(f"{table}({', '.join(col_parts)})")
        return "\n".join(lines).strip()

    schema_text = await conn.run_sync(_read_schema)
    if schema_text:
        return schema_text
    return "No schema metadata available."


async def load_household_prompt_hints(
    session: AsyncSession,
    *,
    household_id: UUID,
    limit: int = 30,
) -> str:
    """Load household-specific values to improve SQL grounding."""
    context = await load_household_prompt_context(
        session,
        household_id=household_id,
        limit=limit,
    )
    return context.to_prompt_text()


async def load_household_prompt_context(
    session: AsyncSession,
    *,
    household_id: UUID,
    limit: int = 30,
) -> HouseholdPromptContext:
    """Load household-specific values as structured context."""
    params = {"household_id": str(household_id), "limit": limit}

    cat_query = text(
        """
        SELECT DISTINCT TRIM(COALESCE(category, 'Other')) AS category
        FROM expenses
        WHERE CAST(household_id AS TEXT) = :household_id
          AND category IS NOT NULL
          AND TRIM(category) <> ''
        ORDER BY category
        LIMIT :limit
        """
    )
    name_query = text(
        """
        SELECT DISTINCT TRIM(COALESCE(u.full_name, 'Unknown')) AS logged_by
        FROM expenses e
        LEFT JOIN users u ON u.id = e.logged_by_user_id
        WHERE CAST(e.household_id AS TEXT) = :household_id
        ORDER BY logged_by
        LIMIT :limit
        """
    )
    merchant_query = text(
        """
        SELECT DISTINCT TRIM(COALESCE(merchant_or_item, '')) AS merchant_or_item
        FROM expenses
        WHERE CAST(household_id AS TEXT) = :household_id
          AND merchant_or_item IS NOT NULL
          AND TRIM(merchant_or_item) <> ''
        ORDER BY merchant_or_item
        LIMIT :limit
        """
    )

    cat_res = await session.execute(cat_query, params)
    name_res = await session.execute(name_query, params)
    merchant_res = await session.execute(merchant_query, params)

    categories = [str(x) for x in cat_res.scalars().all() if x]
    names = [str(x) for x in name_res.scalars().all() if x]
    merchants = [str(x) for x in merchant_res.scalars().all() if x]

    return HouseholdPromptContext(
        categories=categories,
        members=names,
        merchants=merchants,
    )
