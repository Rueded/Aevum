"""Retrospective Timeline Orchestration Coordinator for Phase 8B.5 (Step C3).

Coordinates per-turn temporal constraint gating, candidate trajectory evaluation,
trajectory plurality preservation, and canonical temporal conflict signal delegation.

Constitutional Locks & Invariants (Phase 8B.5 Architecture Gate v0.2):
1. Lock 1 (Trajectory Incompatibility != Candidate Incompatibility):
   A candidate hypothesis is excluded ONLY when ALL applicable trajectories
   are HARD_INCOMPATIBLE. If even one trajectory is COMPATIBLE, ADVISORY_ANOMALY,
   or UNDETERMINED, the candidate remains eligible for Step E.
2. Lock 2 (C3 Has Zero Repair-Policy Authority):
   C3 is a signal/evidence producer only. suggested_repair_level is strictly
   forbidden. RealityRepairService independently selects the repair level.
3. Lock 3 (Singular Repair Authority):
   Zero second repair engine. Delegates canonical temporal conflicts directly
   to existing RealityRepairService.repair() via timeline_evidence.
4. Lock 4 (Explicit Availability Semantics):
   evaluation_status is strictly AVAILABLE or UNAVAILABLE.
   NOT EVALUATED != NO CONFLICT. On failure, status is UNAVAILABLE:
   zero false candidate exclusions, zero conflict signals emitted.
5. Lock 5 (Serialization-Only Context Presentation):
   ContextBuilder performs zero temporal reasoning and zero winner selection.
6. Lock 6 (Constraint Gate, Not Competition Engine):
   C3 provides binary candidate eligibility only. Zero candidate scoring,
   zero candidate ranking, zero margin manipulation.
7. Lock 7 (Structured timeline_evidence Adapter):
   timeline_evidence passed to RealityRepairService conforms to an explicit,
   structurally constrained adapter (TimelineEvidenceAdapter).
8. Lock 8 (Symmetric Conflict Facts Without Tuple Index [0] Priority):
   conflicting_fact_keys is symmetric; tuple ordering MUST NOT designate
   which fact is erroneous or the repair target.
9. Zero Mutation Authority:
   Ephemeral in-memory reasoning only. Zero set_fact(), zero tokens,
   zero DB persistence, zero network, zero LLM, zero pseudo-probability.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import enum
import logging
from typing import Any, Optional, Sequence, Union, TYPE_CHECKING
import uuid

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from app.character.core_models import CharacterCore

from app.reality.candidate_models import CandidateHypothesis
from app.reality.models import FactAuthority, FactSource
from app.reality.temporal_models import (
    MAX_PROJECTED_NODES,
    MAX_TEMPORAL_PROPAGATION_HOPS,
    Canonicality,
    EpistemicGrounding,
    LifeStage,
    TemporalGranularity,
    TemporalHorizon,
    TemporalInterval,
)
from app.reality.temporal_rules import (
    TemporalRuleItem,
    TemporalRuleRegistry,
)
from app.reality.temporal_graph import (
    ConstraintEvaluationResult,
    ConstraintStatus,
    TemporalConstraintEvaluator,
    TemporalConstraintGraph,
    TemporalEdge,
    TemporalNode,
    TemporalRelationType,
)
from app.reality.trajectory_engine import (
    CANONICAL_HIGHER_ED_PATHWAYS,
    LifeTrajectory,
    TimelineTrajectoryEngine,
    TrajectoryPluralityResult,
    TrajectoryStatus,
)

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# =============================================================================
# Categorical Enums & Domain Models
# =============================================================================

class TemporalEvaluationStatus(str, enum.Enum):
    """Categorical evaluation status enforcing NOT EVALUATED != NO CONFLICT (Lock 4)."""

    AVAILABLE = "AVAILABLE"        # Temporal evaluation succeeded normally
    UNAVAILABLE = "UNAVAILABLE"    # Evaluation failed or could not run; graceful degradation


class TimelineEvidenceAdapter(BaseModel):
    """Structured adapter model conforming to the Phase 7 RealityRepairService timeline_evidence contract (Lock 7).

    Hard Invariant:
    Every field passed into RealityRepairService.timeline_evidence has an explicitly defined
    semantic contract with documented meanings and sources. No free-form unstructured dicts.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    independent_timeline_supported: bool = Field(
        ...,
        description="Whether existing timeline facts independently support reconciling past vs present states.",
    )
    temporal_split: Optional[dict[str, Any]] = Field(
        default=None,
        description="Structured assignments separating past and present states.",
    )
    conflicting_node_ids: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Identifiers of temporal nodes participating in the conflict.",
    )
    evidence_fact_keys: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Canonical core fact keys grounding the conflicting nodes.",
    )
    explanation: str = Field(
        default="",
        description="Deterministic explanation of the temporal conflict and reconciliation basis.",
    )

    def to_repair_evidence_dict(self) -> dict[str, Any]:
        """Convert adapter to the exact dictionary schema consumed by RealityRepairService."""
        data: dict[str, Any] = {
            "independent_timeline_supported": self.independent_timeline_supported,
            "temporal_split": self.temporal_split,
            "conflicting_node_ids": list(self.conflicting_node_ids),
            "evidence_fact_keys": list(self.evidence_fact_keys),
            "explanation": self.explanation,
        }
        if self.temporal_split:
            if "past" in self.temporal_split:
                data["past"] = self.temporal_split["past"]
            if "present" in self.temporal_split:
                data["present"] = self.temporal_split["present"]
        return data


