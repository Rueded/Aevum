"""Longitudinal Life Progression Coordinator (Phase 8C.5).

Orchestration Step C4: Bridges Phase 8C.1–8C.4 components with the per-turn
reality pipeline. Coordinates:
- Authoritative Life Clock (effective_now)
- Derived Age (pure mathematical calculation, zero set_fact writes)
- Calendar Boundary Detection (deterministic order)
- Guarded Transition Engine (three-layer guard, non-canonical signals)
- Milestone Lapse & Trajectory Realignment (advisory signals, Lapsed != Deleted)

Constitutional Invariants Enforced:
- Lock 1: Anti-Magical-Promotion (PROJECTED + time passage != CANONICAL).
- Lock 2: Derived temporal age view (identity.birth_date -> derived age; zero set_fact).
- Lock 3: Three-layer guard (calendar eligibility != personal transition).
- Lock 4 & Permanent Lock: Advisory lapse (Lapsed != Deleted, zero candidate deletion).
- Lock 7: Canonical mutation singularity (zero canonical writes, zero token minting).
- Lock 8: Singular authoritative life clock holding effective_now.
- Lock 10 & 11: Deterministic boundary ordering; world calendar != personal reality.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field

from app.character.core_models import CharacterCore
from app.reality.authoritative_clock import AuthoritativeLifeClock
from app.reality.calendar_boundary_engine import (
    CalendarBoundaryDetector,
    CalendarBoundaryEvent,
    calendar_age,
)
from app.reality.candidate_models import CandidateHypothesis
from app.reality.guarded_transition_engine import (
    GuardedTransitionEngine,
    LifeStateTransitionEvaluation,
    LifeStateTransitionSignal,
    TransitionEvaluationStatus,
)
from app.reality.milestone_lapse_engine import (
    MilestoneEvaluationRecord,
    MilestoneLapseEngine,
    ProjectedMilestoneStatus,
    TemporalLapseSignal,
    TrajectoryRealignmentResult,
)
from app.reality.temporal_models import (
    Canonicality,
    EpistemicGrounding,
    LifeStage,
    TemporalGranularity,
    TemporalHorizon,
    TemporalInterval,
)
from app.reality.trajectory_engine import LifeTrajectory

logger = logging.getLogger(__name__)


# =============================================================================
# Evaluation Status & Results DTO
# =============================================================================


class LongitudinalEvaluationStatus(str, Enum):
    """Categorical availability status of the longitudinal evaluation."""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class LongitudinalCoordinatorResult(BaseModel):
    """Immutable result of longitudinal life progression coordination for a turn.

    Constitutional Invariants:
    - Zero canonical mutation authority (Lock 7).
    - Lapsed candidates and trajectories are non-canonical ephemeral signals (Lock 4).
    - derived_age is a pure mathematical view; identity.birth_date is canonical (Lock 2).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_status: LongitudinalEvaluationStatus = Field(
        default=LongitudinalEvaluationStatus.AVAILABLE,
        description="Whether evaluation succeeded or degraded to UNAVAILABLE.",
    )
    effective_now: datetime = Field(
        ...,
        description="Authoritative UTC timestamp used for all evaluations (Lock 8).",
    )
    derived_age: Optional[int] = Field(
        default=None,
        description="Pure derived integer age from identity.birth_date (Lock 2: zero set_fact).",
    )
    detected_boundaries: tuple[CalendarBoundaryEvent, ...] = Field(
        default_factory=tuple,
        description="Calendar boundary events crossed since last evaluation.",
    )
    transition_evaluations: tuple[LifeStateTransitionEvaluation, ...] = Field(
        default_factory=tuple,
        description="Guarded transition evaluations (Guard A + B + C).",
    )
    transition_signals: tuple[LifeStateTransitionSignal, ...] = Field(
        default_factory=tuple,
        description="Advisory non-canonical transition signals (is_canonical=False).",
    )
    milestone_evaluations: tuple[MilestoneEvaluationRecord, ...] = Field(
        default_factory=tuple,
        description="Evaluated milestone progressions under effective_now (Lock 1).",
    )
    candidate_lapse_signals: tuple[TemporalLapseSignal, ...] = Field(
        default_factory=tuple,
        description="Advisory temporal lapse signals for candidates (Lock 4: Lapsed != Deleted).",
    )
    realignment_result: Optional[TrajectoryRealignmentResult] = Field(
        default=None,
        description="Realignment result segregating active vs lapsed trajectories.",
    )
    temporally_lapsed_candidate_ids: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Candidate IDs whose time window elapsed; excluded from active competition (Lapsed != Deleted).",
    )
    evaluation_error: Optional[str] = Field(
        default=None,
        description="Error detail if degraded to UNAVAILABLE.",
    )

    def to_context_dict(self) -> dict[str, Any]:
        """Produce pure dict for serialization in RealityContextBuilder."""
        return {
            "effective_now_iso": self.effective_now.isoformat(),
            "derived_age": self.derived_age,
            "calendar_events": [
                {
                    "event_type": b.event_type.value,
                    "boundary_date": b.boundary_date.isoformat(),
                }
                for b in self.detected_boundaries
            ],
            "transition_signals": [
                {
                    "target_stage": s.target_stage.value,
                    "source_stage": s.source_stage.value,
                    "rationale": s.rationale,
                    "is_canonical": s.is_canonical,
                }
                for s in self.transition_signals
            ],
            "candidate_lapses": [
                {
                    "slot_name": s.slot_name,
                    "candidate_id": s.candidate_id,
                    "is_advisory": s.is_advisory,
                }
                for s in self.candidate_lapse_signals
            ],
            "lapsed_trajectories_count": (
                len(self.realignment_result.lapsed_trajectories)
                if self.realignment_result is not None
                else 0
            ),
        }


