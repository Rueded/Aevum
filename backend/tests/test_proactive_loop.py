"""Unit tests for ProactiveLoop & ProactiveThoughtEngine (Phase 5 §8.1 - §8.5)."""

from datetime import datetime, timezone
import json
from typing import Any
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import (
    Base,
    CharacterDefinitionRecord,
    Conversation,
    DesktopUserSettingsRecord,
    Message,
    ProactiveNotificationRecord,
)
from app.llm.base import ChatMessage, LLMProvider, LLMResponse
from app.llm.context import LLMContext
from app.proactive.loop import ProactiveLoop
from app.proactive.thought_engine import ProactiveThoughtEngine, ProactiveThoughtOutput


class MockLLMProvider(LLMProvider):
    """Mock LLM Provider for proactive loop tests."""

    def __init__(self, fixed_output: str):
        self.fixed_output = fixed_output
        self.calls: list[Any] = []

    @property
    def provider_name(self) -> str:
        return "mock"

    async def generate_response(self, context: LLMContext) -> LLMResponse:
        self.calls.append(context)
        return LLMResponse(content=self.fixed_output)

    async def generate_structured_response(self, context: LLMContext, response_schema: Any) -> LLMResponse:
        self.calls.append(context)
        return LLMResponse(content=self.fixed_output)


