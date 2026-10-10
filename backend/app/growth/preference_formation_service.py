"""Phase 16.3 Preference Formation Service.

Provides three components:

1. PreferenceCompatibilityProjector (Blocker 6)
   Uni-directional adapter from Phase 16.3 PreferencePolarity163 to a Phase 16.2-compatible
   hint string. state_machine.py has ZERO import from any Phase 16.3 module.
   MIXED_AMBIVALENT → "MIXED" → PreferencePolarity.UNFORMED (never ATTRACTED).

2. PreferenceFormationService
   Queries character_facet_appraisals (source of truth), applies 5-case polarity conflict
   resolution (Blocker 3), applies epistemic inertia, and deterministically upserts
   character_preferences (materialized projection).
   Idempotency: same appraisal stream → same preference, regardless of call order (G49).

3. PreferenceAwareGrowthService
   Extends Phase 16.2 InterestDomainService via composition only.
   InterestDomainService.evaluate_growth_state() is called unchanged.
   Preference projection is layered on top via PreferenceCompatibilityProjector.

Constitutional Invariants:
- character_facet_appraisals is the source of truth (Req 7).
- character_preferences is a mutable materialized projection — NOT source of truth.
  It has NO ORM immutability events (unlike character_facet_appraisals).
- All consolidation is idempotent: same appraisal stream → same result (G49).
- state_machine.py is NOT imported or modified by this module.
- MIXED_AMBIVALENT never maps to ATTRACTED or POSITIVE in the 16.2 compatibility layer.
"""

from __future__ import annotations

import uuid
from typing import NamedTuple, Optional, Sequence

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.growth.appraisal_models import (
    CONSOLIDATED_APPRAISAL_THRESHOLD,
    CONSOLIDATED_DOMINANCE_PERCENTAGE,
    CONSOLIDATED_SESSION_THRESHOLD,
    INERTIA_REVISION_APPRAISAL_THRESHOLD,
    INERTIA_REVISION_SESSION_THRESHOLD,
    MIXED_APPRAISAL_THRESHOLD,
    MIXED_DOMINANCE_FLOOR_PERCENTAGE,
    MIXED_SESSION_THRESHOLD,
    STABILIZED_APPRAISAL_THRESHOLD,
    STABILIZED_DOMINANCE_PERCENTAGE,
    STABILIZED_SESSION_THRESHOLD,
    STRONG_INTENSITY_PERCENTAGE,
    TENTATIVE_APPRAISAL_THRESHOLD,
    TENTATIVE_DOMINANCE_PERCENTAGE,
    TENTATIVE_SESSION_THRESHOLD,
    CompositeDomainPreference,
    PersonalPreferenceRecord,
    PolarityBucket,
    PreferencePolarity163,
    PreferenceRevisionKind,
    StabilityTier,
    compute_composite_domain_preference,
    evaluate_consistency_threshold,
    map_appraisal_to_bucket,
    utc_now,
    validate_legal_polarity_stability_combo,
)
from app.growth.experiential_models import FacetAppraisalKind
from app.growth.growth_db_models import CharacterFacetAppraisalTable, CharacterPreferenceTable
from app.growth.interest_domain_service import InterestDomainService
from app.growth.state_machine import CuriosityEvidence, PersonalGrowthState, PreferencePolarity


# =============================================================================
# Internal Data Structure
# =============================================================================

class AppraisalDataPoint(NamedTuple):
    """Lightweight internal record for preference consolidation computation.

    Extracted from CharacterFacetAppraisalTable rows before computation.
    Allows testing _compute_preference_from_appraisals() without DB access.
    """
    appraisal_kind: FacetAppraisalKind
    calendar_session_id: str
    timeline_tick: int


# =============================================================================
# Phase 16.2 Compatibility Adapter (Blocker 6 — uni-directional)
# =============================================================================

