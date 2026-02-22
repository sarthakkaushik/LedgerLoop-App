from collections.abc import AsyncIterator

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.core.config import get_settings
from app.models.household import DEFAULT_MONTHLY_BUDGET

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        await conn.run_sync(_ensure_user_is_active_column)
        await conn.run_sync(_ensure_expense_subcategory_column)
        await conn.run_sync(_ensure_expense_attributed_family_member_column)
        await conn.run_sync(_ensure_household_monthly_budget_column)


def _ensure_user_is_active_column(sync_conn) -> None:
    inspector = inspect(sync_conn)
    table_names = set(inspector.get_table_names())
    if "users" not in table_names:
        return

    column_names = {column["name"] for column in inspector.get_columns("users")}
    if "is_active" in column_names:
        return

    dialect = sync_conn.dialect.name
    if dialect == "postgresql":
        sync_conn.exec_driver_sql(
            "ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE"
        )
    else:
        sync_conn.exec_driver_sql(
            "ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"
        )


def _ensure_expense_subcategory_column(sync_conn) -> None:
    inspector = inspect(sync_conn)
    table_names = set(inspector.get_table_names())
    if "expenses" not in table_names:
        return

    column_names = {column["name"] for column in inspector.get_columns("expenses")}
    if "subcategory" in column_names:
        return

    sync_conn.exec_driver_sql("ALTER TABLE expenses ADD COLUMN subcategory VARCHAR(80)")


def _ensure_expense_attributed_family_member_column(sync_conn) -> None:
    inspector = inspect(sync_conn)
    table_names = set(inspector.get_table_names())
    if "expenses" not in table_names:
        return

    column_names = {column["name"] for column in inspector.get_columns("expenses")}
    if "attributed_family_member_id" not in column_names:
        dialect = sync_conn.dialect.name
        if dialect == "postgresql":
            sync_conn.exec_driver_sql(
                "ALTER TABLE expenses ADD COLUMN attributed_family_member_id UUID"
            )
        else:
            sync_conn.exec_driver_sql(
                "ALTER TABLE expenses ADD COLUMN attributed_family_member_id VARCHAR(36)"
            )

    index_names = {index.get("name", "") for index in inspector.get_indexes("expenses")}
    if "ix_expenses_attributed_family_member_id" not in index_names:
        sync_conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_expenses_attributed_family_member_id "
            "ON expenses (attributed_family_member_id)"
        )


def _ensure_household_monthly_budget_column(sync_conn) -> None:
    inspector = inspect(sync_conn)
    table_names = set(inspector.get_table_names())
    if "households" not in table_names:
        return

    column_names = {column["name"] for column in inspector.get_columns("households")}
    if "monthly_budget" in column_names:
        return

    sync_conn.exec_driver_sql(
        "ALTER TABLE households ADD COLUMN monthly_budget FLOAT NOT NULL DEFAULT "
        f"{DEFAULT_MONTHLY_BUDGET}"
    )
