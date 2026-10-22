from pathlib import Path
from pydantic import Field, field_validator
from zoneinfo import ZoneInfo
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Aevum Core configuration settings."""

    app_name: str = "Aevum Core"
    version: str = "0.1.0"
    environment: str = Field(default="development", alias="AEVUM_ENV")
    host: str = Field(default="127.0.0.1", alias="AEVUM_HOST")
    port: int = Field(default=8000, alias="AEVUM_PORT")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./aevum.db",
        alias="AEVUM_DATABASE_URL",
    )
    llm_provider: str = Field(
        default="gemini",
        alias="AEVUM_LLM_PROVIDER",
    )
    gemini_api_key: str | None = Field(
        default=None,
        alias="GEMINI_API_KEY",
    )
    gemini_model: str = Field(
        default="gemini-3.8-flash",
        alias="GEMINI_MODEL",
    )
    memory_auto_curation_enabled: bool = Field(
        default=False,
        alias="AEVUM_MEMORY_AUTO_CURATION_ENABLED",
    )
    embedding_provider: str = Field(
        default="gemini",
        alias="AEVUM_EMBEDDING_PROVIDER",
    )
    embedding_model: str = Field(
        default="text-embedding-004",
        alias="AEVUM_EMBEDDING_MODEL",
    )

    aevum_timezone: str = Field(
        default="Asia/Kuala_Lumpur",
        alias="AEVUM_TIMEZONE",
    )

    telegram_bot_token: str | None = Field(
        default=None,
        alias="TELEGRAM_BOT_TOKEN",
    )
    telegram_allowed_user_ids: str = Field(
        default="",
        alias="TELEGRAM_ALLOWED_USER_IDS",
    )
    telegram_enabled: bool = Field(
        default=False,
        alias="TELEGRAM_ENABLED",
    )

    @field_validator("aevum_timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except Exception:
            raise ValueError(f"Invalid timezone: {v}")
        return v

    model_config = SettingsConfigDict(
        env_file=(_PROJECT_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
