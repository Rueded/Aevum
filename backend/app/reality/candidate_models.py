"""Candidate Reality domain models for Reality & Belief Engine (Phase 7B.3).

Tracks proposed reality facts, their systemic impact tiers, inference scopes,
and evidence accumulation history prior to canonical promotion.
"""

from datetime import datetime, timezone
import enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.reality.belief_models import FactSubject


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RealityImpact(str, enum.Enum):
    """Categorical systemic impact of adopting a fact into canonical reality."""

    LOW = "LOW"            # Daily lifestyle, study beverage, commute mode, weather taste
    MEDIUM = "MEDIUM"      # Casual friends, learning an instrument, club membership
    HIGH = "HIGH"          # University, academic major, siblings, parents' occupation, city of residence
    VERY_HIGH = "VERY_HIGH"# Major trauma, marriage/romantic history, fundamental core identity


class InferenceScope(str, enum.Enum):
    """Permissible reasoning distance from direct evidence (Anti-Snowballing Boundary)."""

    DIRECT = "DIRECT"          # Directly asserted or verified in immediate stimulus
    LOCAL = "LOCAL"            # One-hop plausible inference grounded in existing anchor
    DEPENDENT = "DEPENDENT"    # Formed by structural dependency (e.g. year from age & pre-u)
    SPECULATIVE = "SPECULATIVE"# Multi-hop ungrounded narrative assumption (CANNOT AUTO-PROMOTE)


class CandidateStatus(str, enum.Enum):
    """Lifecycle state of a candidate fact prior to canonical promotion."""

    PROPOSED = "PROPOSED"
    ACCUMULATING = "ACCUMULATING"
    ELIGIBLE_FOR_PROMOTION = "ELIGIBLE_FOR_PROMOTION"
    REJECTED = "REJECTED"


class CandidateFact(BaseModel):
    """Immutable domain representation of a candidate fact accumulating evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(..., description="Unique deterministic identifier for this candidate.")
    subject: FactSubject = Field(default=FactSubject.AEVUM, description="Attributed entity.")
    fact_key: str = Field(..., description="Dot-notated fact key, e.g. 'preferences.study_beverage'.")
    value: Any = Field(..., description="Proposed domain value.")
    impact: RealityImpact = Field(default=RealityImpact.LOW, description="Systemic reality impact tier.")
    inference_scope: InferenceScope = Field(default=InferenceScope.DIRECT, description="Reasoning hop distance.")
    status: CandidateStatus = Field(default=CandidateStatus.PROPOSED, description="Current lifecycle status.")
    evidence_count: int = Field(default=1, ge=1, description="Number of independent consistent evidence items.")
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple, description="IDs of supporting EvidenceRecords.")
    dependencies: tuple[str, ...] = Field(default_factory=tuple, description="Keys of prerequisite Core facts.")
    effective_from: Optional[str] = Field(default=None, description="Temporal effective start.")
    effective_until: Optional[str] = Field(default=None, description="Temporal effective end.")
    created_at: datetime = Field(default_factory=_utc_now, description="UTC creation timestamp.")
    updated_at: datetime = Field(default_factory=_utc_now, description="UTC update timestamp.")

    @field_validator("id", "fact_key")
    @classmethod
    def validate_non_empty(cls, v: str, info: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name} must not be empty or whitespace.")
        return v.strip()


# ============================================================================
# Phase 7D.1: Epistemic Candidate Models & Dual Reality Taxonomy
# ============================================================================


class RealityTaxonomy(str, enum.Enum):
    """Categorical boundary between physical world facts and simulated internal biography."""

    OBJECTIVE_WORLD_FACT = "OBJECTIVE_WORLD_FACT"        # Physical/external world (geography, game lore, weather)
    SIMULATED_BIOGRAPHY_FACT = "SIMULATED_BIOGRAPHY_FACT"# Internal life & narrative (major, hobbies, personal history)


class InferenceEdgeType(str, enum.Enum):
    """Formal taxonomy of reasoning dependencies connecting evidence to hypotheses."""

    DIRECT_ATTRIBUTE = "DIRECT_ATTRIBUTE"              # Direct observation or stated attribute
    STRUCTURAL_DEPENDENCY = "STRUCTURAL_DEPENDENCY"    # Institutional or physical rules (degree -> university)
    BEHAVIORAL_CORRELATE = "BEHAVIORAL_CORRELATE"      # Habitual or lifestyle associations (caffeine -> late study)
    TEMPORAL_DEPENDENCY = "TEMPORAL_DEPENDENCY"        # Chronological sequence constraints
    SOCIAL_DEPENDENCY = "SOCIAL_DEPENDENCY"            # Relationship or network links
    SPECULATIVE_ASSOCIATION = "SPECULATIVE_ASSOCIATION"# Multi-hop ungrounded guess (MANDATORY QUARANTINE)


class CandidateLifecycleState(str, enum.Enum):
    """Lifecycle stages enforcing Generated != Persisted != Promotable."""

    GENERATED = "GENERATED"      # Ephemeral hypothesis generated in turn, can be pruned by budget
    PERSISTED = "PERSISTED"      # Stored in character_candidate_facts; non-canonical candidate
    ACTIVE = "ACTIVE"            # Currently participating in competition/ranking for its slot
    PROMOTABLE = "PROMOTABLE"    # Passed validation and choice prerequisites; awaiting promotion gate
    PRUNED = "PRUNED"            # Exceeded slot capacity (>3 active candidates), preserved for provenance
    CONSIDERED_BUT_NOT_SELECTED = "CONSIDERED_BUT_NOT_SELECTED"# Evaluated in choice but alternative chosen, preserved for counterfactual reflection
    DORMANT = "DORMANT"          # Unconfirmed for extended period, decayed plausibility
    SUPERSEDED = "SUPERSEDED"    # Replaced by a more current candidate or revision
    REJECTED = "REJECTED"        # Falsified or violating core invariants


class PlausibilityBreakdown(BaseModel):
    """Heuristic multi-factor plausibility ranking breakdown (NEVER interpreted as mathematical probability)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    prior_weight: float = Field(default=0.5, ge=0.0, le=1.0, description="Heuristic prior plausibility.")
    evidence_grounding_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Strength of grounded observation.")
    coherence_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Internal consistency with canonical reality.")
    utility_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Contextual fit or narrative suitability.")
    composite_plausibility_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Weighted composite heuristic score.")

    @classmethod
    def create(
        cls,
        prior_weight: float = 0.5,
        evidence_grounding_score: float = 0.5,
        coherence_score: float = 0.5,
        utility_score: float = 0.5,
        composite_plausibility_score: Optional[float] = None,
    ) -> "PlausibilityBreakdown":
        if composite_plausibility_score is None:
            # Default weighted composite formula (heuristic ranking signal only)
            composite_plausibility_score = round(
                0.20 * prior_weight
                + 0.40 * evidence_grounding_score
                + 0.25 * coherence_score
                + 0.15 * utility_score,
                4,
            )
        return cls(
            prior_weight=prior_weight,
            evidence_grounding_score=evidence_grounding_score,
            coherence_score=coherence_score,
            utility_score=utility_score,
            composite_plausibility_score=composite_plausibility_score,
        )


