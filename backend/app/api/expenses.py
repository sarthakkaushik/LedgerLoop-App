from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.deps import get_current_user, get_expense_parser, get_llm_parse_context
from app.core.db import get_session
from app.models.expense import Expense, ExpenseStatus
from app.models.user import User
from app.schemas.expense import (
    DashboardCategoryPoint,
    DashboardDailyPoint,
    DashboardMonthlyPoint,
    DashboardUserPoint,
    ExpenseFeedItem,
    ExpenseFeedResponse,
    ExpenseDashboardResponse,
    ExpenseConfirmEdit,
    ExpenseConfirmRequest,
    ExpenseConfirmResponse,
    ExpenseDraft,
    ExpenseLogRequest,
    ExpenseLogResponse,
)
from app.services.llm.base import ExpenseParserProvider
from app.services.llm.provider_factory import ProviderNotConfiguredError
from app.services.llm.types import ParseContext

router = APIRouter(prefix="/expenses", tags=["expenses"])


def _parse_date_incurred(value: str | None, fallback: date) -> date:
    if not value:
        return fallback
    try:
        return date.fromisoformat(value)
    except ValueError:
        return fallback


def _to_expense_draft(expense: Expense) -> ExpenseDraft:
    return ExpenseDraft(
        id=str(expense.id),
        amount=expense.amount,
        currency=expense.currency,
        category=expense.category,
        description=expense.description,
        merchant_or_item=expense.merchant_or_item,
        date_incurred=str(expense.date_incurred),
        is_recurring=expense.is_recurring,
        confidence=expense.confidence,
    )


def _to_expense_feed_item(expense: Expense, logged_by_name: str) -> ExpenseFeedItem:
    return ExpenseFeedItem(
        id=str(expense.id),
        amount=expense.amount,
        currency=expense.currency,
        category=expense.category,
        description=expense.description,
        merchant_or_item=expense.merchant_or_item,
        date_incurred=str(expense.date_incurred),
        is_recurring=expense.is_recurring,
        status=expense.status.value if hasattr(expense.status, "value") else str(expense.status),
        logged_by_user_id=str(expense.logged_by_user_id),
        logged_by_name=logged_by_name,
        created_at=expense.created_at.isoformat(),
        updated_at=expense.updated_at.isoformat(),
    )


def _first_day_of_month(value: date) -> date:
    return value.replace(day=1)


def _last_day_of_month(value: date) -> date:
    first_next = _shift_months(_first_day_of_month(value), 1)
    return first_next - timedelta(days=1)


