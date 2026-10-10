"""Interest Domain Service (Phase 16.2).

Coordinates data retrieval from ExperienceRepository and computes deterministic,
ephemeral PersonalGrowthState projections and derived LifecycleStage postures.

Constitutional Invariants Enforced:
- Rule 11 & Rule 12: Zero direct mutation to character_core_facts or reality authority.
- Ephemeral Derived Projection Lock: All metrics and states are computed deterministically
  on-demand from the append-only event stream; never persisted as mutable growth state.
- Phase 8C Temporal Order: Records queried from repository maintain strict timeline_tick ordering.
- Provenance Barrier: Non-eligible records are strictly filtered from personal growth metrics.
- Domain Isolation: Curiosity resolution is strictly evaluated against matching domain experiences.
"""

from __future__ import annotations

from typing import Optional, Sequence

from app.growth.experience_repository import ExperienceRepository
from app.growth.experiential_models import ExposureState
from app.growth.state_machine import (
    CuriosityEvidence,
    CuriosityState,
    LifecycleStage,
    PersonalGrowthState,
    derive_curiosity_state,
    derive_lifecycle_stage,
    evaluate_experience_level,
    evaluate_familiarity_level,
    is_eligible_personal_experience,
)


class InterestDomainService:
    """Service orchestrating domain evaluation and personal growth state projections."""

    def __init__(self, repository: ExperienceRepository) -> None:
        self._repo = repository

    async def evaluate_growth_state(
        self,
        character_id: str,
        domain_key: str,
        curiosity_evidence_chain: Sequence[CuriosityEvidence] = (),
    ) -> PersonalGrowthState:
        """Evaluate the consolidated orthogonal PersonalGrowthState for a domain from DB records.

        Steps:
        1. Fetch all ExperientialRecords for (character_id, domain_key) in Phase 8C timeline_tick order.
        2. Filter records to only eligible personal lived experiences (Lock 1 & Lock 9).
        3. Fetch registered domain record if available to determine canonical exposure_state.
        4. Derive curiosity_state strictly from validated evidence chain and eligible domain experiences.
        5. Evaluate experience_level based on eligible experience count and distinct session count.
        6. Evaluate familiarity_level based on facet breadth and longitudinal session dispersion.
        7. Compute ephemeral projection metrics (zero independent mutable persistence).
        8. Construct and return immutable PersonalGrowthState.
        """
        # 1. Fetch raw experiential records (already sorted by timeline_tick.asc())
        all_records = await self._repo.list_experiences(character_id=character_id, domain_key=domain_key)

        # 2. Provenance eligibility filtering (Lock 1 & Lock 9)
        eligible = [r for r in all_records if is_eligible_personal_experience(r)]

        # 3. Retrieve domain exposure state
        domain_record = await self._repo.get_domain(character_id=character_id, domain_key=domain_key)
        if domain_record is not None:
            exposure_state = domain_record.exposure_state
        else:
            # If not explicitly registered, presence of eligible experiences implies DIRECTLY_ENCOUNTERED;
            # presence of curiosity/exposure records implies EXPOSED; otherwise UNEXPOSED
            if eligible:
                exposure_state = ExposureState.DIRECTLY_ENCOUNTERED
            elif all_records or curiosity_evidence_chain:
                exposure_state = ExposureState.EXPOSED
            else:
                exposure_state = ExposureState.UNEXPOSED

        # 4. Derive curiosity posture with domain isolation
        curiosity_state = derive_curiosity_state(
            curiosity_evidence_chain=curiosity_evidence_chain,
            eligible_experience_records=eligible,
            domain_key=domain_key,
        )

        # 5. Evaluate orthogonal experience level
        experience_level = evaluate_experience_level(eligible)

        # 6. Evaluate orthogonal familiarity level
        familiarity_level = evaluate_familiarity_level(exposure_state, eligible)

        # 7. Compute ephemeral metrics
        distinct_sessions = {r.calendar_session_id for r in eligible if r.calendar_session_id}
        distinct_facets = {r.facet_key for r in eligible if r.facet_key}
        first_tick = eligible[0].timeline_tick if eligible else None
        latest_tick = eligible[-1].timeline_tick if eligible else None

        # 8. Assemble immutable domain projection DTO
        return PersonalGrowthState(
            character_id=character_id,
            domain_key=domain_key,
            exposure_state=exposure_state,
            experience_level=experience_level,
            familiarity_level=familiarity_level,
            curiosity_state=curiosity_state,
            distinct_session_count=len(distinct_sessions),
            total_experience_count=len(eligible),
            distinct_facet_count_experienced=len(distinct_facets),
            first_experience_tick=first_tick,
            latest_experience_tick=latest_tick,
        )

    async def get_lifecycle_stage(
        self,
        character_id: str,
        domain_key: str,
        curiosity_evidence_chain: Sequence[CuriosityEvidence] = (),
    ) -> LifecycleStage:
        """Evaluate growth state and return the derived orchestration LifecycleStage."""
        growth_state = await self.evaluate_growth_state(
            character_id=character_id,
            domain_key=domain_key,
            curiosity_evidence_chain=curiosity_evidence_chain,
        )
        return derive_lifecycle_stage(growth_state)