class EvidenceFamily(BaseModel):
    """Lineage cluster tracking genuine source independence across sessions.

    Hard invariant: Different sessions != independent evidence.
    Repeated assertions from the same origin increment mention_count, but
    contribute exactly 1 unit of independent evidence.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    family_id: str = Field(..., description="Unique identifier for this evidence family.")
    source_type: str = Field(..., description="Source type (e.g. USER_ASSERTION, EXTERNAL_OBSERVATION, CANONICAL_FACT).")
    cluster_key: str = Field(..., description="Normalized semantic cluster key identifying underlying factual claim.")
    mention_count: int = Field(default=1, ge=1, description="Cumulative times observed across all sessions.")
    session_ids: tuple[str, ...] = Field(default_factory=tuple, description="Distinct conversation/session IDs.")
    first_observed_at: datetime = Field(default_factory=_utc_now, description="UTC timestamp of first occurrence.")
    last_observed_at: datetime = Field(default_factory=_utc_now, description="UTC timestamp of latest occurrence.")

    @property
    def independent_evidence_weight(self) -> int:
        """Each distinct family counts as exactly 1 independent evidence point."""
        return 1

    def record_mention(self, session_id: Optional[str] = None) -> "EvidenceFamily":
        """Return a new instance with incremented mention_count and recorded session."""
        new_sessions = list(self.session_ids)
        if session_id and session_id not in new_sessions:
            new_sessions.append(session_id)
        return EvidenceFamily(
            family_id=self.family_id,
            source_type=self.source_type,
            cluster_key=self.cluster_key,
            mention_count=self.mention_count + 1,
            session_ids=tuple(new_sessions),
            first_observed_at=self.first_observed_at,
            last_observed_at=_utc_now(),
        )


class ProvenanceLineage(BaseModel):
    """Structured derivation path tracking origin evidence, parent hypotheses, and inference depth."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    origin_id: str = Field(..., description="Identifier of the stimulus, message, or seed event.")
    parent_candidate_ids: tuple[str, ...] = Field(default_factory=tuple, description="IDs of predecessor candidate hypotheses.")
    evidence_family_ids: tuple[str, ...] = Field(default_factory=tuple, description="Unique EvidenceFamily IDs grounding this hypothesis.")
    inference_depth: int = Field(default=0, ge=0, description="Hop count from direct evidence (max 2).")
    derivation_path: tuple[str, ...] = Field(default_factory=tuple, description="Audit breadcrumbs of reasoning steps.")


