"""Character state service for Aevum Core.

Provides application-owned retrieval, initial deterministic baseline seeding,
and atomic updates for mutable character state with database-enforced
optimistic concurrency control.
"""

from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.state_models import (
    CharacterMood,
    CharacterState,
    CharacterStateUpdate,
)
from app.db.models import CharacterStateRecord, utc_now


class CharacterStateConflictError(Exception):
    """Raised when a state update fails due to an optimistic concurrency version mismatch."""

    def __init__(self, expected_version: int, actual_version: int) -> None:
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"Character state version mismatch: expected {expected_version}, but current version is {actual_version}"
        )


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime has UTC timezone info attached."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def create_initial_aevum_state() -> CharacterState:
    """Construct the canonical initial CharacterState baseline for Aevum.

    Note:
    - Activity ('resting') and Location ('home') are deterministic bootstrap defaults
      and do not imply permanent placement; future Life simulation systems will drive them.
    - Mood is qualitative ('neutral') and metrics are balanced/moderate.
    """
    return CharacterState(
        id="aevum",
        version=1,
        updated_at=utc_now(),
        mood=CharacterMood.NEUTRAL,
        energy=0.7,
        stress=0.2,
        social_energy=0.6,
        confidence=0.7,
        irritation=0.0,
        loneliness=0.3,
        current_activity="resting",
        current_location="home",
    )


