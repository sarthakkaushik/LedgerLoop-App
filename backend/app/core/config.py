from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Expense Tracker API"
    app_env: str = "dev"
    secret_key: str = "change-me"
    app_encryption_key: str | None = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    database_url: str = "sqlite+aiosqlite:///./expense_tracker.db"
    cors_allow_origins: str = "http://localhost:5173"
    llm_provider: str = "mock"
    llm_model: str = "mock-expense-parser-v1"
    llm_default_currency: str = "INR"
    llm_timezone: str = "Asia/Kolkata"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    cerebras_api_key: str | None = None
    cerebras_model: str = "gpt-oss-120b"
    groq_api_key: str | None = None
    groq_model: str = "moonshotai/kimi-k2-instruct-0905"
    groq_whisper_model: str = "whisper-large-v3-turbo"
    voice_max_upload_mb: int = 10
    clerk_enabled: bool = False
    clerk_issuer: str | None = None
    clerk_jwks_url: str | None = None
    clerk_authorized_parties: str = ""
    clerk_jwt_audience: str | None = None
    clerk_jwks_cache_ttl_seconds: int = 300

    @property
    def cors_origins(self) -> list[str]:
        return [x.strip() for x in self.cors_allow_origins.split(",") if x.strip()]

    @property
    def clerk_authorized_party_list(self) -> list[str]:
        return [x.strip() for x in self.clerk_authorized_parties.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
