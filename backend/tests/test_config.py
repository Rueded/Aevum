"""Focused tests for Aevum Core configuration and environment discovery."""

from pathlib import Path
import pytest
from pydantic_settings import SettingsConfigDict

from app.core.config import Settings, _PROJECT_ROOT, settings


def test_project_root_discovery() -> None:
    """Verify that _PROJECT_ROOT correctly resolves to the repository root containing .env.example."""
    assert _PROJECT_ROOT.is_dir()
    assert (_PROJECT_ROOT / ".env.example").is_file()
    assert (_PROJECT_ROOT / "backend").is_dir()
    assert (_PROJECT_ROOT / "apps").is_dir()


def test_project_root_env_loaded_into_settings() -> None:
    """Verify that Settings loads GEMINI_API_KEY from the project-root .env when present."""
    assert hasattr(settings, "gemini_api_key")
    root_env = _PROJECT_ROOT / ".env"
    if root_env.is_file():
        assert settings.gemini_api_key is not None
        assert isinstance(settings.gemini_api_key, str)
        assert len(settings.gemini_api_key) > 0


def test_os_environment_variable_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that OS environment variables take precedence over .env file configuration."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-override-key-12345")
    monkeypatch.setenv("AEVUM_PORT", "9999")
    monkeypatch.setenv("GEMINI_MODEL", "test-custom-model")

    custom_settings = Settings()
    assert custom_settings.gemini_api_key == "test-override-key-12345"
    assert custom_settings.port == 9999
    assert custom_settings.gemini_model == "test-custom-model"


def test_settings_isolated_hermetic_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that Settings behaves hermetically with custom or empty env files."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    fake_env = tmp_path / ".env"
    fake_env.write_text("GEMINI_API_KEY=mocked-hermetic-key\nAEVUM_PORT=8088\n", encoding="utf-8")

    class IsolatedSettings(Settings):
        model_config = SettingsConfigDict(
            env_file=fake_env,
            env_file_encoding="utf-8",
            extra="ignore",
        )

    s = IsolatedSettings()
    assert s.gemini_api_key == "mocked-hermetic-key"
    assert s.port == 8088
