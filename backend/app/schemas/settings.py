from datetime import datetime

from pydantic import BaseModel, Field

from app.models.llm_setting import LLMProvider


class LLMSettingsResponse(BaseModel):
    provider: LLMProvider
    model: str
    default_currency: str
    timezone: str
    has_api_key: bool
    updated_at: datetime


class LLMSettingsUpdateRequest(BaseModel):
    provider: LLMProvider
    model: str = Field(min_length=2, max_length=120)
    default_currency: str = Field(min_length=3, max_length=8)
    timezone: str = Field(min_length=2, max_length=64)
    api_key: str | None = Field(default=None, min_length=8, max_length=512)


class LLMSettingsTestResponse(BaseModel):
    success: bool
    provider: LLMProvider
    model: str
    message: str