class PreferenceCompatibilityProjector:
    """Uni-directional adapter from Phase 16.3 PreferencePolarity163 to Phase 16.2-compatible signals.

    Constitutional Constraints (Blocker 6):
    - This projector lives exclusively in Phase 16.3. state_machine.py does NOT import 16.3 types.
    - MIXED_AMBIVALENT → "MIXED" → PreferencePolarity.UNFORMED in 16.2 (never ATTRACTED).
    - The mapping is one-way only: 16.3 → 16.2 compatibility hint.
    - 16.2 lifecycle stage derivation must not interpret "MIXED" as a formed preference direction.
    """

    _POLARITY_PROJECTION_MAP: dict[str, Optional[str]] = {
        PreferencePolarity163.UNFORMED.value:           None,
        PreferencePolarity163.STRONGLY_PREFERRED.value: "POSITIVE",
        PreferencePolarity163.PREFERRED.value:          "POSITIVE",
        PreferencePolarity163.NEUTRAL.value:            "NEUTRAL",
        PreferencePolarity163.DISLIKED.value:           "NEGATIVE",
        PreferencePolarity163.AVOIDED.value:            "NEGATIVE",
        PreferencePolarity163.MIXED_AMBIVALENT.value:   "MIXED",   # NEVER maps to POSITIVE
    }

    _COMPOSITE_PROJECTION_MAP: dict[str, Optional[str]] = {
        CompositeDomainPreference.UNFORMED.value:          None,
        CompositeDomainPreference.COMPOSITE_POSITIVE.value: "POSITIVE",
        CompositeDomainPreference.COMPOSITE_NEGATIVE.value: "NEGATIVE",
        CompositeDomainPreference.COMPOSITE_NEUTRAL.value:  "NEUTRAL",
        CompositeDomainPreference.COMPOSITE_MIXED.value:    "MIXED",  # NEVER maps to POSITIVE
    }

    @staticmethod
    def project(polarity: PreferencePolarity163) -> Optional[str]:
        """Project a single facet PreferencePolarity163 to a 16.2-compatible hint."""
        return PreferenceCompatibilityProjector._POLARITY_PROJECTION_MAP[polarity.value]

    @staticmethod
    def project_composite(composite: CompositeDomainPreference) -> Optional[str]:
        """Project a CompositeDomainPreference to a 16.2-compatible hint."""
        return PreferenceCompatibilityProjector._COMPOSITE_PROJECTION_MAP[composite.value]


def _map_hint_to_162_polarity(hint: Optional[str]) -> PreferencePolarity:
    """Map a 16.2-compatible hint string to Phase 16.2's frozen PreferencePolarity (4-value).

    MIXED_AMBIVALENT → "MIXED" → PreferencePolarity.UNFORMED (never ATTRACTED).
    This function intentionally imports Phase 16.2's frozen enum.
    Phase 16.2's state_machine.py does NOT import any 16.3 type.
    """
    mapping: dict[Optional[str], PreferencePolarity] = {
        "POSITIVE": PreferencePolarity.ATTRACTED,
        "NEGATIVE": PreferencePolarity.AVERSIVE,
        "NEUTRAL":  PreferencePolarity.NEUTRAL,
        "MIXED":    PreferencePolarity.UNFORMED,   # MIXED_AMBIVALENT → UNFORMED, never ATTRACTED
        None:       PreferencePolarity.UNFORMED,
    }
    return mapping[hint]


# =============================================================================
# Pure Preference Computation (no I/O — testable without DB)
# =============================================================================

