"""Repository layer for Phase 16.1 Personal Learning & Growth.

Enforces:
- Append-only experiential logging (strictly zero update/delete methods).
- Pre-persistence validation of interaction evidence and qualia barriers.
- Temporal ordering strictly by timeline_tick (Phase 8C AuthoritativeClock).
- Pure DTO boundaries between database models and domain consumers.
"""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.growth.experiential_models import (
    ExperientialRecord,
    ExposureEvent,
    InterestDomainRecord,
    InterestFacetRecord,
    ExperienceProvenanceKind,
    ExposureKind,
    ExposureState,
    FamiliarityLevel,
    validate_interaction_evidence_anchoring,
    validate_phase16_exposure_source,
    validate_qualia_evidence_barrier,
)
from app.growth.growth_db_models import (
    CharacterExperienceTable,
    CharacterInterestDomainTable,
    CharacterInterestFacetTable,
)


class ExperienceRepository:
    """Async repository providing strictly append-only and query operations for experiences and domains."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_experience(self, record: ExperientialRecord) -> ExperientialRecord:
        """Persist a new experiential record into the append-only event log.

        Validates evidence anchoring, qualia barriers, and Phase 17 lockout before staging.
        """
        # 1. Enforce Phase 17 lockout
        validate_phase16_exposure_source(record.exposure_kind)

        # 2. Enforce evidence anchoring
        validate_interaction_evidence_anchoring(record.provenance_kind, record.interaction_evidence_ref)

        # 3. Enforce qualia evidence barrier
        validate_qualia_evidence_barrier(record.interaction_evidence_ref, record.qualia_notes)

        # 4. Map DTO to DB model
        db_record = CharacterExperienceTable(
            id=record.experience_id,
            character_id=record.character_id,
            domain_key=record.domain_key,
            facet_key=record.facet_key,
            provenance_kind=record.provenance_kind.value,
            exposure_kind=record.exposure_kind.value,
            calendar_session_id=record.calendar_session_id,
            timeline_tick=record.timeline_tick,
            interaction_evidence_ref=record.interaction_evidence_ref,
            qualia_notes=record.qualia_notes,
            is_fictional_frame=record.is_fictional_frame,
        )

        self._session.add(db_record)
        await self._session.flush()

        return record

    async def get_experience(self, experience_id: str) -> Optional[ExperientialRecord]:
        """Fetch a single experiential record by its unique ID."""
        stmt = select(CharacterExperienceTable).where(CharacterExperienceTable.id == experience_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None

        return self._to_record_dto(row)

    async def list_experiences(
        self,
        character_id: str,
        domain_key: Optional[str] = None,
    ) -> list[ExperientialRecord]:
        """Retrieve experiences ordered strictly by Phase 8C timeline_tick ascending."""
        stmt = select(CharacterExperienceTable).where(
            CharacterExperienceTable.character_id == character_id
        )
        if domain_key is not None:
            stmt = stmt.where(CharacterExperienceTable.domain_key == domain_key)

        # Crucial Invariant: Order strictly by timeline_tick, NEVER by created_at
        stmt = stmt.order_by(CharacterExperienceTable.timeline_tick.asc(), CharacterExperienceTable.id.asc())

        result = await self._session.execute(stmt)
        rows = result.scalars().all()

        return [self._to_record_dto(row) for row in rows]

    async def register_domain(self, domain: InterestDomainRecord) -> InterestDomainRecord:
        """Register or update exposure state for an interest domain."""
        stmt = select(CharacterInterestDomainTable).where(
            CharacterInterestDomainTable.character_id == domain.character_id,
            CharacterInterestDomainTable.domain_key == domain.domain_key,
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            db_domain = CharacterInterestDomainTable(
                character_id=domain.character_id,
                domain_key=domain.domain_key,
                display_name=domain.display_name,
                exposure_state=domain.exposure_state.value,
                created_at_tick=domain.created_at_tick,
            )
            self._session.add(db_domain)
        else:
            existing.display_name = domain.display_name
            existing.exposure_state = domain.exposure_state.value

        await self._session.flush()
        return domain

    async def get_domain(self, character_id: str, domain_key: str) -> Optional[InterestDomainRecord]:
        """Fetch domain container if registered."""
        stmt = select(CharacterInterestDomainTable).where(
            CharacterInterestDomainTable.character_id == character_id,
            CharacterInterestDomainTable.domain_key == domain_key,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None

        return InterestDomainRecord(
            domain_key=row.domain_key,
            character_id=row.character_id,
            display_name=row.display_name,
            exposure_state=ExposureState(row.exposure_state),
            created_at_tick=row.created_at_tick,
        )

    async def register_facet(self, facet: InterestFacetRecord) -> InterestFacetRecord:
        """Register or update metadata for a sub-facet."""
        stmt = select(CharacterInterestFacetTable).where(
            CharacterInterestFacetTable.character_id == facet.character_id,
            CharacterInterestFacetTable.domain_key == facet.domain_key,
            CharacterInterestFacetTable.facet_key == facet.facet_key,
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            db_facet = CharacterInterestFacetTable(
                character_id=facet.character_id,
                domain_key=facet.domain_key,
                facet_key=facet.facet_key,
                display_name=facet.display_name,
                experience_count=facet.experience_count,
                familiarity_level=facet.familiarity_level.value,
                last_experienced_tick=facet.last_experienced_tick,
            )
            self._session.add(db_facet)
        else:
            existing.display_name = facet.display_name
            existing.experience_count = facet.experience_count
            existing.familiarity_level = facet.familiarity_level.value
            existing.last_experienced_tick = facet.last_experienced_tick

        await self._session.flush()
        return facet

    async def get_facet(
        self,
        character_id: str,
        domain_key: str,
        facet_key: str,
    ) -> Optional[InterestFacetRecord]:
        """Fetch sub-facet record if registered."""
        stmt = select(CharacterInterestFacetTable).where(
            CharacterInterestFacetTable.character_id == character_id,
            CharacterInterestFacetTable.domain_key == domain_key,
            CharacterInterestFacetTable.facet_key == facet_key,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None

        return InterestFacetRecord(
            facet_key=row.facet_key,
            domain_key=row.domain_key,
            character_id=row.character_id,
            display_name=row.display_name,
            experience_count=row.experience_count,
            familiarity_level=FamiliarityLevel(row.familiarity_level),
            last_experienced_tick=row.last_experienced_tick,
        )

    def _to_record_dto(self, row: CharacterExperienceTable) -> ExperientialRecord:
        """Convert a database row into an immutable ExperientialRecord DTO."""
        return ExperientialRecord(
            experience_id=row.id,
            character_id=row.character_id,
            domain_key=row.domain_key,
            facet_key=row.facet_key,
            provenance_kind=ExperienceProvenanceKind(row.provenance_kind),
            exposure_kind=ExposureKind(row.exposure_kind),
            calendar_session_id=row.calendar_session_id,
            timeline_tick=row.timeline_tick,
            interaction_evidence_ref=row.interaction_evidence_ref,
            qualia_notes=row.qualia_notes,
            is_fictional_frame=row.is_fictional_frame,
        )
