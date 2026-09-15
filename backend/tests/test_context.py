import pytest

from app.llm.base import ChatMessage
from app.llm.context import LLMContext
from app.llm.context_builder import build_context
from app.llm.gemini import GeminiProvider
from tests.conftest import FakeLLMProvider


def test_empty_message_list_creates_valid_context():
    """Verify empty message list produces a valid LLMContext without errors."""
    context = build_context(messages=[])
    assert isinstance(context, LLMContext)
    assert context.messages == []
    assert context.system_instructions == []


def test_messages_preserve_order_and_roles_and_content():
    """Verify build_context preserves message ordering, roles, and content."""
    input_messages = [
        ChatMessage(role="user", content="Hello"),
        ChatMessage(role="assistant", content="Hi!"),
        ChatMessage(role="system", content="System premise"),
        ChatMessage(role="user", content="How are you?"),
    ]

    context = build_context(messages=input_messages)

    assert len(context.messages) == 4
    assert [m.role for m in context.messages] == ["user", "assistant", "system", "user"]
    assert [m.content for m in context.messages] == [
        "Hello",
        "Hi!",
        "System premise",
        "How are you?",
    ]


def test_input_list_is_not_mutated():
    """Verify build_context creates independent copies and does not mutate caller's list."""
    original = [
        ChatMessage(role="user", content="Initial"),
    ]
    context = build_context(messages=original)

    # Mutate context and verify original is unaffected
    context.messages.append(ChatMessage(role="assistant", content="Appended"))
    assert len(original) == 1
    assert original[0].content == "Initial"


def test_no_default_personality_or_system_prompt_is_injected():
    """Verify that build_context contains NO hardcoded personality, persona, or default system prompts."""
    context = build_context(messages=[ChatMessage(role="user", content="Test")])
    assert context.system_instructions == []
    assert len(context.messages) == 1
    assert "Aevum" not in context.system_instructions
    assert "girlfriend" not in context.system_instructions


def test_system_instructions_none_produces_empty_list():
    """Verify passing system_instructions=None produces an empty system_instructions list."""
    context = build_context(messages=[], system_instructions=None)
    assert context.system_instructions == []


def test_explicit_system_instructions_preserve_order_and_remain_separate():
    """Verify explicit system instructions preserve order and stay separate from conversation messages."""
    instructions = ["Instruction Alpha", "Instruction Beta"]
    messages = [ChatMessage(role="user", content="User text")]

    context = build_context(messages=messages, system_instructions=instructions)

    assert context.system_instructions == ["Instruction Alpha", "Instruction Beta"]
    assert len(context.messages) == 1
    assert context.messages[0].role == "user"
    assert context.messages[0].content == "User text"


@pytest.mark.asyncio
async def test_llm_context_can_be_passed_to_fake_provider():
    """Verify that FakeLLMProvider accepts LLMContext and registers it in call_history."""
    provider = FakeLLMProvider(response_text="Fake response")
    context = build_context(
        messages=[ChatMessage(role="user", content="Hello")],
        system_instructions=["Be concise"],
    )

    response = await provider.generate_response(context=context)
    assert response.content == "Fake response"
    assert len(provider.call_history) == 1
    assert provider.call_history[0] == context


def test_gemini_context_conversion():
    """Verify GeminiProvider converts LLMContext into Gemini Content objects and system instructions."""
    provider = GeminiProvider(api_key="mock-key")
    context = build_context(
        messages=[
            ChatMessage(role="user", content="User prompt"),
            ChatMessage(role="assistant", content="Model reply"),
            ChatMessage(role="system", content="Conversation system message"),
        ],
        system_instructions=["Context instruction 1", "Context instruction 2"],
    )

    contents, system_instruction = provider._convert_context_to_gemini(context=context)

    # Check contents: user and assistant (model)
    assert len(contents) == 2
    assert contents[0].role == "user"
    assert contents[0].parts[0].text == "User prompt"
    assert contents[1].role == "model"
    assert contents[1].parts[0].text == "Model reply"

    # Check system instructions: context system_instructions + conversation system message combined
    expected_system = "Context instruction 1\n\nContext instruction 2\n\nConversation system message"
    assert system_instruction == expected_system