def _derive_polarity_and_stability(
    positive_count: int,
    neutral_count: int,
    negative_count: int,
    strongly_attracted_count: int,
    aversive_count: int,
    total_count: int,
    distinct_session_count: int,
) -> tuple[PreferencePolarity163, StabilityTier]:
    """Derive (PreferencePolarity163, StabilityTier) from bucket counts.

    5-Case Polarity Conflict Resolution (Blocker 3):
      Case A: POSITIVE + NEGATIVE both present → conflict detection → need 75% dominance
      Case B: POSITIVE + NEUTRAL only → positive may stabilize normally
      Case C: NEGATIVE + NEUTRAL only → negative may stabilize normally
      Case D: NEUTRAL dominant (≥60%) → PreferencePolarity163.NEUTRAL (real evidence)
      Case E: Three-way split / no bucket achieves 60% → MIXED_AMBIVALENT

    All threshold comparisons use integer arithmetic (Permanent Note A — Zero Floats).
    """
    # Not enough data for any formed preference
    if total_count < TENTATIVE_APPRAISAL_THRESHOLD or distinct_session_count < TENTATIVE_SESSION_THRESHOLD:
        return PreferencePolarity163.UNFORMED, StabilityTier.UNFORMED

    has_positive = positive_count > 0
    has_negative = negative_count > 0
    is_mixed_data_eligible = (
        total_count >= MIXED_APPRAISAL_THRESHOLD
        and distinct_session_count >= MIXED_SESSION_THRESHOLD
    )

    # Case A: POSITIVE + NEGATIVE conflict
    if has_positive and has_negative and is_mixed_data_eligible:
        pos_dominates = evaluate_consistency_threshold(
            positive_count, total_count, STABILIZED_DOMINANCE_PERCENTAGE
        )
        neg_dominates = evaluate_consistency_threshold(
            negative_count, total_count, STABILIZED_DOMINANCE_PERCENTAGE
        )
        if not pos_dominates and not neg_dominates:
            # Neither achieves 75% → MIXED_AMBIVALENT (always TENTATIVE per Blocker 4)
            return PreferencePolarity163.MIXED_AMBIVALENT, StabilityTier.TENTATIVE

    # Case E: Three-way split — check if dominant bucket fails 60% floor
    if is_mixed_data_eligible and not (has_positive and has_negative):
        dominant_count = max(positive_count, neutral_count, negative_count)
        if not evaluate_consistency_threshold(dominant_count, total_count, MIXED_DOMINANCE_FLOOR_PERCENTAGE):
            return PreferencePolarity163.MIXED_AMBIVALENT, StabilityTier.TENTATIVE

    # Identify dominant bucket
    if positive_count >= negative_count and positive_count >= neutral_count:
        dominant_count = positive_count
        dominant_bucket = PolarityBucket.POSITIVE
    elif negative_count > positive_count and negative_count >= neutral_count:
        dominant_count = negative_count
        dominant_bucket = PolarityBucket.NEGATIVE
    else:
        dominant_count = neutral_count
        dominant_bucket = PolarityBucket.NEUTRAL

    # Case D: NEUTRAL dominant
    if dominant_bucket == PolarityBucket.NEUTRAL:
        if evaluate_consistency_threshold(neutral_count, total_count, TENTATIVE_DOMINANCE_PERCENTAGE):
            stability = _derive_stability_from_counts(neutral_count, total_count, distinct_session_count)
            return PreferencePolarity163.NEUTRAL, stability
        # Neutral not dominant enough → UNFORMED
        return PreferencePolarity163.UNFORMED, StabilityTier.UNFORMED

    # Case B/C: POSITIVE or NEGATIVE dominant (with or without neutral)
    stability = _derive_stability_from_counts(dominant_count, total_count, distinct_session_count)

    if dominant_bucket == PolarityBucket.POSITIVE:
        # Check for STRONGLY_PREFERRED intensity
        if evaluate_consistency_threshold(strongly_attracted_count, total_count, STRONG_INTENSITY_PERCENTAGE):
            polarity = PreferencePolarity163.STRONGLY_PREFERRED
        else:
            polarity = PreferencePolarity163.PREFERRED
    else:  # NEGATIVE dominant
        # Check for AVOIDED intensity
        if evaluate_consistency_threshold(aversive_count, total_count, STRONG_INTENSITY_PERCENTAGE):
            polarity = PreferencePolarity163.AVOIDED
        else:
            polarity = PreferencePolarity163.DISLIKED

    return polarity, stability


def _derive_stability_from_counts(
    dominant_count: int,
    total_count: int,
    distinct_session_count: int,
) -> StabilityTier:
    """Derive StabilityTier from dominant bucket count and session breadth.

    Uses integer threshold math (Permanent Note A — Zero Floats):
      CONSOLIDATED: total >= 7, sessions >= 5, dominant >= 80%
      STABILIZED:   total >= 4, sessions >= 3, dominant >= 75%
      TENTATIVE:    total >= 2, sessions >= 2, dominant >= 60%
      UNFORMED:     insufficient data
    """
    if (
        total_count >= CONSOLIDATED_APPRAISAL_THRESHOLD
        and distinct_session_count >= CONSOLIDATED_SESSION_THRESHOLD
        and evaluate_consistency_threshold(dominant_count, total_count, CONSOLIDATED_DOMINANCE_PERCENTAGE)
    ):
        return StabilityTier.CONSOLIDATED
    if (
        total_count >= STABILIZED_APPRAISAL_THRESHOLD
        and distinct_session_count >= STABILIZED_SESSION_THRESHOLD
        and evaluate_consistency_threshold(dominant_count, total_count, STABILIZED_DOMINANCE_PERCENTAGE)
    ):
        return StabilityTier.STABILIZED
    if (
        total_count >= TENTATIVE_APPRAISAL_THRESHOLD
        and distinct_session_count >= TENTATIVE_SESSION_THRESHOLD
        and evaluate_consistency_threshold(dominant_count, total_count, TENTATIVE_DOMINANCE_PERCENTAGE)
    ):
        return StabilityTier.TENTATIVE
    return StabilityTier.UNFORMED


