from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import get_settings
from app.core.crypto import decrypt_secret, encrypt_secret
from app.models.llm_setting import LLMProvider, LLMSetting

settings = get_settings()


class LLMRuntimeConfig:
    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        default_currency: str,
        timezone: str,
        api_key: str | None,
    ):
        self.provider = provider
        self.model = model
        self.default_currency = default_currency
        self.timezone = timezone
        self.api_key = api_key


def _provider_from_env() -> LLMProvider:
    try:
        return LLMProvider(settings.llm_provider.lower().strip())
    except ValueError:
        return LLMProvider.MOCK


def _default_model_for(provider: LLMProvider) -> str:
    if provider == LLMProvider.OPENAI:
        return settings.openai_model
    if provider == LLMProvider.GEMINI:
        return settings.gemini_model
    if provider == LLMProvider.CEREBRAS:
        return settings.cerebras_model
    return settings.llm_model


def _default_api_key_for(provider: LLMProvider) -> str | None:
    if provider == LLMProvider.OPENAI:
        return settings.openai_api_key
    if provider == LLMProvider.GEMINI:
        return settings.gemini_api_key
    if provider == LLMProvider.CEREBRAS:
        return settings.cerebras_api_key
    return None


def get_env_runtime_config() -> LLMRuntimeConfig:
    provider = _provider_from_env()
    model = _default_model_for(provider).strip() or settings.llm_model
    api_key = _default_api_key_for(provider)
    default_currency = settings.llm_default_currency.strip().upper() or "INR"
    timezone = settings.llm_timezone.strip() or "UTC"
    return LLMRuntimeConfig(
        provider=provider,
        model=model,
        default_currency=default_currency,
        timezone=timezone,
        api_key=api_key.strip() if api_key else None,
    )


async def get_or_create_household_llm_setting(
    session: AsyncSession,
    household_id: UUID,
) -> LLMSetting:
    result = await session.execute(
        select(LLMSetting).where(LLMSetting.household_id == household_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    provider = _provider_from_env()
    setting = LLMSetting(
        household_id=household_id,
        provider=provider,
        model=_default_model_for(provider),
        default_currency=settings.llm_default_currency,
        timezone=settings.llm_timezone,
        api_key_encrypted=(
            encrypt_secret(_default_api_key_for(provider))
            if _default_api_key_for(provider)
            else None
        ),
    )
    session.add(setting)
    await session.commit()
    await session.refresh(setting)
    return setting


def to_runtime_config(setting: LLMSetting) -> LLMRuntimeConfig:
    api_key = (
        decrypt_secret(setting.api_key_encrypted) if setting.api_key_encrypted else None
    )
    return LLMRuntimeConfig(
        provider=setting.provider,
        model=setting.model,
        default_currency=setting.default_currency,
        timezone=setting.timezone,
        api_key=api_key,
    )


async def update_household_llm_setting(
    session: AsyncSession,
    household_id: UUID,
    provider: LLMProvider,
    model: str,
    default_currency: str,
    timezone: str,
    api_key: str | None,
) -> LLMSetting:
    setting = await get_or_create_household_llm_setting(session, household_id)
    setting.provider = provider
    setting.model = model.strip()
    setting.default_currency = default_currency.strip().upper()
    setting.timezone = timezone.strip()
    if api_key is not None and api_key.strip():
        setting.api_key_encrypted = encrypt_secret(api_key.strip())
    setting.updated_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(setting)
    await session.commit()
    await session.refresh(setting)
    return setting
