"""Guarded Life-State Transition Engine (Phase 8C.3).

Constitutional Invariants & Guardrails Enforced:
- Three-Layer Guard Architecture:
  - Guard A (Temporal Eligibility): Minimum required duration satisfied?
  - Guard B (Predecessor State): Prior stage settled and valid in developmental DAG?
  - Guard C (Progression Evidence): Explicit evidence confirming transition occurred?
- Epistemic Demarcation:
  - Guard A + Guard B == ELIGIBLE_FOR_TRANSITION (calendar & prerequisite conditions met;
    personal transition is merely eligible, NOT supported, NOT canonical).
  - Guard A + Guard B + Guard C == TRANSITION_SUPPORTED (evidentially supported;
    emits LifeStateTransitionSignal for downstream governed pipeline).
- Lock 7: Canonical Mutation Singularity.
  8C.3 NEVER directly mutates canonical reality or calls set_fact().
  Transition signals are non-canonical DTOs processed strictly by BiographyPromotionService.
- Core Guardrail: 8C.3 can determine whether a transition is temporally and evidentially
  supported; it must NOT equate calendar eligibility with personal progression.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional, Sequence
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.reality.temporal_models import LifeStage


# =============================================================================
# Categorical Transition Evaluation Status
# =============================================================================

class TransitionEvaluationStatus(str, Enum):
    """Categorical outcome of a guarded life-state transition evaluation."""

    INELIGIBLE = "INELIGIBLE"
    """Guard A (duration) or Guard B (predecessor/DAG) failed. Cannot transition."""

    ELIGIBLE_FOR_TRANSITION = "ELIGIBLE_FOR_TRANSITION"
    """Guard A and Guard B passed; Guard C (progression evidence) is missing.
    Time window arrived, but personal transition has NO factual evidence.
    CRITICAL: Does NOT authorise stage promotion or state mutation."""

    TRANSITION_SUPPORTED = "TRANSITION_SUPPORTED"
    """Guard A, Guard B, AND Guard C ALL passed.
    Temporal eligibility and factual evidence converge; ready to emit signal."""

    BLOCKED_BY_ANOMALY = "BLOCKED_BY_ANOMALY"
    """Blocked by leave of absence, gap year, academic hold, or active contradiction."""


# =============================================================================
# Three-Layer Guard Evaluation Records
# =============================================================================

class GuardAEvaluation(BaseModel):
    """Guard A outcome: Temporal eligibility and duration verification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool = Field(..., description="True if minimum duration window is satisfied.")
    elapsed_duration_days: int = Field(..., ge=0, description="Elapsed calendar days since stage start.")
    required_minimum_duration_days: int = Field(..., ge=0, description="Minimum days required for eligibility.")
    reason: str = Field(..., description="Audit rationale for Guard A finding.")


class GuardBEvaluation(BaseModel):
    """Guard B outcome: Predecessor state and stage DAG validity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool = Field(..., description="True if predecessor is settled and transition is valid in DAG.")
    source_stage: LifeStage = Field(..., description="Current/preceding developmental stage.")
    target_stage: LifeStage = Field(..., description="Proposed successor developmental stage.")
    is_valid_dag_successor: bool = Field(..., description="True if target is a legal topological successor.")
    is_predecessor_settled: bool = Field(..., description="True if prior stage was completed/settled without unresolved hold.")
    reason: str = Field(..., description="Audit rationale for Guard B finding.")


class GuardCEvaluation(BaseModel):
    """Guard C outcome: Explicit progression evidence verification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool = Field(..., description="True if explicit evidence confirming actual progression exists.")
    evidence_count: int = Field(..., ge=0, description="Number of supporting progression evidence items.")
    evidence_keys: tuple[str, ...] = Field(default_factory=tuple, description="Keys/identifiers of observed evidence.")
    reason: str = Field(..., description="Audit rationale for Guard C finding.")


# =============================================================================
# Composite Evaluation Finding
# =============================================================================

