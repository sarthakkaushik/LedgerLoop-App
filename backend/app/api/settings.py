from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_admin, get_current_user
from app.models.user import User
from app.schemas.settings import (
    LLMSettingsResponse,
    LLMSettingsTestResponse,
    LLMSettingsUpdateRequest,
)
from app.services.llm.provider_factory import (
    ProviderNotConfiguredError,
    get_expense_parser_provider,
)
from app.services.llm.settings_service import (
    get_env_runtime_config,
)
from app.services.llm.types import ParseContext

router = APIRouter(prefix="/settings", tags=["settings"])


def _to_response() -> LLMSettingsResponse:
    runtime = get_env_runtime_config()
    return LLMSettingsResponse(
        provider=runtime.provider,
        model=runtime.model,
        default_currency=runtime.default_currency,
        timezone=runtime.timezone,
        has_api_key=bool(runtime.api_key),
        updated_at=datetime.now(UTC),
    )


@router.get("/llm", response_model=LLMSettingsResponse)
async def get_llm_settings(
    current_user: User = Depends(get_current_user),
) -> LLMSettingsResponse:
    _ = current_user
    return _to_response()


@router.put("/llm", response_model=LLMSettingsResponse)
async def update_llm_settings(
    payload: LLMSettingsUpdateRequest,
    current_user: User = Depends(get_current_admin),
) -> LLMSettingsResponse:
    _ = payload
    _ = current_user
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "LLM settings are managed by server environment variables. "
            "Update backend .env values and restart the API."
        ),
    )


@router.post("/llm/test", response_model=LLMSettingsTestResponse)
async def test_llm_settings(
    current_user: User = Depends(get_current_admin),
) -> LLMSettingsTestResponse:
    _ = current_user
    runtime = get_env_runtime_config()
    context = ParseContext(
        reference_date=datetime.now(UTC).date(),
        timezone=runtime.timezone,
        default_currency=runtime.default_currency,
    )
    try:
        provider = await get_expense_parser_provider()
        result = await provider.parse_expenses(
            "Paid 1 for test transaction",
            context=context,
        )
        return LLMSettingsTestResponse(
            success=True,
            provider=runtime.provider,
            model=runtime.model,
            message=f"Connection is valid. Parsed {len(result.expenses)} expense draft(s).",
        )
    except ProviderNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Provider test failed: {exc}",
        ) from exc
