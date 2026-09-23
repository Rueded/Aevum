"""Choice domain models for Reality & Epistemic Inference Engine (Phase 7D.2).

Defines first-class Choice / Outcome selection data structures, multi-attribute
decision factors, competition evaluation summaries, and structured decision provenance.

Strict Invariants:
- Plausibility != Probability != Choice != Promotion.
- Probability fields/claims are strictly forbidden.
- Output of Choice remains strictly non-canonical.
"""

from datetime import datetime, timezone
import enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.reality.candidate_models import CandidateHypothesis


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CompetitionState(str, enum.Enum):
    """Evaluation status of competing candidate hypotheses within a slot."""

    CLEAR_LEADER = "CLEAR_LEADER"                      # Top candidate plausibility delta >= 0.10
    UNDETERMINED_AMBIVALENCE = "UNDETERMINED_AMBIVALENCE"# Top candidates have delta < 0.10; competition alone cannot discriminate
    SINGLE_CANDIDATE = "SINGLE_CANDIDATE"              # Exactly one viable candidate
    NO_VIABLE_CANDIDATES = "NO_VIABLE_CANDIDATES"      # Zero viable candidates (quarantined, conflicting with user locks, etc.)


class ChoiceRationaleCode(str, enum.Enum):
    """Categorical audit code for decision outcome rationale."""

    TEMPERAMENT_ALIGNMENT = "TEMPERAMENT_ALIGNMENT"    # Selection driven primarily by character temperament/personality fit
    VALUES_ALIGNMENT = "VALUES_ALIGNMENT"              # Selection driven by core personal values/independence
    CHALLENGE_PREFERENCE = "CHALLENGE_PREFERENCE"      # Selection driven by intellectual/creative challenge preference
    RESOURCE_OPTIMAL = "RESOURCE_OPTIMAL"              # Selection driven by practical family/financial resources
    MULTI_FACTOR_BALANCED = "MULTI_FACTOR_BALANCED"    # Balanced multi-attribute composite optimization
    AMBIVALENCE_RESOLVED = "AMBIVALENCE_RESOLVED"      # Plausibility was ambiguous (delta < 0.10), resolved by character choice factors
    USER_LOCK_RESTRICTED = "USER_LOCK_RESTRICTED"      # Choice constrained by USER_LOCKED canonical facts
    NO_VIABLE_CANDIDATES = "NO_VIABLE_CANDIDATES"      # Infeasible: all candidates conflict with constraints/locks
    CHOICE_AMBIVALENCE = "CHOICE_AMBIVALENCE"          # Choice scores themselves are tied/undifferentiated


class CompetitionResult(BaseModel):
    """Deterministic evaluation of candidate viability and plausibility within a slot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    slot_name: str = Field(..., description="Target attribute slot.")
    entity_id: str = Field(default="aevum", description="Target entity ID.")
    candidate_set_id: str = Field(..., description="Deterministic or UUID identifier for candidate set.")
    viable_candidates: tuple[CandidateHypothesis, ...] = Field(
        default_factory=tuple,
        description="Candidates that survived viability validation.",
    )
    excluded_candidates: tuple[tuple[str, str], ...] = Field(
        default_factory=tuple,
        description="Candidate IDs excluded along with specific reason (e.g. USER_LOCK_CONFLICT).",
    )
    plausibility_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Adjusted composite plausibility scores keyed by candidate_id.",
    )
    leading_candidate_id: Optional[str] = Field(default=None, description="Candidate with highest adjusted plausibility.")
    runner_up_candidate_id: Optional[str] = Field(default=None, description="Candidate with second highest plausibility.")
    decision_margin: float = Field(default=0.0, description="Delta |S1 - S2| between top two candidate plausibilities.")
    is_ambiguous: bool = Field(default=False, description="True if decision_margin < 0.10 and >= 2 viable candidates.")
    competition_state: CompetitionState = Field(
        default=CompetitionState.CLEAR_LEADER,
        description="Structured competition status.",
    )
    computed_at: datetime = Field(default_factory=_utc_now, description="UTC evaluation timestamp.")


class ChoiceFactorBreakdown(BaseModel):
    """Structured decision factor scores for a single candidate option."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plausibility_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Input plausibility compatibility.")
    temperament_fit: float = Field(default=0.5, ge=0.0, le=1.0, description="Alignment with Aevum's personality traits.")
    values_alignment: float = Field(default=0.5, ge=0.0, le=1.0, description="Alignment with ethical and personal values.")
    challenge_preference: float = Field(default=0.5, ge=0.0, le=1.0, description="Intellectual or creative challenge fit.")
    resource_compatibility: float = Field(default=0.5, ge=0.0, le=1.0, description="Family resources and financial practicality.")
    timeline_compatibility: float = Field(default=0.5, ge=0.0, le=1.0, description="Age, prerequisite, and schedule compatibility.")
    opportunity_cost: float = Field(default=0.0, ge=0.0, le=1.0, description="Sacrifices, relocation, or debt burden.")
    time_cost: float = Field(default=0.0, ge=0.0, le=1.0, description="Excessive weekly grind or schedule overload.")

    @field_validator("*", mode="before")
    @classmethod
    def reject_probability_words(cls, v: Any, info: Any) -> Any:
        field_name = info.field_name or ""
        if "probability" in field_name.lower():
            raise ValueError(f"Forbidden field '{field_name}': Choice Engine prohibits probability claims.")
        return v


