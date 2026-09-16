from unittest.mock import AsyncMock, MagicMock
import pytest

from app.llm.base import (
    ChatMessage,
    LLMGenerationError,
    LLMPromptContext,
    LLMProvider,
    LLMProviderNotConfiguredError,
    LLMResponse,
)
from app.llm.context import LLMContext
from app.llm.context_builder import build_context
from app.llm.gemini import GeminiProvider


def test_chat_message_model():
    """Verify ChatMessage schema validation."""
    msg = ChatMessage(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_llm_prompt_context_model():
    """Verify LLMPromptContext schema validation."""
    ctx = LLMPromptContext(
        system_instruction="Ground truth instruction.",
        user_message="Hello",
        grounded_state={"mood": "calm"},
    )
    assert ctx.system_instruction == "Ground truth instruction."
    assert ctx.user_message == "Hello"
    assert ctx.grounded_state["mood"] == "calm"


def test_llm_response_model():
    """Verify LLMResponse schema validation."""
    resp = LLMResponse(content="Hello there.")
    assert resp.content == "Hello there."
    assert resp.raw_response is None


def test_llm_provider_cannot_be_instantiated_directly():
    """Verify that the abstract LLMProvider cannot be instantiated without implementation."""
    with pytest.raises(TypeError):
        LLMProvider()  # type: ignore[abstract]


@pytest.mark.asyncio
async def test_gemini_provider_missing_api_key_raises_error(monkeypatch):
    """Verify GeminiProvider raises LLMProviderNotConfiguredError when initialized without API key."""
    monkeypatch.setattr("app.llm.gemini.settings.gemini_api_key", None)
    provider = GeminiProvider(api_key=None, client=None)
    context = build_context(messages=[ChatMessage(role="user", content="Hi")])
    with pytest.raises(LLMProviderNotConfiguredError) as exc_info:
        await provider.generate_response(context=context)
    assert "Gemini API key is not configured" in str(exc_info.value)


@pytest.mark.asyncio
async def test_gemini_provider_empty_messages_raises_error():
    """Verify GeminiProvider raises LLMGenerationError when given an empty message history."""
    mock_client = MagicMock()
    provider = GeminiProvider(api_key="test-key", client=mock_client)
    context = build_context(messages=[])
    with pytest.raises(LLMGenerationError) as exc_info:
        await provider.generate_response(context=context)
    assert "empty message history" in str(exc_info.value)


def test_gemini_provider_role_conversion():
    """Verify neutral roles are correctly converted into Gemini types."""
    provider = GeminiProvider(api_key="dummy-key")
    context = build_context(
        messages=[
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi there!"),
            ChatMessage(role="system", content="System premise"),
        ],
        system_instructions=["Additional sys info"],
    )
    contents, system_inst = provider._convert_context_to_gemini(context=context)

    assert len(contents) == 2
    assert contents[0].role == "user"
    assert contents[0].parts[0].text == "Hello"
    assert contents[1].role == "model"
    assert contents[1].parts[0].text == "Hi there!"
    assert system_inst == "Additional sys info\n\nSystem premise"


@pytest.mark.asyncio
async def test_gemini_provider_generates_response_with_mock():
    """Verify GeminiProvider generates response and extracts content using mocked client."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Hello! I am a simulated Gemini response."

    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    provider = GeminiProvider(api_key="mock-key", client=mock_client)
    context = build_context(messages=[ChatMessage(role="user", content="Hello")])
    result = await provider.generate_response(context=context)

    assert result.content == "Hello! I am a simulated Gemini response."
    mock_client.aio.models.generate_content.assert_awaited_once()


@pytest.mark.asyncio
async def test_gemini_provider_empty_response_raises_error():
    """Verify GeminiProvider treats an empty/blank response as LLMGenerationError."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "   "

    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    provider = GeminiProvider(api_key="mock-key", client=mock_client)
    context = build_context(messages=[ChatMessage(role="user", content="Hello")])
    with pytest.raises(LLMGenerationError) as exc_info:
        await provider.generate_response(context=context)
    assert "empty or blank response" in str(exc_info.value)


@pytest.mark.asyncio
async def test_gemini_provider_upstream_error_sanitizes_credentials():
    """Verify upstream SDK errors are caught and sanitized without exposing API key."""
    mock_client = MagicMock()
    secret_key = "sk-super-secret-key-12345"
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=Exception(f"Network failed with key {secret_key}")
    )

    provider = GeminiProvider(api_key=secret_key, client=mock_client)
    context = build_context(messages=[ChatMessage(role="user", content="Hello")])
    with pytest.raises(LLMGenerationError) as exc_info:
        await provider.generate_response(context=context)

    err_text = str(exc_info.value)
    assert secret_key not in err_text
    assert "[REDACTED]" in err_text
