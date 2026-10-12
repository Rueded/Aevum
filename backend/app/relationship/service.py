"""Relationship service for Aevum Core.

Provides application-owned retrieval, initial deterministic baseline seeding,
and atomic updates for multidimensional relationship state with database-enforced
optimistic concurrency control.
"""

from datetime import datetime, timezone
import logging
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RelationshipRecord, utc_now
from app.relationship.models import (
    BOOTSTRAP_AFFECTION,
    BOOTSTRAP_ATTACHMENT,
    BOOTSTRAP_COMFORT,
    BOOTSTRAP_FAMILIARITY,
    BOOTSTRAP_RESPECT,
    BOOTSTRAP_TRUST,
    DEFAULT_RELATIONSHIP_ID,
    DEFAULT_USER_ID,
    RelationshipState,
    RelationshipStateUpdate,
)

logger = logging.getLogger(__name__)


class RelationshipConflictError(Exception):
    """Raised when a relationship state update fails due to an optimistic concurrency version mismatch."""

    def __init__(self, expected_version: int, actual_version: int) -> None:
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"Relationship state version mismatch: expected version {expected_version}, "
            f"but current database version is {actual_version}."
        )


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime has UTC timezone info attached."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def create_initial_relationship_state(
    relationship_id: str = DEFAULT_RELATIONSHIP_ID,
    user_id: str = DEFAULT_USER_ID,
) -> RelationshipState:
    """Construct the canonical initial RelationshipState baseline for Aevum and the user.

    Semantics:
    - Represents newly acquainted strangers.
    - Zero romantic affection or attachment (affection=0.0, attachment=0.0).
    - Modest baseline trust (0.20), low comfort (0.10), minimal familiarity (0.05).
    - Respect starts at a healthy, positive baseline (0.50).
    - Version begins at 1.
    """
    now = utc_now()
    return RelationshipState(
        id=relationship_id,
        user_id=user_id,
        version=1,
        created_at=now,
        updated_at=now,
        familiarity=BOOTSTRAP_FAMILIARITY,
        trust=BOOTSTRAP_TRUST,
        comfort=BOOTSTRAP_COMFORT,
        affection=BOOTSTRAP_AFFECTION,
        attachment=BOOTSTRAP_ATTACHMENT,
        respect=BOOTSTRAP_RESPECT,
    )