class TemporalConflictSignal(BaseModel):
    """Structured signal emitted when a canonical temporal contradiction is detected (Lock 2 & Lock 8).

    Constitutional Locks:
    - Lock 2: C3 is a signal/evidence producer only. It has zero repair-policy authority.
      'suggested_repair_level' is strictly forbidden.
    - Lock 8: No implicit repair target by tuple ordering ([0]). Conflicting facts are
      symmetric; C3 does not designate one as erroneous.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    conflict_id: str = Field(..., description="Deterministic conflict signal identifier")
    conflicting_fact_keys: tuple[str, ...] = Field(
        ...,
        description="Symmetric tuple of participating canonical fact keys (no ordering precedence)",
    )
    temporal_evidence: TimelineEvidenceAdapter = Field(
        ...,
        description="Validated structured temporal evidence adapter (Lock 7)",
    )
    rationale: str = Field(
        default="",
        description="Audit rationale explaining the temporal constraint violation",
    )
    created_at: datetime = Field(
        default_factory=_utc_now,
        description="UTC creation timestamp",
    )


class TimelineOrchestrationResult(BaseModel):
    """Result of Step C3 timeline orchestration turn evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_status: TemporalEvaluationStatus = Field(
        default=TemporalEvaluationStatus.AVAILABLE,
        description="Whether temporal evaluation was executed or degraded to UNAVAILABLE (Lock 4)",
    )
    temporally_incompatible_candidate_ids: tuple[str, ...] = Field(
        default_factory=tuple,
        description="IDs of candidate hypotheses where ALL applicable trajectories are HARD_INCOMPATIBLE (Lock 1)",
    )
    candidate_evaluations: dict[str, tuple[str, ...]] = Field(
        default_factory=dict,
        description="Map of candidate_id to tuple of trajectory statuses for auditability",
    )
    trajectory_plurality: Optional[TrajectoryPluralityResult] = Field(
        default=None,
        description="Synthesized trajectory plurality result for the character",
    )
    canonical_conflict_signal: Optional[TemporalConflictSignal] = Field(
        default=None,
        description="Canonical temporal contradiction signal if detected among core facts",
    )
    evaluation_error: Optional[str] = Field(
        default=None,
        description="Error details if degraded to UNAVAILABLE",
    )
    created_at: datetime = Field(
        default_factory=_utc_now,
        description="UTC creation timestamp",
    )

    def is_candidate_eligible(self, candidate_id: str) -> bool:
        """Lock 1 check: True if candidate is not in temporally_incompatible_candidate_ids."""
        return candidate_id not in self.temporally_incompatible_candidate_ids


# =============================================================================
# Retrospective Timeline Orchestration Coordinator
# =============================================================================