class CandidateHypothesis(BaseModel):
    """Immutable domain representation of an unconfirmed reality candidate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str = Field(..., description="Unique deterministic identifier for this candidate.")
    entity_id: str = Field(default="aevum", description="Attributed entity (e.g. 'aevum').")
    slot_name: str = Field(..., description="Target attribute slot, e.g. 'education.major'.")
    proposed_value: Any = Field(..., description="Proposed fact value.")
    reality_taxonomy: RealityTaxonomy = Field(
        default=RealityTaxonomy.SIMULATED_BIOGRAPHY_FACT,
        description="Dual reality categorization.",
    )
    inference_depth: int = Field(default=0, ge=0, description="Hop distance from grounded stimulus.")
    inference_edge_type: InferenceEdgeType = Field(
        default=InferenceEdgeType.DIRECT_ATTRIBUTE,
        description="Formal dependency edge type.",
    )
    plausibility: PlausibilityBreakdown = Field(
        default_factory=PlausibilityBreakdown,
        description="Heuristic multi-factor plausibility breakdown.",
    )
    provenance: ProvenanceLineage = Field(..., description="DAG-verified provenance lineage.")
    evidence_families: tuple[EvidenceFamily, ...] = Field(
        default_factory=tuple,
        description="Associated evidence families.",
    )
    lifecycle_state: CandidateLifecycleState = Field(
        default=CandidateLifecycleState.GENERATED,
        description="Current tri-state lifecycle status.",
    )
    is_quarantined: bool = Field(default=False, description="Whether quarantined from promotion paths.")
    quarantine_reason: Optional[str] = Field(default=None, description="Reason for quarantine if active.")
    supersedes_id: Optional[str] = Field(default=None, description="ID of prior candidate superseded by this one.")
    superseded_by_id: Optional[str] = Field(default=None, description="ID of newer candidate superseding this one.")
    created_at: datetime = Field(default_factory=_utc_now, description="UTC creation timestamp.")
    updated_at: datetime = Field(default_factory=_utc_now, description="UTC update timestamp.")
    stale_at: Optional[datetime] = Field(default=None, description="UTC timestamp when candidate becomes stale.")
    selection_metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="Structured provenance of choice evaluation and non-selection reasons.",
    )

    def model_post_init(self, __context: Any) -> None:
        """Enforce strict invariant checks and quarantine triggers."""
        # Invariant 1: SPECULATIVE_ASSOCIATION must be quarantined
        if self.inference_edge_type == InferenceEdgeType.SPECULATIVE_ASSOCIATION:
            if not self.is_quarantined:
                object.__setattr__(self, "is_quarantined", True)
                if not self.quarantine_reason:
                    object.__setattr__(
                        self,
                        "quarantine_reason",
                        "SPECULATIVE_ASSOCIATION requires mandatory quarantine (Anti-Snowballing Boundary).",
                    )
        # Invariant 2: inference_depth > 2 must be quarantined / rejected
        if self.inference_depth > 2:
            if not self.is_quarantined:
                object.__setattr__(self, "is_quarantined", True)
                if not self.quarantine_reason:
                    object.__setattr__(
                        self,
                        "quarantine_reason",
                        f"Inference depth {self.inference_depth} exceeds max_inference_depth (2).",
                    )

    @property
    def independent_evidence_count(self) -> int:
        """Cardinally distinct evidence families grounding this candidate."""
        if self.evidence_families:
            return len({fam.family_id for fam in self.evidence_families})
        return len(set(self.provenance.evidence_family_ids))

    @property
    def total_mention_count(self) -> int:
        """Cumulative mentions across all sessions."""
        if self.evidence_families:
            return sum(fam.mention_count for fam in self.evidence_families)
        return 1

    def to_persisted(self) -> "CandidateHypothesis":
        """Transition from GENERATED to PERSISTED state."""
        return self.model_copy(
            update={
                "lifecycle_state": CandidateLifecycleState.PERSISTED,
                "updated_at": _utc_now(),
            }
        )

    def to_active(self) -> "CandidateHypothesis":
        """Transition to ACTIVE state in slot competition."""
        return self.model_copy(
            update={
                "lifecycle_state": CandidateLifecycleState.ACTIVE,
                "updated_at": _utc_now(),
            }
        )

    def to_promotable(self) -> "CandidateHypothesis":
        """Transition to PROMOTABLE state (prerequisites met; pending promotion authorization)."""
        if self.is_quarantined:
            raise ValueError(f"Cannot mark quarantined candidate {self.candidate_id} as PROMOTABLE.")
        return self.model_copy(
            update={
                "lifecycle_state": CandidateLifecycleState.PROMOTABLE,
                "updated_at": _utc_now(),
            }
        )

    def to_pruned(self, reason: str = "Exceeded max active candidates per slot (3)") -> "CandidateHypothesis":
        """Transition to PRUNED state (non-destructive retirement preserving provenance)."""
        return self.model_copy(
            update={
                "lifecycle_state": CandidateLifecycleState.PRUNED,
                "updated_at": _utc_now(),
            }
        )

    def to_considered_but_not_selected(
        self,
        reason: str = "Alternative candidate selected",
        selected_candidate_id: Optional[str] = None,
        choice_score: Optional[float] = None,
        factor_inputs: Optional[dict[str, float]] = None,
    ) -> "CandidateHypothesis":
        """Transition to CONSIDERED_BUT_NOT_SELECTED state (preserving full provenance and rationale)."""
        metadata = dict(self.selection_metadata or {})
        metadata["non_selection_reason"] = reason
        if selected_candidate_id:
            metadata["selected_candidate_id"] = selected_candidate_id
        if choice_score is not None:
            metadata["choice_score"] = choice_score
        if factor_inputs is not None:
            metadata["factor_inputs"] = factor_inputs
        return self.model_copy(
            update={
                "lifecycle_state": CandidateLifecycleState.CONSIDERED_BUT_NOT_SELECTED,
                "selection_metadata": metadata,
                "updated_at": _utc_now(),
            }
        )


class CandidateHypothesisSet(BaseModel):
    """Aggregate managing competing hypotheses within a single attribute slot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    slot_name: str = Field(..., description="Target attribute slot.")
    entity_id: str = Field(default="aevum", description="Target entity ID.")
    candidates: dict[str, CandidateHypothesis] = Field(
        default_factory=dict,
        description="Competing candidates keyed by candidate_id.",
    )

    @property
    def active_candidates(self) -> list[CandidateHypothesis]:
        """Candidates actively competing (not PRUNED, DORMANT, SUPERSEDED, or REJECTED)."""
        return [
            c for c in self.candidates.values()
            if c.lifecycle_state in (
                CandidateLifecycleState.ACTIVE,
                CandidateLifecycleState.PERSISTED,
                CandidateLifecycleState.PROMOTABLE,
            )
            and not c.is_quarantined
        ]

    @property
    def leading_candidate(self) -> Optional[CandidateHypothesis]:
        """Candidate with highest composite plausibility score."""
        actives = self.active_candidates
        if not actives:
            return None
        return max(actives, key=lambda c: c.plausibility.composite_plausibility_score)

    @property
    def decision_margin(self) -> float:
        """Delta between top 2 active candidate plausibility scores."""
        actives = sorted(
            self.active_candidates,
            key=lambda c: c.plausibility.composite_plausibility_score,
            reverse=True,
        )
        if len(actives) < 2:
            return 1.0 if len(actives) == 1 else 0.0
        return round(
            float(
                actives[0].plausibility.composite_plausibility_score
                - actives[1].plausibility.composite_plausibility_score
            ),
            4,
        )

    def with_candidate(
        self,
        new_candidate: CandidateHypothesis,
        max_active_candidates_per_slot: int = 3,
    ) -> "CandidateHypothesisSet":
        """Add candidate and enforce slot capacity via non-destructive PRUNED transition."""
        updated_dict = dict(self.candidates)
        updated_dict[new_candidate.candidate_id] = new_candidate

        # Count active unquarantined candidates
        active_list = [
            c for c in updated_dict.values()
            if c.lifecycle_state in (
                CandidateLifecycleState.ACTIVE,
                CandidateLifecycleState.PERSISTED,
                CandidateLifecycleState.PROMOTABLE,
            )
            and not c.is_quarantined
        ]

        # Enforce max_active_candidates_per_slot (default 3)
        if len(active_list) > max_active_candidates_per_slot:
            # Sort by lowest plausibility score (weakest pruned first)
            active_list_sorted = sorted(
                active_list,
                key=lambda c: (c.plausibility.composite_plausibility_score, -c.created_at.timestamp()),
            )
            excess_count = len(active_list) - max_active_candidates_per_slot
            for i in range(excess_count):
                weakest = active_list_sorted[i]
                updated_dict[weakest.candidate_id] = weakest.to_pruned(
                    reason="Slot capacity limit exceeded (max 3 active candidates)"
                )

        return CandidateHypothesisSet(
            slot_name=self.slot_name,
            entity_id=self.entity_id,
            candidates=updated_dict,
        )