# =============================================================================
# Longitudinal Coordinator
# =============================================================================


class LongitudinalCoordinator:
    """Coordinates longitudinal progression components during Step C4 of reality orchestration.

    Guarantees:
    1. Single clock authority: Reads effective_now from AuthoritativeLifeClock (Lock 8).
    2. Pure age derivation: Derives calendar_age from birth_date; zero set_fact calls (Lock 2).
    3. Three-layer guard: Transitions require Guard A + B + C; calendar eligibility alone
       never promotes (Lock 3).
    4. Advisory lapse & Lapsed != Deleted: Lapsed candidates emit advisory signals and are excluded
       from active competition, but NEVER deleted from candidate persistence (Lock 4).
    5. Singular canonical mutation authority: BiographyPromotionService alone mutates core;
       LongitudinalCoordinator NEVER writes to canonical state (Lock 7).
    """

    def __init__(
        self,
        clock: Optional[AuthoritativeLifeClock] = None,
        boundary_detector: Optional[CalendarBoundaryDetector] = None,
        transition_engine: Optional[GuardedTransitionEngine] = None,
        lapse_engine: Optional[MilestoneLapseEngine] = None,
    ) -> None:
        self._clock = clock or AuthoritativeLifeClock()
        self._boundary_detector = boundary_detector or CalendarBoundaryDetector()
        self._transition_engine = transition_engine or GuardedTransitionEngine()
        self._lapse_engine = lapse_engine or MilestoneLapseEngine()
        self._last_evaluated_now: Optional[datetime] = None

    @property
    def clock(self) -> AuthoritativeLifeClock:
        """Access the singular authoritative life clock (Lock 8)."""
        return self._clock

    def coordinate_turn(
        self,
        core: Optional[CharacterCore] = None,
        active_candidates: Sequence[CandidateHypothesis] = (),
        trajectories: Sequence[LifeTrajectory] = (),
        projected_milestones: Sequence[Tuple[str, datetime, datetime]] = (),
        target_transition_spec: Optional[dict[str, Any]] = None,
        last_evaluated_now: Optional[datetime] = None,
    ) -> LongitudinalCoordinatorResult:
        """Execute longitudinal reality evaluation for a turn.

        Pure and non-mutating:
        - Reads effective_now from clock.
        - Calculates derived age if identity.birth_date is present.
        - Detects calendar boundaries crossed.
        - Evaluates target life transitions if requested (strictly non-canonical).
        - Scans candidate hypotheses for temporal lapse.
        - Realigns prospective trajectories.
        - Evaluates projected milestones (Lock 1 Anti-Magical-Promotion).

        Degrades gracefully to UNAVAILABLE on unhandled exceptions (zero false exclusions).
        """
        effective_now = self._clock.effective_now
        try:
            # 1. Derived Age View (Lock 2)
            derived_age: Optional[int] = None
            birth_date_val: Optional[date] = None

            if core is not None and core.facts:
                birth_fact = core.facts.get("identity.birth_date")
                if birth_fact is not None and birth_fact.value is not None:
                    raw_val = birth_fact.value
                    if isinstance(raw_val, date) and not isinstance(raw_val, datetime):
                        birth_date_val = raw_val
                    elif isinstance(raw_val, datetime):
                        birth_date_val = raw_val.date()
                    elif isinstance(raw_val, str):
                        try:
                            birth_date_val = date.fromisoformat(raw_val.strip())
                        except ValueError:
                            birth_date_val = None

                    if birth_date_val is not None:
                        derived_age = calendar_age(birth_date_val, effective_now)

            # 2. Calendar Boundary Detection (Lock 10, 11)
            detected_boundaries: tuple[CalendarBoundaryEvent, ...] = ()
            prev_time = last_evaluated_now or self._last_evaluated_now
            if prev_time is not None and prev_time < effective_now:
                detected_boundaries = self._boundary_detector.detect_boundaries(
                    effective_now_old=prev_time,
                    effective_now_new=effective_now,
                    birth_date=birth_date_val,
                )
            self._last_evaluated_now = effective_now

            # 3. Guarded Transition Evaluation (Lock 3, Lock 7)
            transition_evaluations: list[LifeStateTransitionEvaluation] = []
            transition_signals: list[LifeStateTransitionSignal] = []

            if target_transition_spec is not None:
                source_stage = target_transition_spec.get("source_stage") or target_transition_spec.get("current_stage")
                source_start_date = target_transition_spec.get("source_start_date") or target_transition_spec.get("current_stage_start_date")
                target_stage = target_transition_spec["target_stage"]
                source_academic_level = target_transition_spec.get("source_academic_level")
                target_academic_level = target_transition_spec.get("target_academic_level")
                is_predecessor_settled = target_transition_spec.get("is_predecessor_settled", True)
                progression_evidence = target_transition_spec.get("progression_evidence") or target_transition_spec.get("provided_evidence_items")
                minimum_duration_days = target_transition_spec.get("minimum_duration_days") or target_transition_spec.get("required_days", 365)
                is_on_leave_or_hold = target_transition_spec.get("is_on_leave_or_hold") or target_transition_spec.get("is_academic_hold", False)
                char_id = target_transition_spec.get("character_id", "aevum")

                eval_res = self._transition_engine.evaluate_transition(
                    source_stage=source_stage,
                    source_start_date=source_start_date,
                    effective_now=effective_now,
                    target_stage=target_stage,
                    source_academic_level=source_academic_level,
                    target_academic_level=target_academic_level,
                    is_predecessor_settled=is_predecessor_settled,
                    progression_evidence=progression_evidence,
                    minimum_duration_days=minimum_duration_days,
                    is_on_leave_or_hold=is_on_leave_or_hold,
                    character_id=char_id,
                )
                transition_evaluations.append(eval_res)

                if eval_res.status == TransitionEvaluationStatus.TRANSITION_SUPPORTED:
                    signal = self._transition_engine.emit_transition_signal(
                        evaluation=eval_res,
                        effective_now=effective_now,
                    )
                    transition_signals.append(signal)

            # 4. Candidate Lapse Detection (Lock 4 & Permanent Lock: Lapsed != Deleted)
            candidate_lapse_signals: tuple[TemporalLapseSignal, ...] = ()
            temporally_lapsed_candidate_ids: tuple[str, ...] = ()

            if active_candidates:
                candidate_lapse_signals = self._lapse_engine.detect_candidate_lapses(
                    candidates=active_candidates,
                    effective_now=effective_now,
                )
                temporally_lapsed_candidate_ids = tuple(
                    sig.candidate_id for sig in candidate_lapse_signals
                )

            # 5. Trajectory Realignment
            realignment_res: Optional[TrajectoryRealignmentResult] = None
            if trajectories:
                realignment_res = self._lapse_engine.realign_trajectories(
                    trajectories=trajectories,
                    effective_now=effective_now,
                )

            # 6. Milestone Evaluations (Lock 1: Anti-Magical-Promotion)
            milestone_evaluations: list[MilestoneEvaluationRecord] = []
            for milestone_spec in projected_milestones:
                m_id, m_start, m_end = milestone_spec[:3]
                m_interval = TemporalInterval.create_exact(start=m_start.date(), end=m_end.date())
                m_eval = self._lapse_engine.evaluate_milestone(
                    node_id=m_id,
                    label=f"Milestone_{m_id}",
                    interval=m_interval,
                    effective_now=effective_now,
                    epistemic_grounding=EpistemicGrounding.PROJECTED,
                    canonicality=Canonicality.NON_CANONICAL,
                    has_evidence=False,
                )
                milestone_evaluations.append(m_eval)

            return LongitudinalCoordinatorResult(
                evaluation_status=LongitudinalEvaluationStatus.AVAILABLE,
                effective_now=effective_now,
                derived_age=derived_age,
                detected_boundaries=detected_boundaries,
                transition_evaluations=tuple(transition_evaluations),
                transition_signals=tuple(transition_signals),
                milestone_evaluations=tuple(milestone_evaluations),
                candidate_lapse_signals=candidate_lapse_signals,
                realignment_result=realignment_res,
                temporally_lapsed_candidate_ids=temporally_lapsed_candidate_ids,
            )

        except Exception as exc:
            logger.error(
                "LongitudinalCoordinator.coordinate_turn failed: %s. "
                "Degrading to UNAVAILABLE (zero false exclusions).",
                exc,
            )
            return LongitudinalCoordinatorResult(
                evaluation_status=LongitudinalEvaluationStatus.UNAVAILABLE,
                effective_now=effective_now,
                evaluation_error=str(exc),
            )
