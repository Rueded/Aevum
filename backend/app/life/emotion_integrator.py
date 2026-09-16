import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.life.models import LifeEvent, LifeEventType
from app.emotion.event_models import EmotionEventCreate, EmotionEventType, EmotionEventSource
from app.emotion.event_service import EmotionEventService
from app.emotion.influence_models import EmotionInfluenceCreate, EmotionInfluenceDirection
from app.emotion.influence_service import EmotionInfluenceService
from app.emotion.emotion_models import EmotionType
from app.emotion.service import EmotionService
from app.emotion.engine import EmotionEngine

logger = logging.getLogger(__name__)

class LifeEmotionIntegrator:
    """Deterministically integrates meaningful LifeEvents into the Emotion domain."""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._event_service = EmotionEventService(session)
        self._influence_service = EmotionInfluenceService(session)
        self._emotion_service = EmotionService(session)
        self._engine = EmotionEngine(session)

    async def process_life_event(self, life_event: LifeEvent) -> None:
        """Process a single LifeEvent and apply any resulting emotional influence.

        Idempotent: Uses source_life_event_id and existing influence duplicate checks.
        """
        # 1. Determine meaningfulness (Rules)
        target_emotion = None
        strength = 0.30
        direction = EmotionInfluenceDirection.POSITIVE
        reason = ""

        if life_event.event_type == LifeEventType.ACTIVITY_COMPLETED and life_event.significance >= 0.5:
            target_emotion = EmotionType.CONTENT
            reason = "A significant planned activity was completed successfully."
        elif life_event.event_type == LifeEventType.PLAN_CANCELLED and life_event.significance >= 0.5:
            target_emotion = EmotionType.DISAPPOINTED
            reason = "A significant planned activity was cancelled."
        elif life_event.event_type == LifeEventType.SUCCESS:
            target_emotion = EmotionType.HAPPY
            reason = "A meaningful personal success was achieved."
        elif life_event.event_type == LifeEventType.SETBACK:
            target_emotion = EmotionType.FRUSTRATED
            reason = "A meaningful setback occurred."

        # If neutral, we do nothing
        if target_emotion is None:
            return

        # 2. Create EmotionEvent
        summary = f"Life event occurred: {life_event.title}."
        
        event_payload = EmotionEventCreate(
            character_id=life_event.character_id,
            event_type=EmotionEventType.LIFE_EVENT,
            summary=summary,
            source=EmotionEventSource.SYSTEM,
            source_life_event_id=life_event.id,
            emotional_relevance=life_event.significance,
            created_at=life_event.occurred_at,
        )

        emotion_event = await self._event_service.create_event(event_payload)
        
        # If it was duplicate, emotion_event might be None
        if emotion_event is None:
            from sqlalchemy import select
            from app.db.models import EmotionEventRecord
            query = select(EmotionEventRecord).where(
                EmotionEventRecord.character_id == life_event.character_id,
                EmotionEventRecord.source_life_event_id == life_event.id,
            )
            result = await self._session.execute(query)
            existing = result.scalars().first()
            if not existing:
                return
            event_id = existing.id
        else:
            event_id = emotion_event.id

        # 3. Create EmotionInfluence
        influence_payload = EmotionInfluenceCreate(
            character_id=life_event.character_id,
            event_id=event_id,
            target_emotion=target_emotion,
            direction=direction,
            strength=strength,
            reason=reason,
        )
        influence = await self._influence_service.create_influence(influence_payload)
        
        # 4. Apply via EmotionEngine if a new influence was actually created
        if influence:
            current_state = await self._emotion_service.get_emotion_state(life_event.character_id)
            if current_state:
                try:
                    await self._engine.process_influences(current_state, [influence])
                except Exception as e:
                    logger.warning("Failed to apply life-based emotion influence: %s", e)
