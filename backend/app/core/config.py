from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
        default="gemini-2.5-flash",
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


    model_config = SettingsConfigDict(

        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