def _compute_preference_from_appraisals(
    appraisals: Sequence[AppraisalDataPoint],
    existing_preference: Optional[PersonalPreferenceRecord] = None,
) -> tuple[PreferencePolarity163, StabilityTier, PreferenceRevisionKind]:
    """Pure computation of (polarity, stability, revision_kind) from an appraisal stream.

    This function is idempotent: given the same set of AppraisalDataPoints (regardless
    of iteration order because it sorts by timeline_tick), it always returns the same result.

    Args:
        appraisals: Sequence of AppraisalDataPoint; must be sorted by timeline_tick ASC
                    (the caller is responsible for sorting, or this function sorts internally).
        existing_preference: Previous preference record for epistemic inertia application.

    Returns:
        (PreferencePolarity163, StabilityTier, PreferenceRevisionKind)
    """
    # Sort by timeline_tick ASC to ensure permutation-invariance (G49)
    sorted_appraisals = sorted(appraisals, key=lambda x: x.timeline_tick)

    if not sorted_appraisals:
        return PreferencePolarity163.UNFORMED, StabilityTier.UNFORMED, PreferenceRevisionKind.NONE

    # Compute bucket counts
    positive_count = 0
    neutral_count = 0
    negative_count = 0
    strongly_attracted_count = 0
    aversive_count = 0

    distinct_sessions: set[str] = set()

    for dp in sorted_appraisals:
        bucket = map_appraisal_to_bucket(dp.appraisal_kind)
        if bucket == PolarityBucket.POSITIVE:
            positive_count += 1
        elif bucket == PolarityBucket.NEUTRAL:
            neutral_count += 1
        else:
            negative_count += 1

        if dp.appraisal_kind == FacetAppraisalKind.STRONGLY_ATTRACTED:
            strongly_attracted_count += 1
        if dp.appraisal_kind == FacetAppraisalKind.AVERSIVE_DISLIKED:
            aversive_count += 1

        if dp.calendar_session_id:
            distinct_sessions.add(dp.calendar_session_id)

    total_count = len(sorted_appraisals)
    distinct_session_count = len(distinct_sessions)

    # Derive base polarity and stability
    polarity, stability = _derive_polarity_and_stability(
        positive_count=positive_count,
        neutral_count=neutral_count,
        negative_count=negative_count,
        strongly_attracted_count=strongly_attracted_count,
        aversive_count=aversive_count,
        total_count=total_count,
        distinct_session_count=distinct_session_count,
    )

    # Apply epistemic inertia for STABILIZED / CONSOLIDATED preferences
    revision_kind = PreferenceRevisionKind.NONE

    if existing_preference is not None and existing_preference.stability_tier in (
        StabilityTier.STABILIZED,
        StabilityTier.CONSOLIDATED,
    ):
        old_polarity = existing_preference.preference_polarity

        # Determine if new data is a counter-stream to the existing preference
        if old_polarity in (PreferencePolarity163.STRONGLY_PREFERRED, PreferencePolarity163.PREFERRED):
            old_bucket = PolarityBucket.POSITIVE
        elif old_polarity in (PreferencePolarity163.DISLIKED, PreferencePolarity163.AVOIDED):
            old_bucket = PolarityBucket.NEGATIVE
        elif old_polarity == PreferencePolarity163.NEUTRAL:
            old_bucket = PolarityBucket.NEUTRAL
        else:
            old_bucket = None  # UNFORMED / MIXED — no inertia

        if old_bucket is not None:
            # Count appraisals from sessions AFTER the last evaluated tick
            last_tick = existing_preference.last_evaluated_tick or 0
            new_appraisals = [dp for dp in sorted_appraisals if dp.timeline_tick > last_tick]

            if new_appraisals:
                new_counter_appraisals = [
                    dp for dp in new_appraisals
                    if map_appraisal_to_bucket(dp.appraisal_kind) != old_bucket
                ]
                new_counter_sessions = len({dp.calendar_session_id for dp in new_counter_appraisals})

                if (
                    len(new_counter_appraisals) >= INERTIA_REVISION_APPRAISAL_THRESHOLD
                    and new_counter_sessions >= INERTIA_REVISION_SESSION_THRESHOLD
                ):
                    # Sustained opposing evidence → trigger revision
                    revision_kind = PreferenceRevisionKind.REVISION_TRIGGERED
                    polarity = PreferencePolarity163.MIXED_AMBIVALENT
                    stability = StabilityTier.TENTATIVE  # MIXED_AMBIVALENT always TENTATIVE (Blocker 4)
                elif new_counter_appraisals:
                    # Single-session noise → COUNTER_EVIDENCE_ACCUMULATING, preserve polarity
                    revision_kind = PreferenceRevisionKind.COUNTER_EVIDENCE_ACCUMULATING
                    polarity = existing_preference.preference_polarity
                    stability = existing_preference.stability_tier

    # Validate legal combo (Blocker 4 invariant table)
    validate_legal_polarity_stability_combo(polarity, stability)

    return polarity, stability, revision_kind