class LifeStateTransitionEvaluation(BaseModel):
    """Comprehensive, immutable audit result of a guarded life-stage transition evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_id: str = Field(..., description="Deterministic evaluation identifier.")
    character_id: str = Field(default="aevum", description="Character entity identifier.")
    source_stage: LifeStage = Field(..., description="Source developmental stage.")
    source_academic_level: Optional[int] = Field(default=None, description="Source academic level (e.g. 1 for Y1).")
    target_stage: LifeStage = Field(..., description="Target developmental stage.")
    target_academic_level: Optional[int] = Field(default=None, description="Target academic level (e.g. 2 for Y2).")
    guard_a: GuardAEvaluation = Field(..., description="Guard A (Temporal Eligibility) evaluation.")
    guard_b: GuardBEvaluation = Field(..., description="Guard B (Predecessor State) evaluation.")
    guard_c: GuardCEvaluation = Field(..., description="Guard C (Progression Evidence) evaluation.")
    status: TransitionEvaluationStatus = Field(..., description="Overall transition status.")
    explanation: str = Field(..., description="Concise human-readable audit justification.")


# =============================================================================
# Non-Canonical Transition Signal (Lock 7)
# =============================================================================

class LifeStateTransitionSignal(BaseModel):
    """Typed non-canonical signal emitted ONLY when TRANSITION_SUPPORTED (Lock 7).

    Constitutional Invariant:
    This signal is an evidence/candidate payload, NOT a canonical mutation.
    It carries zero set_fact authority and must be processed by BiographyPromotionService.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    signal_id: str = Field(..., description="Deterministic signal identifier.")
    character_id: str = Field(default="aevum", description="Character entity identifier.")
    source_stage: LifeStage = Field(..., description="Source developmental stage.")
    source_academic_level: Optional[int] = Field(default=None, description="Source academic level.")
    target_stage: LifeStage = Field(..., description="Target developmental stage.")
    target_academic_level: Optional[int] = Field(default=None, description="Target academic level.")
    effective_now: datetime = Field(..., description="Authoritative evaluation timestamp.")
    evidence_keys: tuple[str, ...] = Field(default_factory=tuple, description="Corroborating evidence keys.")
    is_canonical: bool = Field(default=False, description="Strictly False; 8C never mints canonical facts.")
    rationale: str = Field(..., description="Explanatory audit text for downstream pipeline.")


# =============================================================================
# Stage DAG Connectivity Rules
# =============================================================================

# Permitted topological forward transitions in Malaysian / general education
_VALID_STAGE_DAG: dict[LifeStage, set[LifeStage]] = {
    LifeStage.PRIMARY_EDUCATION: {LifeStage.SECONDARY_EDUCATION},
    LifeStage.SECONDARY_EDUCATION: {
        LifeStage.PRE_UNIVERSITY,
        LifeStage.DIPLOMA,
        LifeStage.TRANSITIONAL,  # Gap year / deferral
    },
    LifeStage.PRE_UNIVERSITY: {
        LifeStage.UNDERGRADUATE,
        LifeStage.TRANSITIONAL,
    },
    LifeStage.DIPLOMA: {
        LifeStage.UNDERGRADUATE,
        LifeStage.EARLY_CAREER,
        LifeStage.TRANSITIONAL,
    },
    LifeStage.UNDERGRADUATE: {
        LifeStage.UNDERGRADUATE,  # Intras-stage level advancement (Y1 -> Y2 -> Y3)
        LifeStage.INTERNSHIP,
        LifeStage.POSTGRADUATE,
        LifeStage.EARLY_CAREER,
        LifeStage.TRANSITIONAL,
    },
    LifeStage.INTERNSHIP: {
        LifeStage.UNDERGRADUATE,  # Return from internship to complete studies
        LifeStage.EARLY_CAREER,
        LifeStage.TRANSITIONAL,
    },
    LifeStage.POSTGRADUATE: {
        LifeStage.EARLY_CAREER,
        LifeStage.CAREER,
        LifeStage.TRANSITIONAL,
    },
    LifeStage.EARLY_CAREER: {
        LifeStage.CAREER,
        LifeStage.POSTGRADUATE,
        LifeStage.TRANSITIONAL,
    },
    LifeStage.CAREER: {
        LifeStage.POSTGRADUATE,
        LifeStage.TRANSITIONAL,
    },
    LifeStage.TRANSITIONAL: {
        LifeStage.PRE_UNIVERSITY,
        LifeStage.DIPLOMA,
        LifeStage.UNDERGRADUATE,
        LifeStage.INTERNSHIP,
        LifeStage.POSTGRADUATE,
        LifeStage.EARLY_CAREER,
        LifeStage.CAREER,
    },
}


# =============================================================================
# Guarded Transition Evaluator Engine
# =============================================================================