def _shift_months(value: date, delta_months: int) -> date:
    month_index = (value.month - 1) + delta_months
    year = value.year + (month_index // 12)
    month = (month_index % 12) + 1
    return date(year, month, 1)


@router.post("/log", response_model=ExpenseLogResponse)
async def log_expenses(
    payload: ExpenseLogRequest,
    parser: ExpenseParserProvider = Depends(get_expense_parser),
    context: ParseContext = Depends(get_llm_parse_context),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ExpenseLogResponse:
    try:
        parsed = await parser.parse_expenses(payload.text, context)
    except ProviderNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    if parsed.mode == "chat":
        return ExpenseLogResponse(
            mode="chat",
            assistant_message=parsed.assistant_message,
            expenses=[],
            needs_clarification=False,
            clarification_questions=[],
        )

    if not parsed.expenses:
        return ExpenseLogResponse(
            mode="expense",
            assistant_message=parsed.assistant_message,
            expenses=[],
            needs_clarification=parsed.needs_clarification,
            clarification_questions=parsed.clarification_questions,
        )

    new_drafts: list[Expense] = []
    for parsed_expense in parsed.expenses:
        draft = Expense(
            household_id=user.household_id,
            logged_by_user_id=user.id,
            amount=parsed_expense.amount,
            currency=(parsed_expense.currency or context.default_currency).upper(),
            category=parsed_expense.category,
            description=parsed_expense.description,
            merchant_or_item=parsed_expense.merchant_or_item,
            date_incurred=_parse_date_incurred(
                parsed_expense.date_incurred, context.reference_date
            ),
            is_recurring=parsed_expense.is_recurring,
            confidence=parsed_expense.confidence,
            status=ExpenseStatus.DRAFT,
            source_text=payload.text,
        )
        session.add(draft)
        new_drafts.append(draft)

    await session.commit()
    for draft in new_drafts:
        await session.refresh(draft)

    return ExpenseLogResponse(
        mode="expense",
        assistant_message=parsed.assistant_message,
        expenses=[_to_expense_draft(expense) for expense in new_drafts],
        needs_clarification=parsed.needs_clarification,
        clarification_questions=parsed.clarification_questions,
    )


@router.post("/confirm", response_model=ExpenseConfirmResponse)
async def confirm_expenses(
    payload: ExpenseConfirmRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ExpenseConfirmResponse:
    idempotency_key = payload.idempotency_key.strip()

    replay_result = await session.execute(
        select(Expense)
        .where(
            Expense.household_id == user.household_id,
            Expense.status == ExpenseStatus.CONFIRMED,
            Expense.idempotency_key == idempotency_key,
        )
        .order_by(Expense.created_at)
    )
    replay_expenses = replay_result.scalars().all()
    if replay_expenses:
        return ExpenseConfirmResponse(
            confirmed_count=len(replay_expenses),
            idempotent_replay=True,
            expenses=[_to_expense_draft(expense) for expense in replay_expenses],
        )

    expense_updates: dict[UUID, ExpenseConfirmEdit] = {}
    for update in payload.expenses:
        try:
            draft_id = UUID(update.draft_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid draft_id '{update.draft_id}'",
            ) from exc
        if draft_id in expense_updates:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Duplicate draft_id '{update.draft_id}' in request",
            )
        expense_updates[draft_id] = update

    draft_result = await session.execute(
        select(Expense).where(
            Expense.id.in_(list(expense_updates.keys())),
            Expense.household_id == user.household_id,
            Expense.status == ExpenseStatus.DRAFT,
        )
    )
    draft_expenses = draft_result.scalars().all()
    if len(draft_expenses) != len(expense_updates):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more draft expenses were not found for this household.",
        )

    now = datetime.now(UTC).replace(tzinfo=None)
    for expense in draft_expenses:
        update = expense_updates[expense.id]

        if update.amount is not None:
            expense.amount = update.amount
        if update.currency is not None and update.currency.strip():
            expense.currency = update.currency.strip().upper()
        if update.category is not None:
            expense.category = update.category.strip() or None
        if update.description is not None:
            expense.description = update.description.strip() or None
        if update.merchant_or_item is not None:
            expense.merchant_or_item = update.merchant_or_item.strip() or None
        if update.date_incurred is not None:
            try:
                expense.date_incurred = date.fromisoformat(update.date_incurred)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid date_incurred for draft_id '{update.draft_id}'",
                ) from exc
        if update.is_recurring is not None:
            expense.is_recurring = update.is_recurring

        if expense.amount is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Amount is required before confirmation for draft_id '{expense.id}'",
            )

        expense.status = ExpenseStatus.CONFIRMED
        expense.idempotency_key = idempotency_key
        expense.updated_at = now
        session.add(expense)

    await session.commit()

    confirmed_result = await session.execute(
        select(Expense)
        .where(
            Expense.household_id == user.household_id,
            Expense.status == ExpenseStatus.CONFIRMED,
            Expense.idempotency_key == idempotency_key,
        )
        .order_by(Expense.created_at)
    )
    confirmed_expenses = confirmed_result.scalars().all()

    return ExpenseConfirmResponse(
        confirmed_count=len(confirmed_expenses),
        idempotent_replay=False,
        expenses=[_to_expense_draft(expense) for expense in confirmed_expenses],
    )