class CharacterStateService:
    """Application-owned service managing persistent character state."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_state(self, character_id: str = "aevum") -> CharacterState:
        """Load character state, creating deterministic initial baseline if none exists."""
        stmt = select(CharacterStateRecord).where(CharacterStateRecord.id == character_id)
        record = (await self._session.scalars(stmt)).first()

        if record is None:
            initial = create_initial_aevum_state()
            await self._persist_initial_state(initial)
            record = (await self._session.scalars(stmt)).first()
            if record is None:
                raise RuntimeError("Failed to initialize character state record.")

        return self._record_to_domain(record)

    async def update_state(
        self,
        updated_state: CharacterState,
        expected_version: int | None = None,
        character_id: str = "aevum",
        commit: bool = True,
    ) -> CharacterState:
        """Update character state atomically with database-enforced optimistic concurrency."""
        now = utc_now()
        mood_str = (
            updated_state.mood.value
            if hasattr(updated_state.mood, "value")
            else str(updated_state.mood)
        )

        if expected_version is not None:
            update_stmt = (
                update(CharacterStateRecord)
                .where(
                    CharacterStateRecord.id == character_id,
                    CharacterStateRecord.version == expected_version,
                )
                .values(
                    version=CharacterStateRecord.version + 1,
                    updated_at=now,
                    mood=mood_str,
                    energy=updated_state.energy,
                    stress=updated_state.stress,
                    social_energy=updated_state.social_energy,
                    confidence=updated_state.confidence,
                    irritation=updated_state.irritation,
                    loneliness=updated_state.loneliness,
                    current_activity=updated_state.current_activity,
                    current_location=updated_state.current_location,
                )
            )
            result = await self._session.execute(update_stmt)
            if result.rowcount == 0:
                current_v = (
                    await self._session.scalars(
                        select(CharacterStateRecord.version).where(
                            CharacterStateRecord.id == character_id
                        )
                    )
                ).first()
                actual_version = current_v if current_v is not None else 0
                raise CharacterStateConflictError(
                    expected_version=expected_version,
                    actual_version=actual_version,
                )
        else:
            update_stmt = (
                update(CharacterStateRecord)
                .where(CharacterStateRecord.id == character_id)
                .values(
                    version=CharacterStateRecord.version + 1,
                    updated_at=now,
                    mood=mood_str,
                    energy=updated_state.energy,
                    stress=updated_state.stress,
                    social_energy=updated_state.social_energy,
                    confidence=updated_state.confidence,
                    irritation=updated_state.irritation,
                    loneliness=updated_state.loneliness,
                    current_activity=updated_state.current_activity,
                    current_location=updated_state.current_location,
                )
            )
            result = await self._session.execute(update_stmt)
            if result.rowcount == 0:
                raise CharacterStateConflictError(
                    expected_version=0,
                    actual_version=0,
                )

        if commit:
            await self._session.commit()
        else:
            await self._session.flush()
        return await self.get_state(character_id=character_id)

    async def apply_update(
        self,
        state_update: CharacterStateUpdate,
        expected_version: int | None = None,
        character_id: str = "aevum",
        commit: bool = True,
    ) -> CharacterState:
        """Apply a validated partial state replacement request atomically with optimistic concurrency."""
        # 1. Load current canonical state (seeding initial state if table is empty)
        current = await self.get_state(character_id=character_id)

        # 2. Merge supplied fields with existing values (preserving unspecified fields)
        mood = state_update.mood if state_update.mood is not None else current.mood
        mood_str = mood.value if hasattr(mood, "value") else str(mood)
        energy = state_update.energy if state_update.energy is not None else current.energy
        stress = state_update.stress if state_update.stress is not None else current.stress
        social_energy = state_update.social_energy if state_update.social_energy is not None else current.social_energy
        confidence = state_update.confidence if state_update.confidence is not None else current.confidence
        irritation = state_update.irritation if state_update.irritation is not None else current.irritation
        loneliness = state_update.loneliness if state_update.loneliness is not None else current.loneliness
        current_activity = state_update.current_activity if state_update.current_activity is not None else current.current_activity
        current_location = state_update.current_location if state_update.current_location is not None else current.current_location

        # 3. Validate merged candidate state against domain invariants
        CharacterState(
            id=current.id,
            version=current.version + 1,
            updated_at=utc_now(),
            mood=mood,
            energy=energy,
            stress=stress,
            social_energy=social_energy,
            confidence=confidence,
            irritation=irritation,
            loneliness=loneliness,
            current_activity=current_activity,
            current_location=current_location,
        )

        # 4. Perform database-level optimistic concurrency update
        now = utc_now()
        if expected_version is not None:
            update_stmt = (
                update(CharacterStateRecord)
                .where(
                    CharacterStateRecord.id == character_id,
                    CharacterStateRecord.version == expected_version,
                )
                .values(
                    version=CharacterStateRecord.version + 1,
                    updated_at=now,
                    mood=mood_str,
                    energy=energy,
                    stress=stress,
                    social_energy=social_energy,
                    confidence=confidence,
                    irritation=irritation,
                    loneliness=loneliness,
                    current_activity=current_activity,
                    current_location=current_location,
                )
            )
            result = await self._session.execute(update_stmt)
            if result.rowcount == 0:
                current_v = (
                    await self._session.scalars(
                        select(CharacterStateRecord.version).where(
                            CharacterStateRecord.id == character_id
                        )
                    )
                ).first()
                actual_version = current_v if current_v is not None else 0
                raise CharacterStateConflictError(
                    expected_version=expected_version,
                    actual_version=actual_version,
                )
        else:
            update_stmt = (
                update(CharacterStateRecord)
                .where(CharacterStateRecord.id == character_id)
                .values(
                    version=CharacterStateRecord.version + 1,
                    updated_at=now,
                    mood=mood_str,
                    energy=energy,
                    stress=stress,
                    social_energy=social_energy,
                    confidence=confidence,
                    irritation=irritation,
                    loneliness=loneliness,
                    current_activity=current_activity,
                    current_location=current_location,
                )
            )
            result = await self._session.execute(update_stmt)
            if result.rowcount == 0:
                raise CharacterStateConflictError(
                    expected_version=0,
                    actual_version=0,
                )

        if commit:
            await self._session.commit()
        else:
            await self._session.flush()
        return await self.get_state(character_id=character_id)

    async def _persist_initial_state(self, state: CharacterState) -> None:
        """Persist a new initial character state record."""
        rec = CharacterStateRecord(
            id=state.id,
            version=state.version,
            updated_at=state.updated_at,
            mood=state.mood.value,
            energy=state.energy,
            stress=state.stress,
            social_energy=state.social_energy,
            confidence=state.confidence,
            irritation=state.irritation,
            loneliness=state.loneliness,
            current_activity=state.current_activity,
            current_location=state.current_location,
        )
        self._session.add(rec)
        await self._session.commit()

    def _record_to_domain(self, record: CharacterStateRecord) -> CharacterState:
        """Convert an SQLAlchemy CharacterStateRecord into an immutable CharacterState domain model."""
        return CharacterState(
            id=record.id,
            version=record.version,
            updated_at=_ensure_utc(record.updated_at),
            mood=CharacterMood(record.mood),
            energy=record.energy,
            stress=record.stress,
            social_energy=record.social_energy,
            confidence=record.confidence,
            irritation=record.irritation,
            loneliness=record.loneliness,
            current_activity=record.current_activity,
            current_location=record.current_location,
        )


async def get_character_state(
    session: AsyncSession,
    character_id: str = "aevum",
) -> CharacterState:
    """Convenience function to get canonical character state."""
    service = CharacterStateService(session)
    return await service.get_state(character_id=character_id)


async def update_character_state(
    session: AsyncSession,
    updated_state: CharacterState,
    expected_version: int | None = None,
    character_id: str = "aevum",
) -> CharacterState:
    """Convenience function to update canonical character state."""
    service = CharacterStateService(session)
    return await service.update_state(
        updated_state=updated_state,
        expected_version=expected_version,
        character_id=character_id,
    )


async def apply_character_state_update(
    session: AsyncSession,
    state_update: CharacterStateUpdate,
    expected_version: int | None = None,
    character_id: str = "aevum",
) -> CharacterState:
    """Convenience function to apply a validated partial character state update."""
    service = CharacterStateService(session)
    return await service.apply_update(
        state_update=state_update,
        expected_version=expected_version,
        character_id=character_id,
    )

