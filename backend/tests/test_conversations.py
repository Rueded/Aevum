import pytest
from httpx import AsyncClient

from app.llm import (
    ChatMessage,
    LLMGenerationError,
    LLMProvider,
    LLMProviderNotConfiguredError,
    LLMResponse,
    get_llm_provider,
)
from app.main import app
from tests.conftest import FakeLLMProvider


@pytest.mark.asyncio
async def test_create_conversation(client: AsyncClient):
    """Verify creating a conversation returns 201 with valid id and timestamps."""
    response = await client.post("/conversations")
    assert response.status_code == 201

    data = response.json()
    assert "id" in data
    assert len(data["id"]) > 0
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_add_user_message_generates_and_persists_assistant_response(
    client: AsyncClient,
    fake_provider: FakeLLMProvider,
):
    """Verify adding a user message invokes the LLM provider and persists both messages."""
    fake_provider.response_text = "I am a persisted assistant response."

    conv_res = await client.post("/conversations")
    conv_id = conv_res.json()["id"]

    msg_payload = {"role": "user", "content": "Hello Aevum!"}
    msg_res = await client.post(f"/conversations/{conv_id}/messages", json=msg_payload)
    assert msg_res.status_code == 201

    data = msg_res.json()
    # Check user message details
    assert "message" in data
    assert data["message"]["conversation_id"] == conv_id
    assert data["message"]["role"] == "user"
    assert data["message"]["content"] == "Hello Aevum!"

    # Check generated assistant message details
    assert "assistant_response" in data
    assert data["assistant_response"] is not None
    assert data["assistant_response"]["role"] == "assistant"
    assert data["assistant_response"]["content"] == "I am a persisted assistant response."
    assert data["assistant_status"] == "generated"

    # Verify both messages are in the database via GET
    get_res = await client.get(f"/conversations/{conv_id}")
    assert get_res.status_code == 200
    messages = get_res.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello Aevum!"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "I am a persisted assistant response."


@pytest.mark.asyncio
async def test_multi_turn_conversation_receives_history(
    client: AsyncClient,
    fake_provider: FakeLLMProvider,
):
    """Verify that multi-turn interactions pass cumulative conversation history to the provider."""
    conv_res = await client.post("/conversations")
    conv_id = conv_res.json()["id"]

    # Turn 1
    fake_provider.response_text = "Answer 1"
    await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "Question 1"},
    )
    assert len(fake_provider.call_history) == 1
    history_turn_1 = fake_provider.call_history[0]
    assert len(history_turn_1.messages) == 1
    assert history_turn_1.messages[0].role == "user"
    assert history_turn_1.messages[0].content == "Question 1"

    # Turn 2
    fake_provider.response_text = "Answer 2"
    await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "Question 2"},
    )
    assert len(fake_provider.call_history) == 2
    history_turn_2 = fake_provider.call_history[1]
    # History for turn 2 must contain: Question 1, Answer 1, Question 2
    assert len(history_turn_2.messages) == 3
    assert [m.content for m in history_turn_2.messages] == ["Question 1", "Answer 1", "Question 2"]
    assert [m.role for m in history_turn_2.messages] == ["user", "assistant", "user"]


    # Verify final database state has all 4 messages in chronological order
    get_res = await client.get(f"/conversations/{conv_id}")
    assert get_res.status_code == 200
    all_msgs = get_res.json()["messages"]
    assert len(all_msgs) == 4
    assert [m["content"] for m in all_msgs] == [
        "Question 1",
        "Answer 1",
        "Question 2",
        "Answer 2",
    ]


@pytest.mark.asyncio
async def test_client_cannot_inject_assistant_or_system_roles(
    client: AsyncClient,
):
    """Verify that clients cannot inject arbitrary 'assistant' or 'system' messages via the public endpoint."""
    conv_res = await client.post("/conversations")
    conv_id = conv_res.json()["id"]

    # Reject client attempting role='assistant'
    res_assistant = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "assistant", "content": "Spoofed assistant message"},
    )
    assert res_assistant.status_code == 422

    # Reject client attempting role='system'
    res_system = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "system", "content": "Spoofed system message"},
    )
    assert res_system.status_code == 422



@pytest.mark.asyncio
async def test_provider_not_configured_returns_503_and_persists_user_message(
    client: AsyncClient,
):
    """Verify missing provider configuration returns 503 while preserving the user message in DB."""
    class UnconfiguredProvider(LLMProvider):
        @property
        def provider_name(self) -> str:
            return "unconfigured"

        async def generate_response(self, context, **kwargs) -> LLMResponse:
            raise LLMProviderNotConfiguredError("Provider is not configured with API key.")

    app.dependency_overrides[get_llm_provider] = lambda: UnconfiguredProvider()

    conv_res = await client.post("/conversations")
    conv_id = conv_res.json()["id"]

    res = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "Will this be saved?"},
    )
    assert res.status_code == 503
    assert "Provider is not configured" in res.json()["detail"]

    # Verify user message was persisted in the database, with no assistant message
    get_res = await client.get(f"/conversations/{conv_id}")
    assert get_res.status_code == 200
    messages = get_res.json()["messages"]
    assert len(messages) == 1
    assert messages[0]["content"] == "Will this be saved?"
    assert messages[0]["role"] == "user"