class TimelineOrchestrationCoordinator:
    """Coordinator for Step C3 (Retrospective Timeline Orchestration & Conflict Delegation).

    Owns the evaluation of temporal constraints across active candidate hypotheses
    and canonical core reality facts without mutating state.
    """

    def coordinate_turn(
        self,
        core: Optional[CharacterCore] = None,
        active_candidates: Sequence[CandidateHypothesis] = (),
        target_institution_ref: Optional[str] = None,
        current_turn_date: Optional[date] = None,
        candidate_evaluations_override: Optional[
            dict[str, Sequence[Union[TrajectoryStatus, ConstraintStatus, str]]]
        ] = None,
    ) -> TimelineOrchestrationResult:
        """Execute Step C3 temporal orchestration for the current conversation turn.

        Constitutional Guarantees:
        1. Graceful degradation: Catches any unexpected failure and returns
           evaluation_status=UNAVAILABLE with ZERO candidate exclusions (Lock 4).
        2. Candidate exclusion occurs ONLY when ALL applicable trajectories
           for that candidate are HARD_INCOMPATIBLE (Lock 1).
        3. Canonical conflicts produce a TemporalConflictSignal without choosing
           a repair level (Lock 2) and with symmetric fact keys (Lock 8).
        4. Zero scoring, zero ranking, zero candidate promotion, zero DB writes (Lock 6 & 9).
        """
        try:
            # 1. Extract baseline temporal nodes from canonical core facts
            base_nodes = self.extract_base_temporal_nodes(core)

            # 2. Evaluate canonical reality for internal temporal conflicts
            canonical_signal = self._detect_canonical_temporal_conflict(base_nodes, core)

            # 3. Synthesize trajectory plurality for the character
            known_pathway = self._resolve_known_pathway(core, base_nodes)
            trajectory_plurality = TimelineTrajectoryEngine.generate_trajectories(
                base_nodes=base_nodes,
                known_pathway=known_pathway,
                target_institution_ref=target_institution_ref,
            )

            # 4. Evaluate active candidates against temporal constraints
            incompatible_cids, candidate_evals = self._evaluate_active_candidates(
                active_candidates=active_candidates,
                base_nodes=base_nodes,
                plurality=trajectory_plurality,
                evaluations_override=candidate_evaluations_override,
            )

            return TimelineOrchestrationResult(
                evaluation_status=TemporalEvaluationStatus.AVAILABLE,
                temporally_incompatible_candidate_ids=tuple(sorted(incompatible_cids)),
                candidate_evaluations=candidate_evals,
                trajectory_plurality=trajectory_plurality,
                canonical_conflict_signal=canonical_signal,
                evaluation_error=None,
                created_at=_utc_now(),
            )

        except Exception as exc:
            logger.error(
                "Timeline orchestration encountered unexpected error: %s. "
                "Degrading to UNAVAILABLE (zero candidate exclusions, no repair signal).",
                exc,
                exc_info=True,
            )
            return TimelineOrchestrationResult(
                evaluation_status=TemporalEvaluationStatus.UNAVAILABLE,
                temporally_incompatible_candidate_ids=(),
                candidate_evaluations={},
                trajectory_plurality=None,
                canonical_conflict_signal=None,
                evaluation_error=str(exc),
                created_at=_utc_now(),
            )

    # -------------------------------------------------------------------------
    # Node Extraction from Canonical Core Facts
    # -------------------------------------------------------------------------

    def extract_base_temporal_nodes(
        self,
        core: Optional[CharacterCore],
    ) -> list[TemporalNode]:
        """Extract deterministic TemporalNode representations from CharacterCore facts."""
        if core is None or not core.facts:
            return []

        nodes: list[TemporalNode] = []

        # 1. Birth Node
        birth_fact = core.get_fact("identity.birth_date") or core.get_fact("biography.birth_date")
        birth_year_fact = core.get_fact("identity.birth_year")
        age_fact = core.get_fact("identity.age")

        if birth_fact and birth_fact.value:
            b_interval = self._parse_interval(birth_fact.value)
            grounding, canon = self._resolve_fact_epistemics(birth_fact)
            b_key = getattr(birth_fact, "key", None) or getattr(birth_fact, "fact_key", None) or "identity.birth_date"
            nodes.append(
                TemporalNode(
                    node_id="node_birth",
                    label="Birth",
                    stage=None,
                    interval=b_interval,
                    temporal_horizon=TemporalHorizon.PAST,
                    epistemic_grounding=grounding,
                    canonicality=canon,
                    origin_fact_key=b_key,
                )
            )
        elif birth_year_fact and birth_year_fact.value:
            try:
                b_yr = int(birth_year_fact.value)
                grounding, canon = self._resolve_fact_epistemics(birth_year_fact)
                by_key = getattr(birth_year_fact, "key", None) or getattr(birth_year_fact, "fact_key", None) or "identity.birth_year"
                nodes.append(
                    TemporalNode(
                        node_id="node_birth",
                        label="Birth",
                        stage=None,
                        interval=TemporalInterval.create_year(b_yr),
                        temporal_horizon=TemporalHorizon.PAST,
                        epistemic_grounding=grounding,
                        canonicality=canon,
                        origin_fact_key=by_key,
                    )
                )
            except (ValueError, TypeError):
                pass
        elif age_fact and age_fact.value:
            try:
                age_val = int(age_fact.value)
                approx_birth_year = 2025 - age_val
                nodes.append(
                    TemporalNode(
                        node_id="node_birth",
                        label="Birth (Approximate from Age)",
                        stage=None,
                        interval=TemporalInterval.create_approximate_year(approx_birth_year),
                        temporal_horizon=TemporalHorizon.PAST,
                        epistemic_grounding=EpistemicGrounding.DERIVED,
                        canonicality=Canonicality.NON_CANONICAL,
                        origin_fact_key="identity.age",
                    )
                )
            except (ValueError, TypeError):
                pass

        # 2. Secondary Education / SPM Node
        spm_fact = core.get_fact("education.spm_year") or core.get_fact("education.spm_date")
        sec_school_fact = core.get_fact("education.secondary_school")

        if spm_fact and spm_fact.value:
            spm_interval = self._parse_interval(spm_fact.value)
            grounding, canon = self._resolve_fact_epistemics(spm_fact)
            nodes.append(
                TemporalNode(
                    node_id="node_spm",
                    label="SPM Examination",
                    stage=LifeStage.SECONDARY_EDUCATION,
                    interval=spm_interval,
                    temporal_horizon=TemporalHorizon.PAST,
                    epistemic_grounding=grounding,
                    canonicality=canon,
                    origin_fact_key="education.spm_year",
                )
            )
        elif sec_school_fact and sec_school_fact.value:
            grounding, canon = self._resolve_fact_epistemics(sec_school_fact)
            nodes.append(
                TemporalNode(
                    node_id="node_secondary_school",
                    label=str(sec_school_fact.value),
                    stage=LifeStage.SECONDARY_EDUCATION,
                    interval=TemporalInterval.create_unknown(),
                    temporal_horizon=TemporalHorizon.PAST,
                    epistemic_grounding=grounding,
                    canonicality=canon,
                    origin_fact_key="education.secondary_school",
                )
            )

        # 3. Pre-University Node (if explicitly recorded)
        preu_fact = (
            core.get_fact("education.stpm_year")
            or core.get_fact("education.matrikulasi_year")
            or core.get_fact("education.foundation_year")
            or core.get_fact("education.diploma_year")
            or core.get_fact("education.pre_u")
        )
        if preu_fact and preu_fact.value:
            p_key = getattr(preu_fact, "key", None) or getattr(preu_fact, "fact_key", None) or "education.pre_u"
            p_interval = self._parse_interval(preu_fact.value)
            grounding, canon = self._resolve_fact_epistemics(preu_fact)
            p_stage = (
                LifeStage.DIPLOMA
                if "diploma" in p_key.lower()
                else LifeStage.PRE_UNIVERSITY
            )
            nodes.append(
                TemporalNode(
                    node_id="node_pre_u",
                    label=f"Pre-University Studies ({p_key})",
                    stage=p_stage,
                    interval=p_interval,
                    temporal_horizon=TemporalHorizon.PAST,
                    epistemic_grounding=grounding,
                    canonicality=canon,
                    origin_fact_key=p_key,
                )
            )

        # 4. Undergraduate / Degree Node
        ug_fact = (
            core.get_fact("education.undergraduate_intake")
            or core.get_fact("education.degree_intake")
            or core.get_fact("education.university_intake")
        )
        uni_fact = core.get_fact("education.university")

        if ug_fact and ug_fact.value:
            ug_key = getattr(ug_fact, "key", None) or getattr(ug_fact, "fact_key", None) or "education.undergraduate_intake"
            ug_interval = self._parse_interval(ug_fact.value)
            grounding, canon = self._resolve_fact_epistemics(ug_fact)
            uni_ref = str(uni_fact.value) if uni_fact and uni_fact.value else None
            nodes.append(
                TemporalNode(
                    node_id="node_undergrad",
                    label="Undergraduate Studies",
                    stage=LifeStage.UNDERGRADUATE,
                    interval=ug_interval,
                    temporal_horizon=TemporalHorizon.PRESENT,
                    epistemic_grounding=grounding,
                    canonicality=canon,
                    institution_ref=uni_ref,
                    origin_fact_key=ug_key,
                )
            )

        # Sort nodes deterministically by node_id
        return sorted(nodes, key=lambda n: n.node_id)

    # -------------------------------------------------------------------------
    # Canonical Temporal Conflict Detection (Lock 2, Lock 3, Lock 7, Lock 8)
    # -------------------------------------------------------------------------

    def _detect_canonical_temporal_conflict(
        self,
        base_nodes: Sequence[TemporalNode],
        core: Optional[CharacterCore],
    ) -> Optional[TemporalConflictSignal]:
        """Detect whether baseline canonical facts contain internal temporal contradictions."""
        if len(base_nodes) < 2:
            return None

        node_map = {n.node_id: n for n in base_nodes}
        birth_node = node_map.get("node_birth")
        spm_node = node_map.get("node_spm")
        ug_node = node_map.get("node_undergrad")
        preu_node = node_map.get("node_pre_u")

        # Conflict 1: Age sanity check (Birth vs SPM / Secondary)
        if birth_node and spm_node:
            b_start = birth_node.interval.earliest_start
            s_start = spm_node.interval.earliest_start
            if b_start and s_start:
                age_at_spm = (s_start - b_start).days / 365.25
                if age_at_spm < 15.0:  # SPM age rule: minimum 16/17 years
                    adapter = TimelineEvidenceAdapter(
                        independent_timeline_supported=False,
                        temporal_split=None,
                        conflicting_node_ids=(birth_node.node_id, spm_node.node_id),
                        evidence_fact_keys=(
                            birth_node.origin_fact_key or "identity.birth_date",
                            spm_node.origin_fact_key or "education.spm_year",
                        ),
                        explanation=(
                            f"SPM at age {age_at_spm:.1f} violates minimum age requirement "
                            f"(RULE_AGE_MIN_SPM). Chronological impossibility."
                        ),
                    )
                    return TemporalConflictSignal(
                        conflict_id=f"temp_conflict_{uuid.uuid4().hex[:8]}",
                        conflicting_fact_keys=(
                            birth_node.origin_fact_key or "identity.birth_date",
                            spm_node.origin_fact_key or "education.spm_year",
                        ),
                        temporal_evidence=adapter,
                        rationale="Canonical temporal conflict: SPM examination precedes permissible developmental age.",
                    )

        # Conflict 2: Secondary vs Undergraduate Precedence
        if spm_node and ug_node:
            s_end = spm_node.interval.latest_end
            u_start = ug_node.interval.earliest_start
            if s_end and u_start and u_start < s_end:
                # Chronological inversion: Undergraduate starts before SPM finishes
                # Check if independent timeline facts separate past vs present
                is_split_supported = (
                    spm_node.temporal_horizon == TemporalHorizon.PAST
                    and ug_node.temporal_horizon == TemporalHorizon.PRESENT
                )
                split_dict = (
                    {
                        "past": {
                            "fact_key": spm_node.origin_fact_key,
                            "interval": spm_node.interval.model_dump(mode="json"),
                        },
                        "present": {
                            "fact_key": ug_node.origin_fact_key,
                            "interval": ug_node.interval.model_dump(mode="json"),
                        },
                    }
                    if is_split_supported
                    else None
                )
                adapter = TimelineEvidenceAdapter(
                    independent_timeline_supported=is_split_supported,
                    temporal_split=split_dict,
                    conflicting_node_ids=(spm_node.node_id, ug_node.node_id),
                    evidence_fact_keys=(
                        spm_node.origin_fact_key or "education.spm_year",
                        ug_node.origin_fact_key or "education.undergraduate_intake",
                    ),
                    explanation=(
                        f"Undergraduate start ({u_start}) precedes SPM completion ({s_end}), "
                        f"violating RULE_PRECEDENCE_SECONDARY_TO_UNDERGRAD."
                    ),
                )
                return TemporalConflictSignal(
                    conflict_id=f"temp_conflict_{uuid.uuid4().hex[:8]}",
                    conflicting_fact_keys=(
                        spm_node.origin_fact_key or "education.spm_year",
                        ug_node.origin_fact_key or "education.undergraduate_intake",
                    ),
                    temporal_evidence=adapter,
                    rationale="Canonical temporal conflict: Undergraduate intake precedes secondary school completion.",
                )

        # Conflict 3: Pre-U vs Undergraduate Precedence
        if preu_node and ug_node:
            p_end = preu_node.interval.latest_end
            u_start = ug_node.interval.earliest_start
            if p_end and u_start and u_start < p_end:
                is_split_supported = (
                    preu_node.temporal_horizon == TemporalHorizon.PAST
                    and ug_node.temporal_horizon == TemporalHorizon.PRESENT
                )
                split_dict = (
                    {
                        "past": {
                            "fact_key": preu_node.origin_fact_key,
                            "interval": preu_node.interval.model_dump(mode="json"),
                        },
                        "present": {
                            "fact_key": ug_node.origin_fact_key,
                            "interval": ug_node.interval.model_dump(mode="json"),
                        },
                    }
                    if is_split_supported
                    else None
                )
                adapter = TimelineEvidenceAdapter(
                    independent_timeline_supported=is_split_supported,
                    temporal_split=split_dict,
                    conflicting_node_ids=(preu_node.node_id, ug_node.node_id),
                    evidence_fact_keys=(
                        preu_node.origin_fact_key or "education.pre_u",
                        ug_node.origin_fact_key or "education.undergraduate_intake",
                    ),
                    explanation=(
                        f"Undergraduate start ({u_start}) precedes pre-university completion ({p_end})."
                    ),
                )
                return TemporalConflictSignal(
                    conflict_id=f"temp_conflict_{uuid.uuid4().hex[:8]}",
                    conflicting_fact_keys=(
                        preu_node.origin_fact_key or "education.pre_u",
                        ug_node.origin_fact_key or "education.undergraduate_intake",
                    ),
                    temporal_evidence=adapter,
                    rationale="Canonical temporal conflict: Undergraduate intake overlaps uncompleted pre-university stage.",
                )

        return None

    # -------------------------------------------------------------------------
    # Candidate Temporal Evaluation (Lock 1 & Lock 6)
    # -------------------------------------------------------------------------

    def _evaluate_active_candidates(
        self,
        active_candidates: Sequence[CandidateHypothesis],
        base_nodes: Sequence[TemporalNode],
        plurality: TrajectoryPluralityResult,
        evaluations_override: Optional[
            dict[str, Sequence[Union[TrajectoryStatus, ConstraintStatus, str]]]
        ] = None,
    ) -> tuple[set[str], dict[str, tuple[str, ...]]]:
        """Evaluate each active candidate hypothesis under Lock 1.

        Lock 1 Invariant:
        Candidate exclusion occurs ONLY when ALL applicable trajectories
        for that candidate are HARD_INCOMPATIBLE.
        If even one trajectory is COMPATIBLE, ADVISORY_ANOMALY, or UNDETERMINED,
        the candidate remains eligible.
        """
        incompatible_candidate_ids: set[str] = set()
        candidate_evaluations: dict[str, tuple[str, ...]] = {}

        for cand in active_candidates:
            cid = cand.candidate_id

            # Check if test override is provided
            if evaluations_override and cid in evaluations_override:
                raw_statuses = evaluations_override[cid]
                norm_statuses: list[str] = []
                for s in raw_statuses:
                    if isinstance(s, enum.Enum):
                        norm_statuses.append(s.value)
                    else:
                        norm_statuses.append(str(s))

                candidate_evaluations[cid] = tuple(norm_statuses)

                # Lock 1 & Lock A (Zero Applicable Trajectories):
                # Candidate exclusion occurs ONLY when applicable_trajectory_count > 0 AND ALL are HARD_INCOMPATIBLE.
                # When applicable_count == 0, candidate remains strictly eligible.
                applicable_count = len(norm_statuses)
                if applicable_count > 0 and all(
                    s in (TrajectoryStatus.HARD_INCOMPATIBLE.value, ConstraintStatus.VIOLATED.value, "HARD_INCOMPATIBLE", "VIOLATED")
                    for s in norm_statuses
                ):
                    incompatible_candidate_ids.add(cid)
                continue

            # Standard evaluation based on candidate content
            statuses = self._evaluate_single_candidate(cand, base_nodes, plurality)
            str_statuses = tuple(s.value for s in statuses)
            candidate_evaluations[cid] = str_statuses

            # Lock 1 & Lock A (Zero Applicable Trajectories):
            # Candidate exclusion occurs ONLY when applicable_trajectory_count > 0 AND ALL are HARD_INCOMPATIBLE.
            # When applicable_count == 0, candidate remains strictly eligible.
            applicable_count = len(statuses)
            if applicable_count > 0 and all(s == TrajectoryStatus.HARD_INCOMPATIBLE for s in statuses):
                incompatible_candidate_ids.add(cid)

        return incompatible_candidate_ids, candidate_evaluations

    def _evaluate_single_candidate(
        self,
        cand: CandidateHypothesis,
        base_nodes: Sequence[TemporalNode],
        plurality: TrajectoryPluralityResult,
    ) -> tuple[TrajectoryStatus, ...]:
        """Determine trajectory statuses for a single candidate hypothesis."""
        slot = cand.slot_name.lower()
        val_str = str(cand.proposed_value).strip().upper()

        # Case A: Candidate proposes a specific educational pathway
        if slot in ("education.pathway", "biography.pathway") or val_str in CANONICAL_HIGHER_ED_PATHWAYS:
            pathway = val_str if val_str in CANONICAL_HIGHER_ED_PATHWAYS else str(cand.proposed_value).strip().upper()
            cand_plurality = TimelineTrajectoryEngine.generate_trajectories(
                base_nodes=base_nodes,
                known_pathway=pathway,
            )
            # Lock B: Preserve compatible trajectories even under bounded ambiguity
            if cand_plurality.trajectory_bound_exceeded or cand_plurality.total_compatible_count > 0:
                if cand_plurality.compatible_trajectories:
                    all_trajs = cand_plurality.compatible_trajectories + cand_plurality.incompatible_trajectories
                    return tuple(t.status for t in all_trajs)
                statuses = [TrajectoryStatus.COMPATIBLE] * cand_plurality.total_compatible_count
                for incomp in cand_plurality.incompatible_trajectories:
                    statuses.append(incomp.status)
                return tuple(statuses)

            all_trajs = cand_plurality.compatible_trajectories + cand_plurality.incompatible_trajectories
            if not all_trajs:
                return (TrajectoryStatus.COMPATIBLE,)
            return tuple(t.status for t in all_trajs)

        # Case B: Candidate proposes a temporal year/date for SPM or secondary
        if "spm" in slot or "secondary" in slot:
            parsed_interval = self._parse_interval(cand.proposed_value)
            ug_node = next((n for n in base_nodes if n.stage == LifeStage.UNDERGRADUATE), None)
            if ug_node and ug_node.interval.earliest_start and parsed_interval.latest_end:
                if ug_node.interval.earliest_start < parsed_interval.latest_end:
                    # SPM proposed after undergraduate start -> HARD_INCOMPATIBLE across all trajectories
                    return (TrajectoryStatus.HARD_INCOMPATIBLE,)

        # Case C: Candidate proposes undergraduate intake
        if "undergrad" in slot or "degree_intake" in slot or "university_intake" in slot:
            parsed_interval = self._parse_interval(cand.proposed_value)
            spm_node = next((n for n in base_nodes if n.stage == LifeStage.SECONDARY_EDUCATION), None)
            if spm_node and spm_node.interval.latest_end and parsed_interval.earliest_start:
                if parsed_interval.earliest_start < spm_node.interval.latest_end:
                    # UG intake proposed before SPM completion -> HARD_INCOMPATIBLE across all trajectories
                    return (TrajectoryStatus.HARD_INCOMPATIBLE,)

        # Default for non-temporal candidate or candidates consistent with current plurality:
        # Lock B: When trajectory_bound_exceeded is True, compatible_trajectories is ()
        # by bounded ambiguity design, but total_compatible_count > 0. C3 MUST NOT treat this
        # as 0 trajectories or evaluate it as all HARD_INCOMPATIBLE.
        if plurality.trajectory_bound_exceeded or plurality.total_compatible_count > 0:
            if plurality.compatible_trajectories:
                all_trajs = plurality.compatible_trajectories + plurality.incompatible_trajectories
                return tuple(t.status for t in all_trajs)
            # Bound exceeded: compatible_trajectories is (), but total_compatible_count > 0.
            statuses_list: list[TrajectoryStatus] = [TrajectoryStatus.COMPATIBLE] * plurality.total_compatible_count
            for incomp in plurality.incompatible_trajectories:
                statuses_list.append(incomp.status)
            return tuple(statuses_list)

        if plurality.incompatible_trajectories:
            return tuple(t.status for t in plurality.incompatible_trajectories)

        return (TrajectoryStatus.COMPATIBLE,)

    # -------------------------------------------------------------------------
    # Helper Utilities
    # -------------------------------------------------------------------------

    def _resolve_known_pathway(
        self,
        core: Optional[CharacterCore],
        base_nodes: Sequence[TemporalNode],
    ) -> Optional[str]:
        """Resolve authoritative known pathway from core facts or base nodes."""
        if core is not None and core.facts:
            p_fact = core.get_fact("education.pathway") or core.get_fact("biography.pathway")
            if p_fact and p_fact.value:
                return str(p_fact.value).strip().upper()

        for bn in base_nodes:
            if bn.pathway:
                return bn.pathway.strip().upper()
        return None

    def _resolve_fact_epistemics(
        self,
        fact: Any,
    ) -> tuple[EpistemicGrounding, Canonicality]:
        """Resolve valid (EpistemicGrounding, Canonicality) pair for a core fact."""
        auth = getattr(fact, "authority", FactAuthority.AEVUM_CANONICAL)
        src = getattr(fact, "source", FactSource.SYSTEM_BASELINE)

        if auth in (FactAuthority.USER_LOCKED, FactAuthority.USER_CONFIGURED):
            return EpistemicGrounding.USER_CONFIRMED, Canonicality.CANONICAL

        if src in (FactSource.USER_CONFIGURED, FactSource.SYSTEM_BASELINE, FactSource.CONVERSATION):
            return EpistemicGrounding.USER_CONFIRMED, Canonicality.CANONICAL

        # Any derived or inferred fact must carry NON_CANONICAL
        return EpistemicGrounding.DERIVED, Canonicality.NON_CANONICAL

    def _parse_interval(self, val: Any) -> TemporalInterval:
        """Parse value into a valid TemporalInterval without synthetic exact precision."""
        if isinstance(val, TemporalInterval):
            return val

        if isinstance(val, dict):
            try:
                return TemporalInterval(**val)
            except Exception:
                pass

        if isinstance(val, int):
            if 1900 <= val <= 2100:
                return TemporalInterval.create_year(val)
            return TemporalInterval.create_unknown()

        if isinstance(val, date):
            return TemporalInterval.create_exact(start=val)

        if isinstance(val, str):
            val_clean = val.strip()
            # YYYY-MM-DD
            if len(val_clean) == 10 and val_clean[4] == "-" and val_clean[7] == "-":
                try:
                    return TemporalInterval.create_exact(start=date.fromisoformat(val_clean))
                except ValueError:
                    pass
            # YYYY-MM
            elif len(val_clean) == 7 and val_clean[4] == "-":
                try:
                    parts = val_clean.split("-")
                    return TemporalInterval.create_month(year=int(parts[0]), month=int(parts[1]))
                except (ValueError, IndexError):
                    pass
            # YYYY
            elif len(val_clean) == 4 and val_clean.isdigit():
                return TemporalInterval.create_year(int(val_clean))

        return TemporalInterval.create_unknown()