@router.get("/list", response_model=ExpenseFeedResponse)
async def list_expenses(
    status_filter: Literal["confirmed", "draft", "all"] = Query(
        default="confirmed",
        alias="status",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ExpenseFeedResponse:
    filters = [Expense.household_id == user.household_id]
    if status_filter != "all":
        filters.append(Expense.status == ExpenseStatus(status_filter))

    list_result = await session.execute(
        select(Expense)
        .where(*filters)
        .order_by(Expense.date_incurred.desc(), Expense.created_at.desc())
        .limit(limit)
    )
    expenses = list_result.scalars().all()

    user_ids = {expense.logged_by_user_id for expense in expenses}
    user_names: dict[UUID, str] = {}
    if user_ids:
        users_result = await session.execute(select(User).where(User.id.in_(list(user_ids))))
        user_names = {
            member.id: member.full_name
            for member in users_result.scalars().all()
        }

    total_result = await session.execute(
        select(func.count())
        .select_from(Expense)
        .where(*filters)
    )
    total_count = int(total_result.scalar_one() or 0)

    return ExpenseFeedResponse(
        items=[
            _to_expense_feed_item(
                expense,
                user_names.get(expense.logged_by_user_id, "Unknown"),
            )
            for expense in expenses
        ],
        total_count=total_count,
    )


@router.get("/dashboard", response_model=ExpenseDashboardResponse)
async def get_expense_dashboard(
    months_back: int = Query(default=6, ge=1, le=24),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ExpenseDashboardResponse:
    today = datetime.now(UTC).date()
    period_start = _first_day_of_month(today)
    period_end = _last_day_of_month(today)

    period_result = await session.execute(
        select(Expense).where(
            Expense.household_id == user.household_id,
            Expense.status == ExpenseStatus.CONFIRMED,
            Expense.date_incurred >= period_start,
            Expense.date_incurred <= period_end,
        )
    )
    period_expenses = period_result.scalars().all()

    trend_start = _shift_months(period_start, -(months_back - 1))
    trend_result = await session.execute(
        select(Expense).where(
            Expense.household_id == user.household_id,
            Expense.status == ExpenseStatus.CONFIRMED,
            Expense.date_incurred >= trend_start,
            Expense.date_incurred <= period_end,
        )
    )
    trend_expenses = trend_result.scalars().all()

    user_ids = {expense.logged_by_user_id for expense in period_expenses}
    user_names: dict[UUID, str] = {}
    if user_ids:
        users_result = await session.execute(select(User).where(User.id.in_(list(user_ids))))
        user_names = {member.id: member.full_name for member in users_result.scalars().all()}

    total_spend = 0.0
    expense_count = 0
    daily_totals: dict[str, float] = defaultdict(float)
    category_totals: dict[str, float] = defaultdict(float)
    category_counts: dict[str, int] = defaultdict(int)
    user_totals: dict[UUID, float] = defaultdict(float)
    user_counts: dict[UUID, int] = defaultdict(int)

    for expense in period_expenses:
        if expense.amount is None:
            continue
        amount = float(expense.amount)
        total_spend += amount
        expense_count += 1

        day_key = str(expense.date_incurred)
        daily_totals[day_key] += amount

        category = expense.category or "Other"
        category_totals[category] += amount
        category_counts[category] += 1

        user_totals[expense.logged_by_user_id] += amount
        user_counts[expense.logged_by_user_id] += 1

    monthly_totals: dict[str, float] = defaultdict(float)
    for expense in trend_expenses:
        if expense.amount is None:
            continue
        month_key = expense.date_incurred.strftime("%Y-%m")
        monthly_totals[month_key] += float(expense.amount)

    daily_burn = [
        DashboardDailyPoint(day=day, total=round(total, 2))
        for day, total in sorted(daily_totals.items())
    ]
    category_split = [
        DashboardCategoryPoint(
            category=category,
            total=round(total, 2),
            count=category_counts[category],
        )
        for category, total in sorted(
            category_totals.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]
    user_split = [
        DashboardUserPoint(
            user_id=str(user_id),
            user_name=user_names.get(user_id, "Unknown"),
            total=round(total, 2),
            count=user_counts[user_id],
        )
        for user_id, total in sorted(
            user_totals.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]

    monthly_trend: list[DashboardMonthlyPoint] = []
    for offset in range(months_back):
        month_start = _shift_months(period_start, -(months_back - 1 - offset))
        key = month_start.strftime("%Y-%m")
        monthly_trend.append(
            DashboardMonthlyPoint(
                month=key,
                total=round(monthly_totals.get(key, 0.0), 2),
            )
        )

    return ExpenseDashboardResponse(
        period_month=period_start.strftime("%Y-%m"),
        period_start=str(period_start),
        period_end=str(period_end),
        total_spend=round(total_spend, 2),
        expense_count=expense_count,
        daily_burn=daily_burn,
        category_split=category_split,
        user_split=user_split,
        monthly_trend=monthly_trend,
    )