# =============================================================================
# PreferenceFormationService (async, DB-backed)
# =============================================================================

class PreferenceFormationService:
    """Queries character_facet_appraisals (source of truth), applies longitudinal policy,
    and deterministically upserts character_preferences (materialized projection).

    Idempotency guarantee (Req 12 + G49):
      consolidate_facet_preference() always recomputes from the full appraisal stream.
      The same stream in any ingestion order produces identical PersonalPreferenceRecord.
    """

    async def consolidate_facet_preference(
        self,
        character_id: str,
        domain_key: str,
        facet_key: str,
        db_session: AsyncSession,
    ) -> PersonalPreferenceRecord:
        """Consolidate all appraisals for (character_id, domain_key, facet_key) into a preference.

        Steps:
        1. Query ALL character_facet_appraisals for the triple (full stream recomputation, Req 7).
        2. Extract AppraisalDataPoints.
        3. Load existing preference (for epistemic inertia).
        4. Call _compute_preference_from_appraisals() — pure, idempotent, permutation-invariant (G49).
        5. Upsert character_preferences (INSERT ... ON CONFLICT DO UPDATE — Req 12).
        6. Return PersonalPreferenceRecord.
        """
        # Step 1: Query full appraisal stream sorted by timeline_tick ASC
        stmt = (
            select(CharacterFacetAppraisalTable)
            .where(
                CharacterFacetAppraisalTable.character_id == character_id,
                CharacterFacetAppraisalTable.domain_key == domain_key,
                CharacterFacetAppraisalTable.facet_key == facet_key,
            )
            .order_by(CharacterFacetAppraisalTable.timeline_tick.asc())
        )
        result = await db_session.execute(stmt)
        appraisal_rows = result.scalars().all()

        # Step 2: Extract data points
        data_points = [
            AppraisalDataPoint(
                appraisal_kind=FacetAppraisalKind(row.appraisal_kind),
                calendar_session_id=row.calendar_session_id,
                timeline_tick=row.timeline_tick,
            )
            for row in appraisal_rows
        ]

        # Step 3: Load existing preference for inertia
        existing_pref_stmt = (
            select(CharacterPreferenceTable)
            .where(
                CharacterPreferenceTable.character_id == character_id,
                CharacterPreferenceTable.domain_key == domain_key,
                CharacterPreferenceTable.facet_key == facet_key,
            )
        )
        existing_pref_result = await db_session.execute(existing_pref_stmt)
        existing_pref_row = existing_pref_result.scalar_one_or_none()

        existing_pref: Optional[PersonalPreferenceRecord] = None
        if existing_pref_row is not None:
            existing_pref = PersonalPreferenceRecord(
                preference_id=existing_pref_row.id,
                character_id=existing_pref_row.character_id,
                domain_key=existing_pref_row.domain_key,
                facet_key=existing_pref_row.facet_key,
                preference_polarity=PreferencePolarity163(existing_pref_row.preference_polarity),
                stability_tier=StabilityTier(existing_pref_row.stability_tier),
                revision_kind=PreferenceRevisionKind(existing_pref_row.revision_kind),
                appraisal_count=existing_pref_row.appraisal_count,
                distinct_session_count=existing_pref_row.distinct_session_count,
                last_evaluated_tick=existing_pref_row.last_evaluated_tick,
                updated_at=existing_pref_row.updated_at,
            )

        # Step 4: Pure computation (permutation-invariant: sorted internally by timeline_tick)
        polarity, stability, revision_kind = _compute_preference_from_appraisals(
            data_points, existing_pref
        )

        # Step 5: Upsert character_preferences (idempotent: same stream → same row)
        now = utc_now()
        last_tick = max((dp.timeline_tick for dp in data_points), default=None)
        distinct_sessions_count = len({dp.calendar_session_id for dp in data_points if dp.calendar_session_id})

        if existing_pref_row is None:
            # INSERT new preference row
            pref_id = str(uuid.uuid4())
            new_row = CharacterPreferenceTable(
                id=pref_id,
                character_id=character_id,
                domain_key=domain_key,
                facet_key=facet_key,
                preference_polarity=polarity.value,
                stability_tier=stability.value,
                revision_kind=revision_kind.value,
                appraisal_count=len(data_points),
                distinct_session_count=distinct_sessions_count,
                last_evaluated_tick=last_tick,
                updated_at=now,
            )
            db_session.add(new_row)
            await db_session.flush()
        else:
            # UPDATE existing row (deterministic upsert — Req 12)
            pref_id = existing_pref_row.id
            existing_pref_row.preference_polarity = polarity.value
            existing_pref_row.stability_tier = stability.value
            existing_pref_row.revision_kind = revision_kind.value
            existing_pref_row.appraisal_count = len(data_points)
            existing_pref_row.distinct_session_count = distinct_sessions_count
            existing_pref_row.last_evaluated_tick = last_tick
            existing_pref_row.updated_at = now
            await db_session.flush()

        return PersonalPreferenceRecord(
            preference_id=pref_id,
            character_id=character_id,
            domain_key=domain_key,
            facet_key=facet_key,
            preference_polarity=polarity,
            stability_tier=stability,
            revision_kind=revision_kind,
            appraisal_count=len(data_points),
            distinct_session_count=distinct_sessions_count,
            last_evaluated_tick=last_tick,
            updated_at=now,
        )

    async def consolidate_domain_preferences(
        self,
        character_id: str,
        domain_key: str,
        db_session: AsyncSession,
    ) -> CompositeDomainPreference:
        """Consolidate all registered facets for a domain and return CompositeDomainPreference.

        Categorical composition: no scalar averaging (Req 9).
        """
        # Query all current preference rows for this domain
        stmt = (
            select(CharacterPreferenceTable)
            .where(
                CharacterPreferenceTable.character_id == character_id,
                CharacterPreferenceTable.domain_key == domain_key,
            )
        )
        result = await db_session.execute(stmt)
        pref_rows = result.scalars().all()

        if not pref_rows:
            return CompositeDomainPreference.UNFORMED

        facet_preferences = [
            PersonalPreferenceRecord(
                preference_id=row.id,
                character_id=row.character_id,
                domain_key=row.domain_key,
                facet_key=row.facet_key,
                preference_polarity=PreferencePolarity163(row.preference_polarity),
                stability_tier=StabilityTier(row.stability_tier),
                revision_kind=PreferenceRevisionKind(row.revision_kind),
                appraisal_count=row.appraisal_count,
                distinct_session_count=row.distinct_session_count,
                last_evaluated_tick=row.last_evaluated_tick,
                updated_at=row.updated_at,
            )
            for row in pref_rows
        ]

        return compute_composite_domain_preference(facet_preferences)

    async def rebuild_preferences_from_appraisal_stream(
        self,
        character_id: str,
        domain_key: str,
        db_session: AsyncSession,
    ) -> list[PersonalPreferenceRecord]:
        """Drop and rebuild all preferences for (character_id, domain_key) from appraisal stream.

        This proves that character_preferences is a rebuildable materialized projection (Req 7, G46).
        Does NOT modify character_facet_appraisals (source of truth is never touched).
        """
        # Delete all preference rows for this domain (NOT appraisals — those are immutable)
        delete_stmt = text(
            "DELETE FROM character_facet_preferences "
            "WHERE character_id = :character_id AND domain_key = :domain_key"
        )
        await db_session.execute(
            delete_stmt,
            {"character_id": character_id, "domain_key": domain_key},
        )
        await db_session.flush()

        # Find all distinct facet_keys with appraisals for this domain
        facets_stmt = (
            select(CharacterFacetAppraisalTable.facet_key)
            .where(
                CharacterFacetAppraisalTable.character_id == character_id,
                CharacterFacetAppraisalTable.domain_key == domain_key,
            )
            .distinct()
        )
        facets_result = await db_session.execute(facets_stmt)
        facet_keys = [row[0] for row in facets_result.all()]

        rebuilt: list[PersonalPreferenceRecord] = []
        for facet_key in facet_keys:
            record = await self.consolidate_facet_preference(
                character_id, domain_key, facet_key, db_session
            )
            rebuilt.append(record)

        return rebuilt