@pytest.mark.asyncio
async def test_provider_failure_returns_502_and_persists_user_message(
    client: AsyncClient,
):
    """Verify upstream provider failure returns 502 while preserving the user message in DB."""
    class FailingProvider(LLMProvider):
        @property
        def provider_name(self) -> str:
            return "failing"

        async def generate_response(self, context, **kwargs) -> LLMResponse:
            raise LLMGenerationError("Upstream service unavailable.")

    app.dependency_overrides[get_llm_provider] = lambda: FailingProvider()

    conv_res = await client.post("/conversations")
    conv_id = conv_res.json()["id"]

    res = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "Testing upstream failure"},
    )
    assert res.status_code == 502
    assert "Upstream service unavailable" in res.json()["detail"]

    # Verify user message was persisted in the database, with no assistant message
    get_res = await client.get(f"/conversations/{conv_id}")
    assert get_res.status_code == 200
    messages = get_res.json()["messages"]
    assert len(messages) == 1
    assert messages[0]["content"] == "Testing upstream failure"


@pytest.mark.asyncio
async def test_empty_provider_response_returns_502_and_persists_user_message(
    client: AsyncClient,
):
    """Verify that an empty response from the provider returns 502 without saving empty assistant message."""
    class EmptyResponseProvider(LLMProvider):
        @property
        def provider_name(self) -> str:
            return "empty"

        async def generate_response(self, context, **kwargs) -> LLMResponse:
            return LLMResponse(content="   ")


    app.dependency_overrides[get_llm_provider] = lambda: EmptyResponseProvider()

    conv_res = await client.post("/conversations")
    conv_id = conv_res.json()["id"]

    res = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "Trigger empty reply"},
    )
    assert res.status_code == 502
    assert "empty response" in res.json()["detail"]

    # Verify only user message was persisted
    get_res = await client.get(f"/conversations/{conv_id}")
    assert get_res.status_code == 200
    messages = get_res.json()["messages"]
    assert len(messages) == 1
    assert messages[0]["content"] == "Trigger empty reply"


@pytest.mark.asyncio
async def test_reject_empty_or_whitespace_message(client: AsyncClient):
    """Verify that empty or whitespace-only messages are rejected with 422."""
    conv_res = await client.post("/conversations")
    conv_id = conv_res.json()["id"]

    res_empty = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": ""},
    )
    assert res_empty.status_code == 422

    res_ws = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "   \n\t  "},
    )
    assert res_ws.status_code == 422


@pytest.mark.asyncio
async def test_invalid_conversation_id_handling(client: AsyncClient):
    """Verify that non-existent conversation IDs return 404 for both GET and POST."""
    non_existent_id = "00000000-0000-0000-0000-000000000000"

    get_res = await client.get(f"/conversations/{non_existent_id}")
    assert get_res.status_code == 404
    assert f"'{non_existent_id}' not found" in get_res.json()["detail"]

    post_res = await client.post(
        f"/conversations/{non_existent_id}/messages",
        json={"role": "user", "content": "Hello into the void"},
    )
    assert post_res.status_code == 404
    assert f"'{non_existent_id}' not found" in post_res.json()["detail"]


@pytest.mark.asyncio
async def test_client_role_validation(client: AsyncClient):
    """Verify that clients can only submit messages with role='user', rejecting assistant, system, and arbitrary roles."""
    conv_res = await client.post("/conversations")
    conv_id = conv_res.json()["id"]

    # Explicit role='user' succeeds
    res_user = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "Valid user message"},
    )
    assert res_user.status_code == 201

    # Omitted role defaults to 'user' and succeeds
    res_default = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"content": "Default role message"},
    )
    assert res_default.status_code == 201

    # Client attempting role='assistant' must be rejected with 422
    res_assistant = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "assistant", "content": "Spoofed assistant message"},
    )
    assert res_assistant.status_code == 422

    # Client attempting role='system' must be rejected with 422
    res_system = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "system", "content": "Spoofed system message"},
    )
    assert res_system.status_code == 422

    # Arbitrary role must be rejected with 422
    res_admin = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "admin", "content": "Invalid admin role"},
    )
    assert res_admin.status_code == 422


@pytest.mark.asyncio
async def test_database_model_supports_all_internal_roles(test_session):
    """Verify that the database model continues supporting user, assistant, and system roles for Core logic."""
    from app.db.models import Conversation, Message, MessageRole
    from sqlalchemy import select

    conv = Conversation()
    test_session.add(conv)
    await test_session.commit()
    await test_session.refresh(conv)

    # Core/internal logic adds all three roles directly
    for role_enum in [MessageRole.USER, MessageRole.ASSISTANT, MessageRole.SYSTEM]:
        msg = Message(
            conversation_id=conv.id,
            role=role_enum.value,
            content=f"Internal message for {role_enum.value}",
        )
        test_session.add(msg)

    await test_session.commit()

    # Query back from DB
    result = await test_session.execute(
        select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at.asc())
    )
    persisted_roles = [m.role for m in result.scalars().all()]
    assert persisted_roles == ["user", "assistant", "system"]

