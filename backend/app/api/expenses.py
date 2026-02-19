from collections import defaultdict
import csv
from datetime import UTC, date, datetime, timedelta
import io
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.deps import get_current_user, get_expense_parser, get_llm_parse_context
from app.core.config import get_settings
from app.core.db import get_session
from app.models.expense import Expense, ExpenseStatus
from app.models.household_category import HouseholdCategory
from app.models.household_subcategory import HouseholdSubcategory
from app.models.user import User, UserRole
from app.schemas.expense import (
    ExpenseAudioTranscriptionResponse,
    DashboardCategoryPoint,
    DashboardDailyPoint,
    DashboardMonthlyPoint,
    DashboardUserPoint,
    ExpenseDeleteResponse,
    ExpenseFeedItem,
    ExpenseFeedResponse,
    ExpenseDashboardResponse,
    ExpenseConfirmEdit,
    ExpenseConfirmRequest,
    ExpenseConfirmResponse,
    ExpenseDraft,
    ExpenseLogRequest,
    ExpenseLogResponse,
    ExpenseRecurringUpdateRequest,
    ExpenseRecurringUpdateResponse,
    RecurringExpenseCreateRequest,
    RecurringExpenseCreateResponse,
)
from app.services.audio.groq_transcription import (
    GroqTranscriptionConfigError,
    GroqTranscriptionUpstreamError,
    transcribe_audio_with_groq,
)
from app.services.llm.base import ExpenseParserProvider
from app.services.llm.provider_factory import ProviderNotConfiguredError
from app.services.llm.types import ParseContext
from app.services.taxonomy_service import normalize_taxonomy_name

router = APIRouter(prefix="/expenses", tags=["expenses"])
settings = get_settings()

ALLOWED_AUDIO_CONTENT_TYPES = {
    "audio/webm",
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/ogg",
}

AUDIO_EXTENSION_TO_CONTENT_TYPE = {
    "webm": "audio/webm",
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "mp4": "audio/mp4",
    "m4a": "audio/mp4",
    "ogg": "audio/ogg",
}


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
        subcategory=expense.subcategory,
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
        subcategory=expense.subcategory,
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


def _build_expense_filters(
    household_id: UUID,
    status_filter: Literal["confirmed", "draft", "all"],
    recurring_only: bool = False,
) -> list:
    filters = [Expense.household_id == household_id]
    if status_filter != "all":
        filters.append(Expense.status == ExpenseStatus(status_filter))
    if recurring_only:
        filters.append(Expense.is_recurring.is_(True))
    return filters


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    return cleaned or None


def _normalize_content_type(value: str | None) -> str:
    if not value:
        return ""
    return value.split(";")[0].strip().lower()


def _audio_extension_from_filename(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].strip().lower()


async def _load_taxonomy_lookup(
    session: AsyncSession,
    household_id: UUID,
) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    categories_result = await session.execute(
        select(HouseholdCategory).where(
            HouseholdCategory.household_id == household_id,
            HouseholdCategory.is_active.is_(True),
        )
    )
    categories = categories_result.scalars().all()
    category_lookup: dict[str, str] = {}
    category_ids: list[UUID] = []
    category_norm_by_id: dict[UUID, str] = {}
    for category in categories:
        normalized = normalize_taxonomy_name(category.name)
        if not normalized:
            continue
        cleaned_name = _clean_optional_text(category.name)
        if not cleaned_name:
            continue
        category_lookup[normalized] = cleaned_name
        category_ids.append(category.id)
        category_norm_by_id[category.id] = normalized

    subcategory_lookup: dict[str, dict[str, str]] = {}
    if category_ids:
        subcategories_result = await session.execute(
            select(HouseholdSubcategory).where(
                HouseholdSubcategory.household_category_id.in_(category_ids),
                HouseholdSubcategory.is_active.is_(True),
            )
        )
        for subcategory in subcategories_result.scalars().all():
            category_norm = category_norm_by_id.get(subcategory.household_category_id)
            if not category_norm:
                continue
            sub_norm = normalize_taxonomy_name(subcategory.name)
            if not sub_norm:
                continue
            cleaned_name = _clean_optional_text(subcategory.name)
            if not cleaned_name:
                continue
            subcategory_lookup.setdefault(category_norm, {})[sub_norm] = cleaned_name

    return category_lookup, subcategory_lookup