class ChoiceConfig(BaseModel):
    """Deterministic configuration and weights for the Choice Engine."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    w_plausibility: float = Field(default=0.20, ge=0.0, le=1.0, description="Weight for plausibility input.")
    w_temperament: float = Field(default=0.25, ge=0.0, le=1.0, description="Weight for temperament/personality fit.")
    w_values: float = Field(default=0.20, ge=0.0, le=1.0, description="Weight for values alignment.")
    w_challenge: float = Field(default=0.15, ge=0.0, le=1.0, description="Weight for challenge preference.")
    w_resources: float = Field(default=0.10, ge=0.0, le=1.0, description="Weight for practical resource compatibility.")
    w_timeline: float = Field(default=0.10, ge=0.0, le=1.0, description="Weight for timeline fit.")
    w_opportunity: float = Field(default=0.10, ge=0.0, le=1.0, description="Negative weight penalty for opportunity cost.")
    w_time_cost: float = Field(default=0.10, ge=0.0, le=1.0, description="Negative weight penalty for time cost.")
    occam_penalty_per_depth: float = Field(default=0.05, ge=0.0, le=0.5, description="Plausibility discount per inference hop.")
    ambivalence_threshold: float = Field(default=0.10, ge=0.0, le=0.5, description="Plausibility delta below which ambiguity holds.")
    choice_ambivalence_margin: float = Field(default=0.02, ge=0.0, le=0.5, description="Choice score delta below which choice is ambivalently tied.")


class ChoiceDecisionResult(BaseModel):
    """Structured decision record emitted by ChoiceSelectionService.
    
    Hard Invariants:
    - Output is strictly NON-CANONICAL.
    - Zero modification of character_core_facts.
    - Full decision provenance and factor contributions preserved.
    - Unselected alternatives transitioned to CONSIDERED_BUT_NOT_SELECTED.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_id: str = Field(..., description="Unique deterministic or UUID identifier for this choice decision.")
    entity_id: str = Field(default="aevum", description="Target entity ID.")
    slot_name: str = Field(..., description="Attribute slot evaluated.")
    candidate_set_id: str = Field(..., description="Identifier of the evaluated candidate set.")
    candidate_ids_considered: tuple[str, ...] = Field(..., description="IDs of all candidates evaluated.")
    selected_candidate_id: Optional[str] = Field(default=None, description="ID of chosen candidate, if any.")
    unselected_candidate_ids: tuple[str, ...] = Field(default_factory=tuple, description="IDs of unselected candidates.")
    selected_candidate: Optional[CandidateHypothesis] = Field(default=None, description="Chosen candidate instance.")
    archived_unselected_candidates: tuple[CandidateHypothesis, ...] = Field(
        default_factory=tuple,
        description="Unselected candidates transitioned to CONSIDERED_BUT_NOT_SELECTED.",
    )
    decision_timestamp: datetime = Field(default_factory=_utc_now, description="UTC timestamp of decision.")
    decision_model_version: str = Field(default="1.0.0", description="Version of the Choice Engine logic.")
    competition_state: CompetitionState = Field(..., description="Competition state from CandidateCompetitionService.")
    competition_margin: float = Field(default=0.0, description="Plausibility delta between top two candidates.")
    plausibility_scores: dict[str, float] = Field(default_factory=dict, description="Plausibility scores evaluated.")
    factor_inputs: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="Raw factor inputs per candidate_id.",
    )
    factor_contributions: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="Weighted factor contributions per candidate_id.",
    )
    choice_scores: dict[str, float] = Field(default_factory=dict, description="Final composite ChoiceScores per candidate_id.")
    choice_margin: float = Field(default=0.0, description="Delta between top two ChoiceScores.")
    rationale_code: ChoiceRationaleCode = Field(
        default=ChoiceRationaleCode.MULTI_FACTOR_BALANCED,
        description="Structured rationale category.",
    )
    rationale_description: str = Field(..., description="Human-auditable explanation synthesized from structured factors.")
    is_non_canonical: bool = Field(default=True, description="Strict lock-in: Choice outcomes are NOT canonical reality.")
    provenance_references: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Evidence family and origin references.",
    )