class RelationshipService:
    """Application-owned service managing persistent relationship state."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_relationship_state(
        self,
        relationship_id: str = DEFAULT_RELATIONSHIP_ID,
    ) -> RelationshipState:
        """Load relationship state, creating deterministic initial baseline if none exists.

        Guarantees read-only semantics: repeated reads do not mutate version or timestamps.
        """
        stmt = select(RelationshipRecord).where(RelationshipRecord.id == relationship_id)
        record = (await self._session.scalars(stmt)).first()

        if record is None:
            initial = create_initial_relationship_state(relationship_id=relationship_id)
            await self._persist_initial_state(initial)
            record = (await self._session.scalars(stmt)).first()
            if record is None:
                raise RuntimeError("Failed to initialize relationship state record.")

        return self._record_to_domain(record)

    async def update_relationship_state(
        self,
        updated_state: RelationshipState,
        expected_version: int | None = None,
        relationship_id: str = DEFAULT_RELATIONSHIP_ID,
    ) -> RelationshipState:
        """Update entire relationship state atomically with database-enforced optimistic concurrency."""
        now = utc_now()

        if expected_version is not None:
            update_stmt = (
                update(RelationshipRecord)
                .where(
                    RelationshipRecord.id == relationship_id,
                    RelationshipRecord.version == expected_version,
                )
                .values(
                    version=RelationshipRecord.version + 1,
                    updated_at=now,
                    familiarity=updated_state.familiarity,
                    trust=updated_state.trust,
                    comfort=updated_state.comfort,
                    affection=updated_state.affection,
                    attachment=updated_state.attachment,
                    respect=updated_state.respect,
                )
            )
            result = await self._session.execute(update_stmt)
            if result.rowcount == 0:
                current_v = (
                    await self._session.scalars(
                        select(RelationshipRecord.version).where(
                            RelationshipRecord.id == relationship_id
                        )
                    )
                ).first()
                actual_version = current_v if current_v is not None else 0
                raise RelationshipConflictError(
                    expected_version=expected_version,
                    actual_version=actual_version,
                )
        else:
            update_stmt = (
                update(RelationshipRecord)
                .where(RelationshipRecord.id == relationship_id)
                .values(
                    version=RelationshipRecord.version + 1,
                    updated_at=now,
                    familiarity=updated_state.familiarity,
                    trust=updated_state.trust,
                    comfort=updated_state.comfort,
                    affection=updated_state.affection,
                    attachment=updated_state.attachment,
                    respect=updated_state.respect,
                )
            )
            result = await self._session.execute(update_stmt)
            if result.rowcount == 0:
                raise RelationshipConflictError(
                    expected_version=0,
                    actual_version=0,
                )

        await self._session.commit()
        return await self.get_relationship_state(relationship_id=relationship_id)

    async def apply_update(
        self,
        update_data: RelationshipStateUpdate,
        expected_version: int | None = None,
        relationship_id: str = DEFAULT_RELATIONSHIP_ID,
    ) -> RelationshipState:
        """Apply a validated partial replacement request atomically with optimistic concurrency.

        Semantics:
        - Explicit target values (replaces supplied fields, preserves unspecified fields).
        - Atomic execution (all-or-nothing database update).
        - Rejects stale writes with RelationshipConflictError.
        """
        # 1. Load current canonical state (seeding initial baseline if record is absent)
        current = await self.get_relationship_state(relationship_id=relationship_id)

        # 2. Merge supplied target values, preserving unspecified fields
        familiarity = update_data.familiarity if update_data.familiarity is not None else current.familiarity
        trust = update_data.trust if update_data.trust is not None else current.trust
        comfort = update_data.comfort if update_data.comfort is not None else current.comfort
        affection = update_data.affection if update_data.affection is not None else current.affection
        attachment = update_data.attachment if update_data.attachment is not None else current.attachment
        respect = update_data.respect if update_data.respect is not None else current.respect

        now = utc_now()

        # 3. Database-enforced atomic conditional update
        if expected_version is not None:
            update_stmt = (
                update(RelationshipRecord)
                .where(
                    RelationshipRecord.id == relationship_id,
                    RelationshipRecord.version == expected_version,
                )
                .values(
                    version=RelationshipRecord.version + 1,
                    updated_at=now,
                    familiarity=familiarity,
                    trust=trust,
                    comfort=comfort,
                    affection=affection,
                    attachment=attachment,
                    respect=respect,
                )
            )
            result = await self._session.execute(update_stmt)
            if result.rowcount == 0:
                current_v = (
                    await self._session.scalars(
                        select(RelationshipRecord.version).where(
                            RelationshipRecord.id == relationship_id
                        )
                    )
                ).first()
                actual_version = current_v if current_v is not None else 0
                raise RelationshipConflictError(
                    expected_version=expected_version,
                    actual_version=actual_version,
                )
        else:
            update_stmt = (
                update(RelationshipRecord)
                .where(RelationshipRecord.id == relationship_id)
                .values(
                    version=RelationshipRecord.version + 1,
                    updated_at=now,
                    familiarity=familiarity,
                    trust=trust,
                    comfort=comfort,
                    affection=affection,
                    attachment=attachment,
                    respect=respect,
                )
            )
            result = await self._session.execute(update_stmt)
            if result.rowcount == 0:
                raise RelationshipConflictError(
                    expected_version=0,
                    actual_version=0,
                )

        await self._session.commit()
        updated_state = await self.get_relationship_state(relationship_id=relationship_id)
        try:
            from app.core.firestore_sync import sync_relationship_to_firestore
            sync_relationship_to_firestore(
                user_id=updated_state.user_id,
                affection=updated_state.affection,
                familiarity=updated_state.familiarity,
                trust=updated_state.trust,
                comfort=updated_state.comfort,
                attachment=updated_state.attachment,
                respect=updated_state.respect,
                version=updated_state.version,
            )
        except Exception:
            pass
        return updated_state

    async def _persist_initial_state(self, initial: RelationshipState) -> None:
        """Persist the initial RelationshipRecord to SQLite."""
        record = RelationshipRecord(
            id=initial.id,
            user_id=initial.user_id,
            version=initial.version,
            created_at=_ensure_utc(initial.created_at),
            updated_at=_ensure_utc(initial.updated_at),
            familiarity=initial.familiarity,
            trust=initial.trust,
            comfort=initial.comfort,
            affection=initial.affection,
            attachment=initial.attachment,
            respect=initial.respect,
        )
        self._session.add(record)
        await self._session.commit()

    @staticmethod
    def _record_to_domain(record: RelationshipRecord) -> RelationshipState:
        """Map a database RelationshipRecord to an immutable RelationshipState domain model."""
        return RelationshipState(
            id=record.id,
            user_id=record.user_id,
            version=record.version,
            created_at=_ensure_utc(record.created_at),
            updated_at=_ensure_utc(record.updated_at),
            familiarity=record.familiarity,
            trust=record.trust,
            comfort=record.comfort,
            affection=record.affection,
            attachment=record.attachment,
            respect=record.respect,
        )


# =============================================================================
# Convenience module-level functions
# =============================================================================


async def get_relationship_state(
    session: AsyncSession,
    relationship_id: str = DEFAULT_RELATIONSHIP_ID,
) -> RelationshipState:
    """Convenience helper to retrieve canonical relationship state."""
    service = RelationshipService(session)
    return await service.get_relationship_state(relationship_id=relationship_id)


async def update_relationship_state(
    session: AsyncSession,
    updated_state: RelationshipState,
    expected_version: int | None = None,
    relationship_id: str = DEFAULT_RELATIONSHIP_ID,
) -> RelationshipState:
    """Convenience helper to update entire relationship state."""
    service = RelationshipService(session)
    return await service.update_relationship_state(
        updated_state=updated_state,
        expected_version=expected_version,
        relationship_id=relationship_id,
    )


async def apply_relationship_update(
    session: AsyncSession,
    update_data: RelationshipStateUpdate,
    expected_version: int | None = None,
    relationship_id: str = DEFAULT_RELATIONSHIP_ID,
) -> RelationshipState:
    """Convenience helper to apply a partial relationship update."""
    service = RelationshipService(session)
    return await service.apply_update(
        update_data=update_data,
        expected_version=expected_version,
        relationship_id=relationship_id,
    )
