"""Emotion cause and event service for Aevum Core.

Manages recording, deduplication, retrieval, and querying of historical
emotionally relevant causes and events.
"""

from datetime import datetime, timezone
import logging
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CharacterDefinitionRecord, EmotionEventRecord
from app.emotion.event_models import (
    DEFAULT_CHARACTER_ID,
    EmotionEvent,
    EmotionEventCreate,
    EmotionEventSource,
    EmotionEventType,
)

logger = logging.getLogger(__name__)

MAX_EMOTION_EVENTS_LIST_LIMIT: int = 50
DEFAULT_EMOTION_EVENTS_LIST_LIMIT: int = 20


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime has UTC timezone info attached."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class EmotionEventService:
    """Application-owned service managing persistent EmotionEvent records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_event(
        self,
        payload: EmotionEventCreate,
        commit: bool = True,
    ) -> EmotionEvent | None:
        """Persist an emotion event if it is not an exact duplicate.

        Deterministic duplicate protection:
        Checks whether an event with identical (character_id, event_type, normalized_summary)
        already exists.

        Returns:
            The created EmotionEvent, or None if skipped as duplicate.
        """
        # Ensure character definition exists if character_id matches default Aevum character
        if payload.character_id == DEFAULT_CHARACTER_ID:
            char_stmt = select(CharacterDefinitionRecord).where(
                CharacterDefinitionRecord.id == payload.character_id
            )
            char_record = (await self._session.scalars(char_stmt)).first()
            if char_record is None:
                from app.character.service import CharacterDefinitionService

                await CharacterDefinitionService(self._session).get_character(payload.character_id)

        normalized_summary = payload.summary.strip().lower()

        # Check existing events for identical character, type, and normalized summary
        # If source_life_event_id is provided, check for that exact ID
        if payload.source_life_event_id:
            query = select(EmotionEventRecord).where(
                EmotionEventRecord.character_id == payload.character_id,
                EmotionEventRecord.source_life_event_id == payload.source_life_event_id,
            )
            result = await self._session.execute(query)
            existing = result.scalars().first()
            if existing:
                logger.info("Skipping duplicate emotion event for life event %s", payload.source_life_event_id)
                return None
        
        query = select(EmotionEventRecord).where(
            EmotionEventRecord.character_id == payload.character_id,
            EmotionEventRecord.event_type == payload.event_type.value,
        )
        result = await self._session.execute(query)
        existing_records = result.scalars().all()

        for existing in existing_records:
            if existing.summary.strip().lower() == normalized_summary:
                logger.info(
                    "Skipping duplicate emotion event for type %s on character %s.",
                    payload.event_type.value,
                    payload.character_id,
                )
                return None

        # Create and persist new record
        record = EmotionEventRecord(
            character_id=payload.character_id,
            event_type=payload.event_type.value,
            summary=payload.summary.strip(),
            source=payload.source.value,
            source_life_event_id=payload.source_life_event_id,
            emotional_relevance=payload.emotional_relevance,
        )
        if payload.created_at is not None:
            record.created_at = payload.created_at
            
        self._session.add(record)
        if commit:
            await self._session.commit()
            await self._session.refresh(record)
        else:
            await self._session.flush()

        return self._record_to_domain(record)

    async def get_event(
        self,
        event_id: str,
    ) -> EmotionEvent | None:
        """Retrieve a specific emotion event by ID."""
        query = select(EmotionEventRecord).where(EmotionEventRecord.id == event_id)
        result = await self._session.execute(query)
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return self._record_to_domain(record)

    async def list_events(
        self,
        character_id: str = DEFAULT_CHARACTER_ID,
        limit: int = DEFAULT_EMOTION_EVENTS_LIST_LIMIT,
        event_type: EmotionEventType | None = None,
    ) -> list[EmotionEvent]:
        """List emotion events in reverse chronological order (newest first).

        Deterministic ordering:
        ORDER BY created_at DESC, id DESC

        Limits:
        Enforces upper bound MAX_EMOTION_EVENTS_LIST_LIMIT = 50.
        """
        clamped_limit = max(1, min(limit, MAX_EMOTION_EVENTS_LIST_LIMIT))

        query = select(EmotionEventRecord).where(
            EmotionEventRecord.character_id == character_id
        )
        if event_type is not None:
            query = query.where(
                EmotionEventRecord.event_type == event_type.value
            )

        query = query.order_by(
            EmotionEventRecord.created_at.desc(),
            EmotionEventRecord.id.desc(),
        ).limit(clamped_limit)

        result = await self._session.execute(query)
        records = result.scalars().all()
        return [self._record_to_domain(r) for r in records]

    async def delete_event(
        self,
        event_id: str,
    ) -> bool:
        """Delete an emotion event by ID.

        Returns:
            True if an event was deleted, False otherwise.
        """
        record = (
            await self._session.scalars(
                select(EmotionEventRecord).where(EmotionEventRecord.id == event_id)
            )
        ).first()
        if record is None:
            return False
        await self._session.delete(record)
        await self._session.commit()
        return True

    @staticmethod
    def _record_to_domain(record: EmotionEventRecord) -> EmotionEvent:
        """Map persistent SQLAlchemy record to immutable domain model."""
        return EmotionEvent(
            id=record.id,
            character_id=record.character_id,
            event_type=EmotionEventType(record.event_type),
            summary=record.summary,
            source=EmotionEventSource(record.source),
            source_life_event_id=record.source_life_event_id,
            emotional_relevance=record.emotional_relevance,
            created_at=_ensure_utc(record.created_at),
        )
