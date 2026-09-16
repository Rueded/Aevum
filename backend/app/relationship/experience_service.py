"""Relationship experience and history service for Aevum Core.

Manages recording, deduplication, retrieval, and querying of historical
relationship-relevant interaction experiences.
"""

from collections.abc import Sequence
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RelationshipExperienceRecord
from app.relationship.experience_models import (
    RelationshipExperience,
    RelationshipExperienceCreate,
    RelationshipExperienceType,
    map_signal_to_experience_create,
)
from app.relationship.models import DEFAULT_RELATIONSHIP_ID, RelationshipSignal
from app.relationship.policy import filter_eligible_signals

logger = logging.getLogger(__name__)

MAX_EXPERIENCES_LIST_LIMIT: int = 50
DEFAULT_EXPERIENCES_LIST_LIMIT: int = 20


class RelationshipExperienceService:
    """Service for managing persistent RelationshipExperience records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_experience(
        self,
        payload: RelationshipExperienceCreate,
    ) -> RelationshipExperience | None:
        """Persist a relationship experience if it is not an exact duplicate.

        Deterministic duplicate protection:
        Checks whether an experience with identical (relationship_id, experience_type, normalized_summary)
        already exists.

        Returns:
            The created RelationshipExperience, or None if skipped as duplicate.
        """
        normalized_summary = payload.summary.strip().lower()

        # Check existing experiences for identical type and normalized summary
        query = select(RelationshipExperienceRecord).where(
            RelationshipExperienceRecord.relationship_id == payload.relationship_id,
            RelationshipExperienceRecord.experience_type == payload.experience_type.value,
        )
        result = await self._session.execute(query)
        existing_records = result.scalars().all()

        for existing in existing_records:
            if existing.summary.strip().lower() == normalized_summary:
                logger.info(
                    "Skipping duplicate relationship experience for type %s in relationship %s.",
                    payload.experience_type.value,
                    payload.relationship_id,
                )
                return None

        # Create and persist new record
        record = RelationshipExperienceRecord(
            relationship_id=payload.relationship_id,
            experience_type=payload.experience_type.value,
            source=payload.source.value,
            summary=payload.summary.strip(),
            significance=payload.significance,
            confidence=payload.confidence,
        )
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)

        return self._record_to_domain(record)

    async def get_experience(
        self,
        experience_id: str,
    ) -> RelationshipExperience | None:
        """Retrieve a specific experience by ID."""
        query = select(RelationshipExperienceRecord).where(
            RelationshipExperienceRecord.id == experience_id
        )
        result = await self._session.execute(query)
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return self._record_to_domain(record)

    async def list_experiences(
        self,
        relationship_id: str = DEFAULT_RELATIONSHIP_ID,
        limit: int = DEFAULT_EXPERIENCES_LIST_LIMIT,
        experience_type: RelationshipExperienceType | None = None,
    ) -> list[RelationshipExperience]:
        """List relationship experiences in reverse chronological order (newest first).

        Deterministic ordering:
        ORDER BY created_at DESC, id DESC

        Limits:
        Enforces upper bound MAX_EXPERIENCES_LIST_LIMIT = 50.
        """
        clamped_limit = max(1, min(limit, MAX_EXPERIENCES_LIST_LIMIT))

        query = select(RelationshipExperienceRecord).where(
            RelationshipExperienceRecord.relationship_id == relationship_id
        )
        if experience_type is not None:
            query = query.where(
                RelationshipExperienceRecord.experience_type == experience_type.value
            )

        query = query.order_by(
            RelationshipExperienceRecord.created_at.desc(),
            RelationshipExperienceRecord.id.desc(),
        ).limit(clamped_limit)

        result = await self._session.execute(query)
        records = result.scalars().all()
        return [self._record_to_domain(r) for r in records]

    async def record_signals(
        self,
        signals: Sequence[RelationshipSignal],
        relationship_id: str = DEFAULT_RELATIONSHIP_ID,
    ) -> list[RelationshipExperience]:
        """Process accepted relationship signals into persistent relationship experiences.

        Only signals that survive deterministic policy evaluation (confidence >= 0.70, strength >= 0.10,
        contradiction resolution, deduplication) are mapped and recorded.

        Returns:
            List of successfully recorded RelationshipExperience domain objects.
        """
        eligible = filter_eligible_signals(signals)
        recorded: list[RelationshipExperience] = []

        for sig in eligible:
            create_payload = map_signal_to_experience_create(
                signal=sig,
                relationship_id=relationship_id,
            )
            exp = await self.create_experience(create_payload)
            if exp is not None:
                recorded.append(exp)

        return recorded

    @staticmethod
    def _record_to_domain(record: RelationshipExperienceRecord) -> RelationshipExperience:
        """Convert ORM record to immutable domain model."""
        return RelationshipExperience(
            id=record.id,
            relationship_id=record.relationship_id,
            experience_type=RelationshipExperienceType(record.experience_type),
            source=record.source,
            summary=record.summary,
            significance=record.significance,
            confidence=record.confidence,
            created_at=record.created_at,
        )
