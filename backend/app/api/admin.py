import csv
from datetime import UTC, date, datetime
from enum import Enum
import io
from uuid import UUID
import zipfile

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, select

from app.api.deps import get_current_super_admin
from app.core.db import get_session
from app.models.analysis_query import AnalysisQuery
from app.models.analysis_query_attempt import AnalysisQueryAttempt
from app.models.expense import Expense
from app.models.family_member import FamilyMember
from app.models.household import Household
from app.models.household_category import HouseholdCategory
from app.models.household_subcategory import HouseholdSubcategory
from app.models.llm_setting import LLMSetting
from app.models.user import User
from app.models.user_login_event import UserLoginEvent
from app.schemas.admin import (
    AdminHouseholdSummary,
    AdminOverviewResponse,
    AdminSchemaColumn,
    AdminSchemaMapResponse,
    AdminSchemaRelation,
    AdminSchemaTable,
    AdminTableSummary,
    AdminUserBehavior,
)

router = APIRouter(prefix="/admin", tags=["admin"])

EXPORT_TABLE_MODELS: dict[str, type[SQLModel]] = {
    "households": Household,
    "users": User,
    "user_login_events": UserLoginEvent,
    "family_members": FamilyMember,
    "expenses": Expense,
    "household_categories": HouseholdCategory,
    "household_subcategories": HouseholdSubcategory,
    "llm_settings": LLMSetting,
    "analysis_queries": AnalysisQuery,
    "analysis_query_attempts": AnalysisQueryAttempt,
}


def _serialize_csv_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


async def _count_rows(session: AsyncSession, model: type[SQLModel]) -> int:
    result = await session.execute(select(func.count()).select_from(model))
    return int(result.scalar_one() or 0)


async def _build_table_csv_payload(session: AsyncSession, table_name: str) -> str:
    model = EXPORT_TABLE_MODELS.get(table_name)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown table '{table_name}'",
        )

    result = await session.execute(select(model))
    records = result.scalars().all()
    columns = [column.name for column in model.__table__.columns]

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for record in records:
        writer.writerow([_serialize_csv_value(getattr(record, column)) for column in columns])
    return buffer.getvalue()


@router.get("/overview", response_model=AdminOverviewResponse)
async def admin_overview(
    _super_admin: User = Depends(get_current_super_admin),
    session: AsyncSession = Depends(get_session),
) -> AdminOverviewResponse:
    users_result = await session.execute(select(User).order_by(User.created_at.asc()))
    users = users_result.scalars().all()

    households_result = await session.execute(
        select(Household).order_by(Household.created_at.asc(), Household.name.asc())
    )
    households = households_result.scalars().all()
    households_by_id = {household.id: household for household in households}

    household_user_counts_result = await session.execute(
        select(User.household_id, func.count())
        .group_by(User.household_id)
    )
    household_user_counts = {
        household_id: int(count or 0)
        for household_id, count in household_user_counts_result.all()
    }

    household_member_counts_result = await session.execute(
        select(FamilyMember.household_id, func.count())
        .group_by(FamilyMember.household_id)
    )
    household_member_counts = {
        household_id: int(count or 0)
        for household_id, count in household_member_counts_result.all()
    }

    household_expense_counts_result = await session.execute(
        select(Expense.household_id, func.count())
        .group_by(Expense.household_id)
    )
    household_expense_counts = {
        household_id: int(count or 0)
        for household_id, count in household_expense_counts_result.all()
    }

    user_expense_counts_result = await session.execute(
        select(Expense.logged_by_user_id, func.count())
        .group_by(Expense.logged_by_user_id)
    )
    user_expense_counts = {
        user_id: int(count or 0)
        for user_id, count in user_expense_counts_result.all()
    }

    last_login_result = await session.execute(
        select(UserLoginEvent.user_id, func.max(UserLoginEvent.login_at))
        .group_by(UserLoginEvent.user_id)
    )
    last_login_by_user = {
        user_id: login_at
        for user_id, login_at in last_login_result.all()
    }

    user_rows = [
        AdminUserBehavior(
            user_id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            role=user.role.value if hasattr(user.role, "value") else str(user.role),
            is_active=bool(user.is_active),
            household_id=str(user.household_id),
            household_name=households_by_id.get(user.household_id).name
            if households_by_id.get(user.household_id)
            else "Unknown",
            household_member_count=household_member_counts.get(user.household_id, 0),
            expense_entries_count=user_expense_counts.get(user.id, 0),
            last_login_at=(
                last_login_by_user.get(user.id).isoformat()
                if last_login_by_user.get(user.id) is not None
                else None
            ),
            created_at=user.created_at.isoformat(),
        )
        for user in users
    ]

    household_rows = [
        AdminHouseholdSummary(
            household_id=str(household.id),
            household_name=household.name,
            user_count=household_user_counts.get(household.id, 0),
            family_member_count=household_member_counts.get(household.id, 0),
            expense_count=household_expense_counts.get(household.id, 0),
            created_at=household.created_at.isoformat(),
        )
        for household in households
    ]

    table_rows: list[AdminTableSummary] = []
    for table_name, model in EXPORT_TABLE_MODELS.items():
        table_rows.append(
            AdminTableSummary(
                table_name=table_name,
                row_count=await _count_rows(session, model),
            )
        )

    total_expenses = int(sum(user_expense_counts.values()))
    total_members = int(sum(household_member_counts.values()))

    return AdminOverviewResponse(
        generated_at=datetime.now(UTC).replace(tzinfo=None).isoformat(),
        total_users=len(users),
        active_users=sum(1 for user in users if user.is_active),
        total_households=len(households),
        total_family_members=total_members,
        total_expenses=total_expenses,
        users=user_rows,
        households=household_rows,
        tables=table_rows,
    )


@router.get("/schema", response_model=AdminSchemaMapResponse)
async def admin_schema_map(
    _super_admin: User = Depends(get_current_super_admin),
) -> AdminSchemaMapResponse:
    tables: list[AdminSchemaTable] = []
    relations: list[AdminSchemaRelation] = []

    for table in sorted(SQLModel.metadata.sorted_tables, key=lambda item: item.name):
        columns = [
            AdminSchemaColumn(
                name=column.name,
                data_type=str(column.type),
                nullable=bool(column.nullable),
                is_primary_key=bool(column.primary_key),
            )
            for column in table.columns
        ]
        tables.append(AdminSchemaTable(table_name=table.name, columns=columns))

        for foreign_key in table.foreign_keys:
            relations.append(
                AdminSchemaRelation(
                    from_table=table.name,
                    from_column=foreign_key.parent.name,
                    to_table=foreign_key.column.table.name,
                    to_column=foreign_key.column.name,
                )
            )

    relations.sort(key=lambda item: (item.from_table, item.from_column, item.to_table, item.to_column))
    return AdminSchemaMapResponse(tables=tables, relations=relations)


@router.get("/export/{table_name}.csv")
async def export_table_csv(
    table_name: str,
    _super_admin: User = Depends(get_current_super_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    normalized = table_name.strip().lower()
    payload = await _build_table_csv_payload(session, normalized)
    filename = f"{normalized}_{datetime.now(UTC).date().isoformat()}.csv"
    return Response(
        content=payload,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/all.zip")
async def export_all_tables_zip(
    _super_admin: User = Depends(get_current_super_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for table_name in EXPORT_TABLE_MODELS:
            archive.writestr(f"{table_name}.csv", await _build_table_csv_payload(session, table_name))

    filename = f"expense_tracker_all_tables_{datetime.now(UTC).date().isoformat()}.zip"
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
