"""Emotion service for Aevum Core.

Provides application-owned retrieval, initial deterministic baseline seeding,
and atomic updates for dominant emotional state with database-enforced
optimistic concurrency control.
"""

from datetime import datetime, timezone
import logging
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CharacterDefinitionRecord, EmotionStateRecord, utc_now
from app.emotion.emotion_models import (
    DEFAULT_CHARACTER_ID,
    EmotionState,
    EmotionStateUpdate,
    EmotionType,
    create_initial_emotion_state,
)

logger = logging.getLogger(__name__)


class EmotionConflictError(Exception):
    """Raised when an emotion state update fails due to an optimistic concurrency version mismatch."""

    def __init__(self, expected_version: int, actual_version: int) -> None:
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"Emotion state version mismatch: expected version {expected_version}, "
            f"but current database version is {actual_version}."
        )


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime has UTC timezone info attached."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class EmotionService:
    """Application-owned service managing persistent emotion state."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_emotion_state(
        self,
        character_id: str = DEFAULT_CHARACTER_ID,
    ) -> EmotionState:
        """Load emotion state, creating deterministic initial baseline if none exists.

        Guarantees read-only semantics: repeated reads do not mutate version or timestamps.
        """
        stmt = select(EmotionStateRecord).where(EmotionStateRecord.character_id == character_id)
        record = (await self._session.scalars(stmt)).first()

        if record is None:
            # Ensure character definition exists if character_id matches default Aevum character
            char_stmt = select(CharacterDefinitionRecord).where(
                CharacterDefinitionRecord.id == character_id
            )
            char_record = (await self._session.scalars(char_stmt)).first()
            if char_record is None and character_id == DEFAULT_CHARACTER_ID:
                from app.character.service import CharacterDefinitionService

                await CharacterDefinitionService(self._session).get_character(character_id)

            initial = create_initial_emotion_state(character_id=character_id)
            await self._persist_initial_state(initial)
            record = (await self._session.scalars(stmt)).first()
            if record is None:
                raise RuntimeError("Failed to initialize emotion state record.")

        return self._record_to_domain(record)

    async def update_emotion_state(
        self,
        updated_state: EmotionState,
        expected_version: int | None = None,
        character_id: str = DEFAULT_CHARACTER_ID,
    ) -> EmotionState:
        """Update entire emotion state atomically with database-enforced optimistic concurrency."""
        now = utc_now()
        emotion_str = (
            updated_state.emotion_type.value
            if hasattr(updated_state.emotion_type, "value")
            else str(updated_state.emotion_type)
        )

        if expected_version is not None:
            update_stmt = (
                update(EmotionStateRecord)
                .where(
                    EmotionStateRecord.character_id == character_id,
                    EmotionStateRecord.version == expected_version,
                )
                .values(
                    version=EmotionStateRecord.version + 1,
                    updated_at=now,
                    emotion_type=emotion_str,
                    intensity=updated_state.intensity,
                )
            )
            result = await self._session.execute(update_stmt)
            if result.rowcount == 0:
                current_v = (
                    await self._session.scalars(
                        select(EmotionStateRecord.version).where(
                            EmotionStateRecord.character_id == character_id
                        )
                    )
                ).first()
                actual_version = current_v if current_v is not None else 0
                raise EmotionConflictError(
                    expected_version=expected_version,
                    actual_version=actual_version,
                )
        else:
            update_stmt = (
                update(EmotionStateRecord)
                .where(EmotionStateRecord.character_id == character_id)
                .values(
                    version=EmotionStateRecord.version + 1,
                    updated_at=now,
                    emotion_type=emotion_str,
                    intensity=updated_state.intensity,
                )
            )
            result = await self._session.execute(update_stmt)
            if result.rowcount == 0:
                raise EmotionConflictError(expected_version=0, actual_version=0)

        await self._session.commit()
        return await self.get_emotion_state(character_id=character_id)

    async def apply_update(
        self,
        state_update: EmotionStateUpdate,
        expected_version: int | None = None,
        character_id: str = DEFAULT_CHARACTER_ID,
    ) -> EmotionState:
        """Apply a validated partial replacement request atomically with optimistic concurrency."""
        current = await self.get_emotion_state(character_id=character_id)

        target_emotion = (
            state_update.emotion_type
            if state_update.emotion_type is not None
            else current.emotion_type
        )
        target_intensity = (
            state_update.intensity
            if state_update.intensity is not None
            else current.intensity
        )

        # Build candidate EmotionState to validate domain rules
        candidate = EmotionState(
            id=current.id,
            character_id=character_id,
            emotion_type=target_emotion,
            intensity=target_intensity,
            created_at=current.created_at,
            updated_at=utc_now(),
            version=current.version + 1,
        )

        target_version = expected_version if expected_version is not None else current.version
        return await self.update_emotion_state(
            updated_state=candidate,
            expected_version=target_version,
            character_id=character_id,
        )

    async def _persist_initial_state(self, state: EmotionState) -> None:
        """Persist a newly instantiated initial EmotionState to SQLite."""
        record = EmotionStateRecord(
            id=state.id,
            character_id=state.character_id,
            emotion_type=(
                state.emotion_type.value
                if hasattr(state.emotion_type, "value")
                else str(state.emotion_type)
            ),
            intensity=state.intensity,
            created_at=state.created_at,
            updated_at=state.updated_at,
            version=state.version,
        )
        self._session.add(record)
        await self._session.commit()

    @staticmethod
    def _record_to_domain(record: EmotionStateRecord) -> EmotionState:
        """Map persistent SQLAlchemy record to immutable domain model."""
        return EmotionState(
            id=record.id,
            character_id=record.character_id,
            emotion_type=EmotionType(record.emotion_type),
            intensity=record.intensity,
            created_at=_ensure_utc(record.created_at),
            updated_at=_ensure_utc(record.updated_at),
            version=record.version,
        )


async def get_emotion_state(
    session: AsyncSession,
    character_id: str = DEFAULT_CHARACTER_ID,
) -> EmotionState:
    """Convenience helper to retrieve current emotion state."""
    service = EmotionService(session)
    return await service.get_emotion_state(character_id=character_id)


async def update_emotion_state(
    session: AsyncSession,
    updated_state: EmotionState,
    expected_version: int | None = None,
    character_id: str = DEFAULT_CHARACTER_ID,
) -> EmotionState:
    """Convenience helper to update emotion state with optimistic concurrency."""
    service = EmotionService(session)
    return await service.update_emotion_state(
        updated_state=updated_state,
        expected_version=expected_version,
        character_id=character_id,
    )
