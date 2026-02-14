from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession


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