class GuardedTransitionEngine:
    """Deterministic, pure evaluator for life-stage transitions (Phase 8C.3).

    Guarantees:
    1. Three-Layer Guard enforcement:
       A (Duration) + B (Predecessor) -> ELIGIBLE_FOR_TRANSITION
       A + B + C (Evidence) -> TRANSITION_SUPPORTED
    2. Singularity (Lock 7): Zero database writes, zero set_fact calls.
    3. Separation of Calendar from Personal Reality (Lock 11):
       Time passing never automatically advances an academic stage.
    """

    DEFAULT_MINIMUM_ACADEMIC_YEAR_DAYS: int = 240
    """Standard minimum days (~8 months) required before considering academic year advancement."""

    @classmethod
    def evaluate_transition(
        cls,
        source_stage: LifeStage,
        source_start_date: date,
        effective_now: datetime,
        target_stage: LifeStage,
        source_academic_level: Optional[int] = None,
        target_academic_level: Optional[int] = None,
        is_predecessor_settled: bool = True,
        progression_evidence: Optional[Sequence[str]] = None,
        minimum_duration_days: Optional[int] = None,
        is_on_leave_or_hold: bool = False,
        character_id: str = "aevum",
    ) -> LifeStateTransitionEvaluation:
        """Evaluate whether a proposed transition is eligible and evidentially supported.

        Args:
            source_stage: Current active life stage.
            source_start_date: Calendar start date of the current stage.
            effective_now: Authoritative current UTC datetime.
            target_stage: Proposed target life stage.
            source_academic_level: Current academic year/level (e.g. 1 for Year 1).
            target_academic_level: Target academic year/level (e.g. 2 for Year 2).
            is_predecessor_settled: True if current stage has completed all requirements.
            progression_evidence: Sequence of explicit observation keys/statements confirming transition.
            minimum_duration_days: Minimum days required to satisfy temporal eligibility.
            is_on_leave_or_hold: True if student is on academic leave, deferral, or disciplinary hold.
            character_id: Character entity identifier.

        Returns:
            LifeStateTransitionEvaluation documenting findings of all three guards.
        """
        if effective_now.tzinfo is None:
            raise ValueError(f"effective_now '{effective_now}' must be timezone-aware (UTC).")

        now_date = effective_now.date()
        if now_date < source_start_date:
            raise ValueError(
                f"Temporal anomaly: effective_now date '{now_date}' cannot precede "
                f"source_start_date '{source_start_date}'."
            )

        elapsed_days = (now_date - source_start_date).days
        min_days = (
            minimum_duration_days
            if minimum_duration_days is not None
            else cls.DEFAULT_MINIMUM_ACADEMIC_YEAR_DAYS
        )

        # ---------------------------------------------------------------------
        # Guard A: Temporal Eligibility (Minimum Duration Window)
        # ---------------------------------------------------------------------
        guard_a_passed = elapsed_days >= min_days
        guard_a = GuardAEvaluation(
            passed=guard_a_passed,
            elapsed_duration_days=elapsed_days,
            required_minimum_duration_days=min_days,
            reason=(
                f"Elapsed {elapsed_days} days satisfies required minimum {min_days} days."
                if guard_a_passed
                else f"Elapsed {elapsed_days} days is less than required minimum {min_days} days."
            ),
        )

        # ---------------------------------------------------------------------
        # Guard B: Predecessor State & Stage DAG Validity
        # ---------------------------------------------------------------------
        valid_successors = _VALID_STAGE_DAG.get(source_stage, set())
        is_valid_dag = target_stage in valid_successors

        # Intra-stage undergraduate progression validation
        if source_stage == LifeStage.UNDERGRADUATE and target_stage == LifeStage.UNDERGRADUATE:
            if source_academic_level is not None and target_academic_level is not None:
                # Must be strictly +1 level (e.g. Y1 -> Y2, Y2 -> Y3); no multi-year leaping
                if target_academic_level != source_academic_level + 1:
                    is_valid_dag = False

        guard_b_passed = is_valid_dag and is_predecessor_settled and not is_on_leave_or_hold
        b_reasons: list[str] = []
        if not is_valid_dag:
            b_reasons.append(
                f"Target {target_stage.value} (level={target_academic_level}) is not a valid successor "
                f"from {source_stage.value} (level={source_academic_level}) in stage DAG."
            )
        if not is_predecessor_settled:
            b_reasons.append(f"Predecessor stage {source_stage.value} is not marked as settled/completed.")
        if is_on_leave_or_hold:
            b_reasons.append("Character is currently on academic leave, deferral, or administrative hold.")
        if guard_b_passed:
            b_reasons.append("Predecessor stage is settled and transition is topologically valid in DAG.")

        guard_b = GuardBEvaluation(
            passed=guard_b_passed,
            source_stage=source_stage,
            target_stage=target_stage,
            is_valid_dag_successor=is_valid_dag,
            is_predecessor_settled=is_predecessor_settled,
            reason="; ".join(b_reasons),
        )

        # ---------------------------------------------------------------------
        # Guard C: Progression Evidence
        # ---------------------------------------------------------------------
        ev_tuple = tuple(progression_evidence) if progression_evidence else ()
        guard_c_passed = len(ev_tuple) > 0
        guard_c = GuardCEvaluation(
            passed=guard_c_passed,
            evidence_count=len(ev_tuple),
            evidence_keys=ev_tuple,
            reason=(
                f"Found {len(ev_tuple)} corroborating progression evidence items: {ev_tuple}."
                if guard_c_passed
                else "Zero progression evidence found. Calendar duration alone does not prove transition."
            ),
        )

        # ---------------------------------------------------------------------
        # Composite Status Determination
        # ---------------------------------------------------------------------
        if is_on_leave_or_hold:
            status = TransitionEvaluationStatus.BLOCKED_BY_ANOMALY
            explanation = "Transition is actively blocked by academic leave, deferral, or hold."
        elif not guard_a.passed or not guard_b.passed:
            status = TransitionEvaluationStatus.INELIGIBLE
            explanation = f"Transition ineligible: Guard A={guard_a.passed}, Guard B={guard_b.passed}."
        elif guard_a.passed and guard_b.passed and not guard_c.passed:
            # The Critical Boundary: Time arrived, but personal transition has NO factual evidence!
            status = TransitionEvaluationStatus.ELIGIBLE_FOR_TRANSITION
            explanation = (
                "Transition is temporally and topologically eligible (Guard A & B passed), "
                "but lacks progression evidence (Guard C failed). Time elapsed != personal progression."
            )
        elif guard_a.passed and guard_b.passed and guard_c.passed:
            # Full convergence
            status = TransitionEvaluationStatus.TRANSITION_SUPPORTED
            explanation = (
                "Transition is fully supported by temporal duration, settled predecessor, "
                "and explicit progression evidence (Guard A, B, and C all passed)."
            )
        else:
            status = TransitionEvaluationStatus.INELIGIBLE
            explanation = "Unknown guard combination; fail closed."

        eval_id = f"eval_{source_stage.value}_{target_stage.value}_{now_date.isoformat()}"

        return LifeStateTransitionEvaluation(
            evaluation_id=eval_id,
            character_id=character_id,
            source_stage=source_stage,
            source_academic_level=source_academic_level,
            target_stage=target_stage,
            target_academic_level=target_academic_level,
            guard_a=guard_a,
            guard_b=guard_b,
            guard_c=guard_c,
            status=status,
            explanation=explanation,
        )

    @classmethod
    def emit_transition_signal(
        cls,
        evaluation: LifeStateTransitionEvaluation,
        effective_now: datetime,
    ) -> Optional[LifeStateTransitionSignal]:
        """Emit a non-canonical LifeStateTransitionSignal IF AND ONLY IF TRANSITION_SUPPORTED.

        Constitutional Invariant (Lock 7):
        If status is ELIGIBLE_FOR_TRANSITION or INELIGIBLE, returns None.
        Calendar eligibility alone NEVER generates a transition signal.
        """
        if evaluation.status != TransitionEvaluationStatus.TRANSITION_SUPPORTED:
            return None

        signal_id = f"sig_trans_{evaluation.source_stage.value}_to_{evaluation.target_stage.value}_{uuid.uuid4().hex[:8]}"

        return LifeStateTransitionSignal(
            signal_id=signal_id,
            character_id=evaluation.character_id,
            source_stage=evaluation.source_stage,
            source_academic_level=evaluation.source_academic_level,
            target_stage=evaluation.target_stage,
            target_academic_level=evaluation.target_academic_level,
            effective_now=effective_now,
            evidence_keys=evaluation.guard_c.evidence_keys,
            is_canonical=False,
            rationale=evaluation.explanation,
        )