# =============================================================================
# PreferenceAwareGrowthService — Phase 16.2 composition extension (16.2 not modified)
# =============================================================================

class PreferenceAwareGrowthService:
    """Extends InterestDomainService with Phase 16.3 preference awareness via composition.

    InterestDomainService.evaluate_growth_state() is called unchanged.
    This service layers Phase 16.3 preference data on top of the 16.2 result via
    PreferenceCompatibilityProjector (one-way adapter, Blocker 6).

    Constitutional Invariants:
    - InterestDomainService is NOT modified.
    - state_machine.py has zero import from any Phase 16.3 module.
    - MIXED_AMBIVALENT → "MIXED" → PreferencePolarity.UNFORMED (never ATTRACTED).
    - LifecycleStage.PREFERENCE_FORMING / ESTABLISHED_TASTE are reachable from 16.2's
      derive_lifecycle_stage() only when polarity hint is "POSITIVE" or "NEGATIVE".
      "MIXED" hint → UNFORMED → lifecycle cannot advance to PREFERENCE_FORMING.
    """

    def __init__(
        self,
        domain_service: InterestDomainService,
        preference_service: PreferenceFormationService,
    ) -> None:
        self._domain = domain_service
        self._prefs = preference_service

    async def evaluate_growth_state(
        self,
        character_id: str,
        domain_key: str,
        curiosity_evidence_chain: Sequence[CuriosityEvidence] = (),
        db_session: Optional[AsyncSession] = None,
    ) -> PersonalGrowthState:
        """Evaluate growth state with Phase 16.3 preference projection.

        Steps:
        1. Get base Phase 16.2 PersonalGrowthState (unchanged 16.2 path).
        2. Get CompositeDomainPreference from Phase 16.3 (if db_session provided).
        3. Project composite → 16.2-compatible hint via PreferenceCompatibilityProjector.
        4. Map hint → Phase 16.2 PreferencePolarity (frozen 4-value).
        5. Return updated PersonalGrowthState with preference_polarity filled.
        """
        # Step 1: Base 16.2 state (unchanged)
        base_state = await self._domain.evaluate_growth_state(
            character_id=character_id,
            domain_key=domain_key,
            curiosity_evidence_chain=curiosity_evidence_chain,
        )

        if db_session is None:
            return base_state

        # Step 2: Phase 16.3 composite preference
        composite = await self._prefs.consolidate_domain_preferences(
            character_id, domain_key, db_session
        )

        # Step 3: Project to 16.2-compatible hint
        polarity_hint = PreferenceCompatibilityProjector.project_composite(composite)

        # Step 4: Map to Phase 16.2 frozen PreferencePolarity
        polarity_162 = _map_hint_to_162_polarity(polarity_hint)

        # Step 5: Return updated state (Pydantic model_copy for frozen model)
        return PersonalGrowthState(
            **{
                k: v
                for k, v in base_state.model_dump().items()
                if k != "preference_polarity"
            },
            preference_polarity=polarity_162,
        )