def _normalize_taxonomy_selection(
    *,
    category: str | None,
    subcategory: str | None,
    category_lookup: dict[str, str],
    subcategory_lookup: dict[str, dict[str, str]],
) -> tuple[str | None, str | None, list[str]]:
    warnings: list[str] = []
    cleaned_category = _clean_optional_text(category)
    cleaned_subcategory = _clean_optional_text(subcategory)
    if not cleaned_category:
        if cleaned_subcategory:
            warnings.append(
                f"Subcategory '{cleaned_subcategory}' was cleared because category was empty."
            )
        return None, None, warnings

    normalized_category = normalize_taxonomy_name(cleaned_category)
    resolved_category = category_lookup.get(normalized_category)
    if not resolved_category:
        warnings.append(
            f"Category '{cleaned_category}' was not in household taxonomy and was normalized to 'Other'."
        )
        return "Other", None, warnings

    if not cleaned_subcategory:
        return resolved_category, None, warnings

    resolved_subcategory = subcategory_lookup.get(normalized_category, {}).get(
        normalize_taxonomy_name(cleaned_subcategory)
    )
    if not resolved_subcategory:
        warnings.append(
            f"Subcategory '{cleaned_subcategory}' was not valid for category '{resolved_category}' and was cleared."
        )
        return resolved_category, None, warnings

    return resolved_category, resolved_subcategory, warnings


async def _resolve_user_names(
    session: AsyncSession,
    user_ids: set[UUID],
) -> dict[UUID, str]:
    if not user_ids:
        return {}
    users_result = await session.execute(select(User).where(User.id.in_(list(user_ids))))
    return {member.id: member.full_name for member in users_result.scalars().all()}


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
            subcategory=parsed_expense.subcategory,
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


@router.post("/transcribe-audio", response_model=ExpenseAudioTranscriptionResponse)
async def transcribe_audio(
    audio_file: UploadFile = File(...),
    language: str | None = Form(default=None),
    user: User = Depends(get_current_user),
) -> ExpenseAudioTranscriptionResponse:
    _ = user
    audio_bytes = await audio_file.read()
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Audio file is empty.",
        )

    max_upload_bytes = max(0, settings.voice_max_upload_mb) * 1024 * 1024
    if len(audio_bytes) > max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Audio file is too large. Limit is {settings.voice_max_upload_mb} MB.",
        )

    content_type = _normalize_content_type(audio_file.content_type)
    extension = _audio_extension_from_filename(audio_file.filename)
    if (
        content_type not in ALLOWED_AUDIO_CONTENT_TYPES
        and extension not in AUDIO_EXTENSION_TO_CONTENT_TYPE
    ):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported audio type. Upload webm, wav, mp3, mp4, m4a, or ogg.",
        )

    safe_content_type = content_type
    if not safe_content_type:
        safe_content_type = AUDIO_EXTENSION_TO_CONTENT_TYPE.get(
            extension, "application/octet-stream"
        )

    try:
        text, resolved_language = await transcribe_audio_with_groq(
            api_key=settings.groq_api_key,
            model=settings.groq_whisper_model,
            audio_bytes=audio_bytes,
            filename=audio_file.filename or "voice-note.webm",
            content_type=safe_content_type,
            language=language,
        )
    except GroqTranscriptionConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except GroqTranscriptionUpstreamError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return ExpenseAudioTranscriptionResponse(text=text, language=resolved_language)


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
            warnings=[],
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

    category_lookup, subcategory_lookup = await _load_taxonomy_lookup(session, user.household_id)
    if "other" not in category_lookup:
        category_lookup["other"] = "Other"

    now = datetime.now(UTC).replace(tzinfo=None)
    normalization_warnings: list[str] = []
    for expense in draft_expenses:
        update = expense_updates[expense.id]

        if update.amount is not None:
            expense.amount = update.amount
        if update.currency is not None and update.currency.strip():
            expense.currency = update.currency.strip().upper()
        if update.category is not None:
            expense.category = update.category.strip() or None
        if update.subcategory is not None:
            expense.subcategory = update.subcategory.strip() or None
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

        resolved_category, resolved_subcategory, warnings = _normalize_taxonomy_selection(
            category=expense.category,
            subcategory=expense.subcategory,
            category_lookup=category_lookup,
            subcategory_lookup=subcategory_lookup,
        )
        expense.category = resolved_category
        expense.subcategory = resolved_subcategory
        normalization_warnings.extend(warnings)

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
        warnings=normalization_warnings,
    )


