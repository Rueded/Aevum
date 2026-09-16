"""Emotion influence service for Aevum Core.

Manages recording, deduplication, retrieval, and querying of historical
emotional influences without applying them or mutating EmotionState.
"""

from datetime import datetime, timezone
import logging
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    CharacterDefinitionRecord,
    EmotionEventRecord,
    EmotionInfluenceRecord,
)
from app.emotion.emotion_models import DEFAULT_CHARACTER_ID, EmotionType
from app.emotion.influence_models import (
    EmotionInfluence,
    EmotionInfluenceCreate,
    EmotionInfluenceDirection,
)

logger = logging.getLogger(__name__)

MAX_EMOTION_INFLUENCES_LIST_LIMIT: int = 50
DEFAULT_EMOTION_INFLUENCES_LIST_LIMIT: int = 20


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime has UTC timezone info attached."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class EmotionInfluenceService:
    """Application-owned service managing persistent EmotionInfluence records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_influence(
        self,
        payload: EmotionInfluenceCreate,
    ) -> EmotionInfluence | None:
        """Persist an emotion influence proposal if it is not an exact duplicate.

        Validates that the originating event exists, enforces deterministic duplicate
        protection on (character_id, event_id, target_emotion, direction, normalized_reason),
        and commits to SQLite.

        Returns:
            The created EmotionInfluence, or None if skipped as duplicate.
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

        # Ensure originating event exists
        event_stmt = select(EmotionEventRecord).where(EmotionEventRecord.id == payload.event_id)
        event_record = (await self._session.scalars(event_stmt)).first()
        if event_record is None:
            raise ValueError(f"Originating emotion event '{payload.event_id}' not found.")

        normalized_reason = payload.reason.strip().lower()

        # Check existing influences for duplicate match
        query = select(EmotionInfluenceRecord).where(
            EmotionInfluenceRecord.character_id == payload.character_id,
            EmotionInfluenceRecord.event_id == payload.event_id,
            EmotionInfluenceRecord.target_emotion == payload.target_emotion.value,
            EmotionInfluenceRecord.direction == payload.direction.value,
        )
        result = await self._session.execute(query)
        existing_records = result.scalars().all()

        for existing in existing_records:
            if existing.reason.strip().lower() == normalized_reason:
                logger.info(
                    "Skipping duplicate emotion influence for target %s on event %s.",
                    payload.target_emotion.value,
                    payload.event_id,
                )
                return None

        # Create and persist new record
        record = EmotionInfluenceRecord(
            character_id=payload.character_id,
            event_id=payload.event_id,
            target_emotion=payload.target_emotion.value,
            direction=payload.direction.value,
            strength=payload.strength,
            reason=payload.reason.strip(),
        )
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)

        return self._record_to_domain(record)

    async def get_influence(
        self,
        influence_id: str,
    ) -> EmotionInfluence | None:
        """Retrieve a specific emotion influence by ID."""
        query = select(EmotionInfluenceRecord).where(EmotionInfluenceRecord.id == influence_id)
        result = await self._session.execute(query)
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return self._record_to_domain(record)

    async def list_influences(
        self,
        character_id: str = DEFAULT_CHARACTER_ID,
        event_id: str | None = None,
        limit: int = DEFAULT_EMOTION_INFLUENCES_LIST_LIMIT,
        target_emotion: EmotionType | None = None,
    ) -> list[EmotionInfluence]:
        """List emotion influences in reverse chronological order (newest first).

        Deterministic ordering:
        ORDER BY created_at DESC, id DESC

        Limits:
        Enforces upper bound MAX_EMOTION_INFLUENCES_LIST_LIMIT = 50.
        """
        clamped_limit = max(1, min(limit, MAX_EMOTION_INFLUENCES_LIST_LIMIT))

        query = select(EmotionInfluenceRecord).where(
            EmotionInfluenceRecord.character_id == character_id
        )
        if event_id is not None:
            query = query.where(EmotionInfluenceRecord.event_id == event_id)
        if target_emotion is not None:
            query = query.where(EmotionInfluenceRecord.target_emotion == target_emotion.value)

        query = query.order_by(
            EmotionInfluenceRecord.created_at.desc(),
            EmotionInfluenceRecord.id.desc(),
        ).limit(clamped_limit)

        result = await self._session.execute(query)
        records = result.scalars().all()
        return [self._record_to_domain(r) for r in records]

    async def delete_influence(
        self,
        influence_id: str,
    ) -> bool:
        """Delete an emotion influence by ID.

        Returns:
            True if an influence was deleted, False otherwise.
        """
        record = (
            await self._session.scalars(
                select(EmotionInfluenceRecord).where(EmotionInfluenceRecord.id == influence_id)
            )
        ).first()
        if record is None:
            return False
        await self._session.delete(record)
        await self._session.commit()
        return True

    @staticmethod
    def _record_to_domain(record: EmotionInfluenceRecord) -> EmotionInfluence:
        """Map persistent SQLAlchemy record to immutable domain model."""
        return EmotionInfluence(
            id=record.id,
            character_id=record.character_id,
            event_id=record.event_id,
            target_emotion=EmotionType(record.target_emotion),
            direction=EmotionInfluenceDirection(record.direction),
            strength=record.strength,
            reason=record.reason,
            created_at=_ensure_utc(record.created_at),
        )