@pytest.fixture
async def test_session():
    """Create in-memory SQLite async database engine and session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        # Seed character
        char = CharacterDefinitionRecord(
            id="aevum",
            name="苏棠",
            age=19,
            occupation="Student",
            background="A test companion",
        )
        session.add(char)
        await session.commit()
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_proactive_loop_disabled_when_setting_off(test_session: AsyncSession):
    """Verify tick does not reach out when proactive_enabled is False."""
    settings = DesktopUserSettingsRecord(
        character_id="aevum",
        proactive_enabled=False,
    )
    test_session.add(settings)
    await test_session.commit()

    provider = MockLLMProvider("should not be called")
    loop = ProactiveLoop(llm_provider=provider)

    results = await loop.run_tick(session_override=test_session)
    assert len(results) == 1
    assert results[0]["reached_out"] is False
    assert results[0]["reason"] == "proactive_disabled"
    assert len(provider.calls) == 0


@pytest.mark.asyncio
async def test_proactive_loop_gate_suppresses_in_quiet_hours(test_session: AsyncSession):
    """Verify tick is suppressed when current time falls in quiet hours."""
    # Quiet hours 23:00 to 08:00; local time 02:00 UTC = 10:00 Shanghai, but if we set quiet hours to cover 10:00
    settings = DesktopUserSettingsRecord(
        character_id="aevum",
        proactive_enabled=True,
        timezone="Asia/Shanghai",
        quiet_hours_enabled=True,
        quiet_hours_start="09:00",
        quiet_hours_end="18:00",
        max_daily_reach_outs=3,
        min_cooldown_minutes=60,
    )
    test_session.add(settings)
    await test_session.commit()

    test_time = datetime(2026, 10, 22, 4, 0, tzinfo=timezone.utc)  # 12:00 in Asia/Shanghai
    provider = MockLLMProvider("should not be called")
    loop = ProactiveLoop(llm_provider=provider)

    results = await loop.run_tick(current_time=test_time, session_override=test_session)
    assert len(results) == 1
    assert results[0]["reached_out"] is False
    assert "gate_suppressed" in results[0]["reason"]
    assert len(provider.calls) == 0


@pytest.mark.asyncio
async def test_proactive_loop_thought_engine_decides_silence(test_session: AsyncSession):
    """Verify that when gates pass, but Thought Engine decides NO_MESSAGE, no message is created."""
    settings = DesktopUserSettingsRecord(
        character_id="aevum",
        proactive_enabled=True,
        timezone="Asia/Shanghai",
        quiet_hours_enabled=False,
        max_daily_reach_outs=3,
        min_cooldown_minutes=60,
    )
    test_session.add(settings)
    await test_session.commit()

    # Thought engine outputs should_reach_out = False
    thought_json = json.dumps({
        "should_reach_out": False,
        "thought_reason": "忙于看书，无特别分享欲",
        "bubbles": [],
    })
    provider = MockLLMProvider(thought_json)
    loop = ProactiveLoop(llm_provider=provider)

    test_time = datetime(2026, 10, 22, 6, 0, tzinfo=timezone.utc)
    results = await loop.run_tick(current_time=test_time, session_override=test_session)

    assert len(results) == 1
    assert results[0]["reached_out"] is False
    assert "thought_silence" in results[0]["reason"]

    # Verify zero messages or notifications in DB
    msg_count = len((await test_session.scalars(select(Message))).all())
    notif_count = len((await test_session.scalars(select(ProactiveNotificationRecord))).all())
    assert msg_count == 0
    assert notif_count == 0


@pytest.mark.asyncio
async def test_proactive_loop_thought_engine_reaches_out_success(test_session: AsyncSession):
    """Verify that when Thought Engine decides to speak, bubbles and notification are persisted."""
    settings = DesktopUserSettingsRecord(
        character_id="aevum",
        proactive_enabled=True,
        timezone="Asia/Shanghai",
        quiet_hours_enabled=False,
        max_daily_reach_outs=3,
        min_cooldown_minutes=60,
    )
    test_session.add(settings)
    await test_session.commit()

    # Thought engine outputs should_reach_out = True with 2 bubbles
    thought_json = json.dumps({
        "should_reach_out": True,
        "reach_out_type": "SHARE_INCIDENT",
        "thought_reason": "刚下楼遇到好笑的事想吐槽",
        "bubbles": ["刚下楼拿外卖 地板好烫", "迅速逃回空调房瘫着"],
    })
    provider = MockLLMProvider(thought_json)
    loop = ProactiveLoop(llm_provider=provider)

    test_time = datetime(2026, 10, 22, 6, 0, tzinfo=timezone.utc)
    results = await loop.run_tick(current_time=test_time, session_override=test_session)

    assert len(results) == 1
    assert results[0]["reached_out"] is True
    assert len(results[0]["bubbles"]) == 2

    # Verify messages and notifications persisted
    messages = list((await test_session.scalars(select(Message).order_by(Message.created_at.asc()))).all())
    assert len(messages) == 2
    assert messages[0].content == "刚下楼拿外卖 地板好烫"
    assert messages[1].content == "迅速逃回空调房瘫着"

    notifs = list((await test_session.scalars(select(ProactiveNotificationRecord))).all())
    assert len(notifs) == 1
    assert notifs[0].status == "PENDING"
    assert notifs[0].conversation_message_id == messages[0].id
    assert notifs[0].character_id == "aevum"


@pytest.mark.asyncio
async def test_proactive_loop_gate_suppresses_when_busy_with_exam(test_session: AsyncSession):
    """Verify tick is suppressed when character is taking an exam (Brief §8.4)."""
    settings = DesktopUserSettingsRecord(
        character_id="aevum",
        proactive_enabled=True,
        timezone="Asia/Shanghai",
        quiet_hours_enabled=False,
        max_daily_reach_outs=3,
        min_cooldown_minutes=60,
    )
    test_session.add(settings)
    await test_session.commit()

    from app.db.models import LifeStateRecord
    from datetime import timedelta

    test_time = datetime(2026, 10, 22, 6, 0, tzinfo=timezone.utc)

    # Seed life state with exam activity (active contingency)
    life_rec = LifeStateRecord(
        id="aevum",
        character_id="aevum",
        current_activity="大学物理期末考试",
        current_location="教学楼考场",
        status="BUSY",
        active_contingency_id="exam_contingency",
        contingency_expires_at=test_time + timedelta(hours=2),
    )
    test_session.add(life_rec)
    await test_session.commit()

    provider = MockLLMProvider("should not speak")
    loop = ProactiveLoop(llm_provider=provider)

    results = await loop.run_tick(current_time=test_time, session_override=test_session)

    assert len(results) == 1
    assert results[0]["reached_out"] is False
    assert "gate_suppressed:BUSY" in results[0]["reason"]
    assert len(provider.calls) == 0


@pytest.mark.asyncio
async def test_proactive_thought_engine_unreplied_backoff_silence(test_session: AsyncSession):
    """Verify that when 2+ consecutive assistant messages are unreplied, thought engine defaults to silence (Brief §8.4)."""
    import uuid
    conv = Conversation(id=str(uuid.uuid4()), character_id="aevum")
    test_session.add(conv)
    await test_session.flush()

    now = datetime(2026, 10, 22, 6, 0, tzinfo=timezone.utc)
    m1 = Message(id=str(uuid.uuid4()), conversation_id=conv.id, role="assistant", content="今天天气不错", created_at=now)
    m2 = Message(id=str(uuid.uuid4()), conversation_id=conv.id, role="assistant", content="刚看到一只小猫", created_at=now)
    test_session.add_all([m1, m2])
    await test_session.commit()

    provider = MockLLMProvider("should not be called")
    thought = await ProactiveThoughtEngine.evaluate_reach_out(
        session=test_session,
        character_id="aevum",
        llm_provider=provider,
        current_time=now,
    )

    assert thought.should_reach_out is False
    assert len(thought.bubbles) == 0
    assert "对方尚未回复前两条主动消息" in thought.thought_reason
    assert len(provider.calls) == 0