@router.post(
    "/recurring",
    response_model=RecurringExpenseCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_recurring_expense(
    payload: RecurringExpenseCreateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RecurringExpenseCreateResponse:
    cleaned_currency = payload.currency.strip().upper()
    if not cleaned_currency:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Currency is required.",
        )

    category_lookup, subcategory_lookup = await _load_taxonomy_lookup(session, user.household_id)
    if "other" not in category_lookup:
        category_lookup["other"] = "Other"

    resolved_category, resolved_subcategory, warnings = _normalize_taxonomy_selection(
        category=payload.category,
        subcategory=payload.subcategory,
        category_lookup=category_lookup,
        subcategory_lookup=subcategory_lookup,
    )

    now = datetime.now(UTC).replace(tzinfo=None)
    expense = Expense(
        household_id=user.household_id,
        logged_by_user_id=user.id,
        amount=payload.amount,
        currency=cleaned_currency,
        category=resolved_category,
        subcategory=resolved_subcategory,
        description=_clean_optional_text(payload.description),
        merchant_or_item=_clean_optional_text(payload.merchant_or_item),
        date_incurred=_parse_date_incurred(payload.date_incurred, datetime.now(UTC).date()),
        is_recurring=True,
        confidence=1.0,
        status=ExpenseStatus.CONFIRMED,
        source_text="manual recurring expense",
        updated_at=now,
    )
    session.add(expense)
    await session.commit()
    await session.refresh(expense)

    return RecurringExpenseCreateResponse(
        item=_to_expense_feed_item(expense, user.full_name),
        message="Recurring expense added successfully.",
        warnings=warnings,
    )


@router.get("/list", response_model=ExpenseFeedResponse)
async def list_expenses(
    status_filter: Literal["confirmed", "draft", "all"] = Query(
        default="confirmed",
        alias="status",
    ),
    recurring_only: bool = Query(default=False, alias="recurring_only"),
    limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ExpenseFeedResponse:
    filters = _build_expense_filters(
        user.household_id,
        status_filter,
        recurring_only=recurring_only,
    )

    list_result = await session.execute(
        select(Expense)
        .where(*filters)
        .order_by(Expense.date_incurred.desc(), Expense.created_at.desc())
        .limit(limit)
    )
    expenses = list_result.scalars().all()

    user_ids = {expense.logged_by_user_id for expense in expenses}
    user_names = await _resolve_user_names(session, user_ids)

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


@router.get("/export.csv")
async def export_expenses_csv(
    status_filter: Literal["confirmed", "draft", "all"] = Query(
        default="confirmed",
        alias="status",
    ),
    recurring_only: bool = Query(default=False, alias="recurring_only"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    filters = _build_expense_filters(
        user.household_id,
        status_filter,
        recurring_only=recurring_only,
    )
    list_result = await session.execute(
        select(Expense)
        .where(*filters)
        .order_by(Expense.date_incurred.desc(), Expense.created_at.desc())
    )
    expenses = list_result.scalars().all()
    user_names = await _resolve_user_names(
        session,
        {expense.logged_by_user_id for expense in expenses},
    )

    csv_buffer = io.StringIO(newline="")
    writer = csv.writer(csv_buffer)
    writer.writerow(
        [
            "expense_id",
            "date_incurred",
            "logged_by",
            "status",
            "category",
            "subcategory",
            "description",
            "merchant_or_item",
            "amount",
            "currency",
            "is_recurring",
            "confidence",
            "created_at",
            "updated_at",
        ]
    )

    for expense in expenses:
        writer.writerow(
            [
                str(expense.id),
                str(expense.date_incurred),
                user_names.get(expense.logged_by_user_id, "Unknown"),
                expense.status.value,
                expense.category or "",
                expense.subcategory or "",
                expense.description or "",
                expense.merchant_or_item or "",
                "" if expense.amount is None else f"{float(expense.amount):.2f}",
                expense.currency,
                "true" if expense.is_recurring else "false",
                f"{float(expense.confidence):.2f}",
                expense.created_at.isoformat(),
                expense.updated_at.isoformat(),
            ]
        )

    recurring_suffix = "_recurring" if recurring_only else ""
    filename = f"expenses_{status_filter}{recurring_suffix}_{datetime.now(UTC).date().isoformat()}.csv"
    return Response(
        content=csv_buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch("/{expense_id}/recurring", response_model=ExpenseRecurringUpdateResponse)
async def update_expense_recurring(
    expense_id: str,
    payload: ExpenseRecurringUpdateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ExpenseRecurringUpdateResponse:
    try:
        expense_uuid = UUID(expense_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid expense_id",
        ) from exc

    expense_result = await session.execute(
        select(Expense).where(
            Expense.id == expense_uuid,
            Expense.household_id == user.household_id,
        )
    )
    expense = expense_result.scalar_one_or_none()
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found in your household.",
        )

    if expense.logged_by_user_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update recurring flag for expenses you logged.",
        )

    expense.is_recurring = payload.is_recurring
    expense.updated_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(expense)
    await session.commit()
    await session.refresh(expense)

    user_names = await _resolve_user_names(session, {expense.logged_by_user_id})
    message = (
        "Expense marked as recurring."
        if payload.is_recurring
        else "Expense removed from recurring."
    )
    return ExpenseRecurringUpdateResponse(
        item=_to_expense_feed_item(
            expense,
            user_names.get(expense.logged_by_user_id, "Unknown"),
        ),
        message=message,
    )


@router.delete("/{expense_id}", response_model=ExpenseDeleteResponse)
async def delete_expense(
    expense_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ExpenseDeleteResponse:
    try:
        expense_uuid = UUID(expense_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid expense_id",
        ) from exc

    expense_result = await session.execute(
        select(Expense).where(
            Expense.id == expense_uuid,
            Expense.household_id == user.household_id,
        )
    )
    expense = expense_result.scalar_one_or_none()
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found in your household.",
        )

    if expense.logged_by_user_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete expenses you logged.",
        )

    await session.delete(expense)
    await session.commit()

    return ExpenseDeleteResponse(
        expense_id=str(expense.id),
        message="Expense deleted successfully.",
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
