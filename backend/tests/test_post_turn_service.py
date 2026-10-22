import json
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.character.post_turn_service import (
    PostTurnExtractionPayload,
    PostTurnService,
)
from app.db.models import Conversation, Message, MessageRole
from app.llm import ChatMessage, LLMContext, LLMResponse
from app.memory.models import MemoryCategory, MemorySubjectEntity
from app.relationship.models import RelationshipSignalType
from app.relationship.service import RelationshipService
from tests.conftest import FakeLLMProvider


@pytest.mark.asyncio
async def test_extract_signals_and_memories_merged_success():
    """Verify single merged extraction produces both relationship signals and memory proposals."""
    fake_payload = {
        "relationship_signals": [
            {
                "signal_type": "PLAYFUL_CONNECTION",
                "confidence": 0.85,
                "strength": 0.35,
                "reason": "互相打趣逗乐",
            }
        ],
        "memory_proposals": [
            {
                "category": "USER_GOAL",
                "subject_entity": "USER",
                "content": "用户今天下午要去琴房练琴",
                "importance": 0.80,
                "confidence": 0.95,
                "emotional_weight": 0.2,
            }
        ],
    }
    provider = FakeLLMProvider(structured_response_text=json.dumps(fake_payload))

    messages = [
        ChatMessage(role="user", content="下午打算去琴房练会儿琴"),
        ChatMessage(role="assistant", content="加油\n别又偷懒"),
    ]

    result = await PostTurnService.extract_signals_and_memories(
        messages=messages,
        llm_provider=provider,
    )

    assert len(result.relationship_signals) == 1
    assert result.relationship_signals[0].signal_type == RelationshipSignalType.PLAYFUL_CONNECTION
    assert len(result.memory_proposals) == 1
    assert result.memory_proposals[0].category == MemoryCategory.USER_GOAL
    assert "琴房" in result.memory_proposals[0].content


@pytest.mark.asyncio
async def test_extract_signals_and_memories_failure_isolation():
    """Verify provider error does not crash and returns empty payload."""
    class FailingProvider(FakeLLMProvider):
        async def generate_structured_response(self, context, response_schema=None):
            raise RuntimeError("API timeout")

    provider = FailingProvider()
    messages = [ChatMessage(role="user", content="hi")]

    result = await PostTurnService.extract_signals_and_memories(
        messages=messages,
        llm_provider=provider,
    )
    assert len(result.relationship_signals) == 0
    assert len(result.memory_proposals) == 0


@pytest.mark.asyncio
async def test_apply_post_turn_results(test_session: AsyncSession):
    """Verify applying extraction results mutates relationship and memory candidate in session."""
    conv = Conversation(character_id="aevum")
    test_session.add(conv)
    await test_session.commit()
    await test_session.refresh(conv)

    payload_json = {
        "relationship_signals": [
            {
                "signal_type": "APPRECIATION",
                "confidence": 0.9,
                "strength": 0.4,
                "reason": "用户表达由衷感谢",
            }
        ],
        "memory_proposals": [
            {
                "category": "FACT",
                "subject_entity": "USER",
                "content": "用户平时喜欢喝少糖冰美禄",
                "importance": 0.75,
                "confidence": 0.95,
                "emotional_weight": 0.1,
            }
        ],
    }
    payload = PostTurnExtractionPayload.model_validate(payload_json)

    await PostTurnService.apply_post_turn_results(
        session=test_session,
        conversation_id=conv.id,
        target_char_id="aevum",
        rel_id="user",
        user_text="今天真的太谢谢你了",
        assistant_text="客气啥 顺手的事",
        payload=payload,
    )

    # Check relationship updated
    rel_service = RelationshipService(test_session)
    rel = await rel_service.get_relationship_state("user")
    assert rel is not None
    assert rel.version >= 2
    assert rel.trust > 0.1


@pytest.mark.asyncio
async def test_update_rolling_summary_threshold(test_session: AsyncSession):
    """Verify rolling summary generates when messages exceed threshold (30 messages)."""
    conv = Conversation(character_id="aevum", summary=None)
    test_session.add(conv)
    await test_session.commit()
    await test_session.refresh(conv)

    # Add 32 messages
    for i in range(32):
        role = MessageRole.USER.value if i % 2 == 0 else MessageRole.ASSISTANT.value
        msg = Message(
            conversation_id=conv.id,
            role=role,
            content=f"Test message line {i} about music and university",
        )
        test_session.add(msg)
    await test_session.commit()

    provider = FakeLLMProvider(response_text="双方讨论了大学生活与音乐练习。")

    await PostTurnService.update_rolling_summary_if_needed(
        session=test_session,
        conversation_id=conv.id,
        llm_provider=provider,
    )

    # Re-query conversation
    updated_conv = await test_session.scalar(select(Conversation).where(Conversation.id == conv.id))
    assert updated_conv.summary == "双方讨论了大学生活与音乐练习。"
