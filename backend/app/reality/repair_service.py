"""Service implementing Minimal Reality Repair (Phase 7D.3).

Evaluates the 5-level deterministic repair hierarchy:
Level 1: SOCIAL_MISSPEAK
Level 2: TEMPORAL_REINTERPRETATION
Level 3: FACT_INVALIDATION
Level 4: RE_ANCHORING
Level 5: GRACEFUL_UNCERTAINTY

Hard Invariants:
- Evaluates lowest-cost repair first: Level 1 -> Level 2 -> Level 3 -> Level 4 -> Level 5.
- Zero compensatory biography invention (compensatory_biography_created is strictly FALSE).
- Zero direct mutation of canonical reality (canonical_mutated is strictly FALSE).
- Level 4 re-anchoring is an EPHEMERAL_REPAIR_INTERPRETATION for current reasoning turn only.
- Unsupported contradictions retain explicit uncertainty without fake bridges.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Optional

from app.reality.repair_models import RealityRepairResult, RepairLevel

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RealityRepairService:
    """Evaluates and resolves epistemic tensions and factual conflicts through the 5-level hierarchy."""

    @classmethod
    def repair(
        cls,
        conflict_type: Optional[str] = None,
        *,
        claim_key: Optional[str] = None,
        claimed_value: Any = None,
        existing_value: Any = None,
        is_social_misspeak: bool = False,
        social_explanation: Optional[str] = None,
        timeline_evidence: Optional[dict[str, Any]] = None,
        unconfirmed_candidate_id: Optional[str] = None,
        entity_disambiguation: Optional[dict[str, Any]] = None,
        compensatory_biography_requested: bool = False,
        rationale: str = "",
    ) -> RealityRepairResult:
        """Resolve contradiction adhering strictly to the 5-level repair hierarchy.

        Evaluates lowest-cost repair first:
        1. LEVEL 1 (Social Misspeak): Conversational acknowledgment without world lore mutation.
        2. LEVEL 2 (Temporal Reinterpretation): Reconciles past vs present ONLY if independently supported.
        3. LEVEL 3 (Fact Invalidation): Invalidates unconfirmed candidate or weaker claim.
        4. LEVEL 4 (Re-Anchoring): Disambiguates entity in ephemeral reasoning context for current turn.
        5. LEVEL 5 (Graceful Uncertainty): Retains explicit uncertainty; strictly rejects fake bridges.
        """
        # Guard: Rejection of compensatory biography attempts
        if compensatory_biography_requested:
            logger.warning(
                "Rejected attempt to invent compensatory biography for conflict on '%s'. "
                "Falling through to GRACEFUL_UNCERTAINTY.",
                claim_key,
            )
            return cls.resolve_graceful_uncertainty(
                reasons=[
                    "Contradiction cannot be resolved without inventing compensatory biography (strictly prohibited).",
                ],
                rationale="Compensatory biography invention rejected; retaining graceful uncertainty.",
            )

        # ---------------------------------------------------------------------
        # LEVEL 1: Social Misspeak / Verbal Slip / Pop-Culture Error
        # ---------------------------------------------------------------------
        if is_social_misspeak or conflict_type in (
            "SOCIAL_MISSPEAK",
            "POP_CULTURE_SLIP",
            "VERBAL_SLIP",
            RepairLevel.LEVEL_1_SOCIAL_MISSPEAK.value,
        ):
            return cls.resolve_social_misspeak(
                description=social_explanation or "Conversational slip or pop-culture attribution error resolved socially.",
                suggested_guidance=social_explanation or "Acknowledge slip conversationally without mutating canonical lore.",
                rationale=rationale or "Resolved at Level 1 via conversational social correction without fact mutation.",
            )

        # ---------------------------------------------------------------------
        # LEVEL 2: Temporal Reinterpretation (past vs present)
        # Invariant: Allowed ONLY when independently supported by existing timeline facts.
        # ---------------------------------------------------------------------
        if timeline_evidence is not None and timeline_evidence.get("independent_timeline_supported") is True:
            split_data = timeline_evidence.get("temporal_split") or {
                "past": timeline_evidence.get("past"),
                "present": timeline_evidence.get("present"),
            }
            return cls.resolve_temporal_reinterpretation(
                temporal_split=split_data,
                rationale=rationale or "Resolved at Level 2 via independent timeline facts separating past and present states.",
            )

        # ---------------------------------------------------------------------
        # LEVEL 3: Fact Invalidation (unconfirmed candidate rejected)
        # ---------------------------------------------------------------------
        if unconfirmed_candidate_id or conflict_type in (
            "FACT_INVALIDATION",
            RepairLevel.LEVEL_3_FACT_INVALIDATION.value,
        ):
            c_ids = (unconfirmed_candidate_id,) if unconfirmed_candidate_id else tuple()
            return cls.resolve_fact_invalidation(
                invalidated_claim_ids=c_ids,
                rationale=rationale or "Resolved at Level 3 by invalidating unconfirmed candidate hypothesis.",
            )

        # ---------------------------------------------------------------------
        # LEVEL 4: Re-Anchoring (ephemeral entity disambiguation)
        # Invariant: Ephemeral reasoning context for current turn only; zero backstory fabrication.
        # ---------------------------------------------------------------------
        if entity_disambiguation is not None and entity_disambiguation.get("independent_evidence_supported") is True:
            return cls.resolve_reanchoring(
                ambiguous_name=entity_disambiguation.get("ambiguous_name", "entity"),
                reanchored_target=entity_disambiguation.get("reanchored_target", "distinct_entity"),
                rationale=rationale or "Resolved at Level 4 via ephemeral entity disambiguation for current turn.",
            )

        # ---------------------------------------------------------------------
        # LEVEL 5: Graceful Uncertainty (unsupported contradiction)
        # ---------------------------------------------------------------------
        return cls.resolve_graceful_uncertainty(
            reasons=[
                "Contradiction cannot be resolved via Levels 1–4 without independent evidence or compensatory biography.",
            ],
            rationale=rationale or "Retained explicit uncertainty at Level 5 without fabricating reality bridges.",
        )

    # =========================================================================
    # Level-Specific Structured Builders
    # =========================================================================

    @classmethod
    def resolve_social_misspeak(
        cls,
        description: str,
        suggested_guidance: Optional[str] = None,
        rationale: str = "Resolved at Level 1 via social misspeak correction.",
    ) -> RealityRepairResult:
        """Resolve contradiction at Level 1 (Social Misspeak)."""
        return RealityRepairResult(
            repair_level=RepairLevel.LEVEL_1_SOCIAL_MISSPEAK,
            is_repaired=True,
            repair_action="SOCIAL_MISSPEAK_RESOLVED",
            social_guidance=suggested_guidance or description,
            compensatory_biography_created=False,
            canonical_mutated=False,
            rationale=rationale,
            created_at=_utc_now(),
        )

    @classmethod
    def resolve_temporal_reinterpretation(
        cls,
        temporal_split: dict[str, Any],
        rationale: str = "Resolved at Level 2 via temporal reinterpretation.",
    ) -> RealityRepairResult:
        """Resolve contradiction at Level 2 (Temporal Reinterpretation)."""
        return RealityRepairResult(
            repair_level=RepairLevel.LEVEL_2_TEMPORAL_REINTERPRETATION,
            is_repaired=True,
            repair_action="TEMPORAL_SPLIT_APPLIED",
            temporal_split=temporal_split,
            compensatory_biography_created=False,
            canonical_mutated=False,
            rationale=rationale,
            created_at=_utc_now(),
        )

    @classmethod
    def resolve_fact_invalidation(
        cls,
        invalidated_claim_ids: tuple[str, ...],
        rationale: str = "Resolved at Level 3 via fact invalidation.",
    ) -> RealityRepairResult:
        """Resolve contradiction at Level 3 (Fact Invalidation)."""
        return RealityRepairResult(
            repair_level=RepairLevel.LEVEL_3_FACT_INVALIDATION,
            is_repaired=True,
            repair_action="FACT_INVALIDATED",
            invalidated_claim_ids=invalidated_claim_ids,
            compensatory_biography_created=False,
            canonical_mutated=False,
            rationale=rationale,
            created_at=_utc_now(),
        )

    @classmethod
    def resolve_reanchoring(
        cls,
        ambiguous_name: str,
        reanchored_target: str,
        rationale: str = "Resolved at Level 4 via ephemeral re-anchoring.",
    ) -> RealityRepairResult:
        """Resolve contradiction at Level 4 (Re-Anchoring)."""
        return RealityRepairResult(
            repair_level=RepairLevel.LEVEL_4_RE_ANCHORING,
            is_repaired=True,
            repair_action="ENTITY_RE_ANCHORED",
            reanchored_context={
                "ambiguous_entity": ambiguous_name,
                "reanchored_to": reanchored_target,
                "scope": "EPHEMERAL_REPAIR_INTERPRETATION",
            },
            compensatory_biography_created=False,
            canonical_mutated=False,
            rationale=rationale,
            created_at=_utc_now(),
        )

    @classmethod
    def resolve_graceful_uncertainty(
        cls,
        reasons: list[str],
        rationale: str = "Resolved at Level 5 via graceful uncertainty.",
    ) -> RealityRepairResult:
        """Resolve contradiction at Level 5 (Graceful Uncertainty)."""
        return RealityRepairResult(
            repair_level=RepairLevel.LEVEL_5_GRACEFUL_UNCERTAINTY,
            is_repaired=False,
            repair_action="GRACEFUL_UNCERTAINTY_EXPRESSED",
            unresolved_reasons=tuple(reasons),
            compensatory_biography_created=False,
            canonical_mutated=False,
            rationale=rationale,
            created_at=_utc_now(),
        )
