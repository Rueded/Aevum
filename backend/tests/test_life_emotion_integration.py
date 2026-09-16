import pytest
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.life.models import LifeEvent, LifeEventType
from app.life.emotion_integrator import LifeEmotionIntegrator
from app.emotion.emotion_models import EmotionType
from app.emotion.service import EmotionService
from app.emotion.event_service import EmotionEventService
from app.emotion.influence_service import EmotionInfluenceService
from app.db.models import EmotionEventRecord, EmotionInfluenceRecord

@pytest.mark.asyncio
async def test_meaningful_positive_event(test_session: AsyncSession):
    emo_service = EmotionService(test_session)
    await emo_service.get_emotion_state("aevum")
    
    integrator = LifeEmotionIntegrator(test_session)
    
    # Meaningful completion
    event = LifeEvent(
        id="life-event-1",
        character_id="aevum",
        event_type=LifeEventType.ACTIVITY_COMPLETED,
        title="Completed highly anticipated reading",
        description="Reading",
        significance=0.8,
        occurred_at=datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc),
    )
    
    await integrator.process_life_event(event)
    
    stmt = select(EmotionEventRecord).where(EmotionEventRecord.source_life_event_id == "life-event-1")
    emotion_event = (await test_session.scalars(stmt)).first()
    assert emotion_event is not None
    from app.emotion.service import _ensure_utc
    assert _ensure_utc(emotion_event.created_at) == event.occurred_at
    
    stmt_inf = select(EmotionInfluenceRecord).where(EmotionInfluenceRecord.event_id == emotion_event.id)
    influence = (await test_session.scalars(stmt_inf)).first()
    assert influence is not None
    assert influence.target_emotion == EmotionType.CONTENT.value
    
    current_state = await emo_service.get_emotion_state("aevum")
    assert current_state.emotion_type == EmotionType.CONTENT

@pytest.mark.asyncio
async def test_neutral_event(test_session: AsyncSession):
    emo_service = EmotionService(test_session)
    await emo_service.get_emotion_state("aevum")

    integrator = LifeEmotionIntegrator(test_session)
    
    event = LifeEvent(
        id="life-event-2",
        character_id="aevum",
        event_type=LifeEventType.ACTIVITY_COMPLETED,
        title="Finished resting",
        description="Routine rest",
        significance=0.2, # < 0.5 makes it neutral for completion
        occurred_at=datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc),
    )
    
    await integrator.process_life_event(event)
    
    stmt = select(EmotionEventRecord).where(EmotionEventRecord.source_life_event_id == "life-event-2")
    emotion_event = (await test_session.scalars(stmt)).first()
    assert emotion_event is None # Should not even create an emotion event

@pytest.mark.asyncio
async def test_negative_event(test_session: AsyncSession):
    emo_service = EmotionService(test_session)
    await emo_service.get_emotion_state("aevum")

    integrator = LifeEmotionIntegrator(test_session)
    
    event = LifeEvent(
        id="life-event-3",
        character_id="aevum",
        event_type=LifeEventType.PLAN_CANCELLED,
        title="Missed important study session",
        description="Cancelled",
        significance=0.8,
        occurred_at=datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc),
    )
    
    await integrator.process_life_event(event)
    
    current_state = await emo_service.get_emotion_state("aevum")
    assert current_state.emotion_type == EmotionType.DISAPPOINTED

@pytest.mark.asyncio
async def test_idempotency(test_session: AsyncSession):
    emo_service = EmotionService(test_session)
    await emo_service.get_emotion_state("aevum")

    integrator = LifeEmotionIntegrator(test_session)
    
    event = LifeEvent(
        id="life-event-4",
        character_id="aevum",
        event_type=LifeEventType.SUCCESS,
        title="Personal success",
        description="Yay",
        significance=0.9,
        occurred_at=datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc),
    )
    
    await integrator.process_life_event(event)
    await integrator.process_life_event(event)
    await integrator.process_life_event(event)
    
    stmt = select(EmotionEventRecord).where(EmotionEventRecord.source_life_event_id == "life-event-4")
    events = (await test_session.scalars(stmt)).all()
    assert len(events) == 1
    
    stmt_inf = select(EmotionInfluenceRecord).where(EmotionInfluenceRecord.event_id == events[0].id)
    influences = (await test_session.scalars(stmt_inf)).all()
    assert len(influences) == 1
