"""Milestone Lapse & Trajectory Realignment Engine (Phase 8C.4).

Constitutional Invariants & Guardrails Enforced:
- Lock 1 & Anti-Magical-Promotion Invariant:
  PROJECTED + time elapsed != CANONICAL.
  When an unverified projected milestone's time window has elapsed into the past,
  it transitions strictly to ELAPSED_UNVERIFIED. It NEVER automatically promotes to
  CONFIRMED_HISTORICAL or CANONICAL without explicit observation or user confirmation.
- Lock 4: Candidate Lapse Boundary.
  8C.4 detects when a candidate's temporal window has elapsed and emits read-only
  TemporalLapseSignal. 8C NEVER directly mutates the candidate database table.
- Trajectory Realignment Invariant:
  Realignment prunes elapsed unconfirmed prospective pathways from the active set;
  it NEVER fabricates an alternative personal history to fill the elapsed void.
- Lock 7: Canonical Mutation Singularity.
  Zero set_fact() calls, zero database writes, zero LLM integration.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from enum import Enum
import re
from typing import Any, Optional, Sequence
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.reality.longitudinal_models import TemporalPosition
from app.reality.temporal_models import (
    Canonicality,
    EpistemicGrounding,
    LifeStage,
    TemporalGranularity,
    TemporalHorizon,
    TemporalInterval,
)
from app.reality.trajectory_engine import (
    LifeTrajectory,
    TrajectoryStatus,
)


# =============================================================================
# Categorical Milestone Status Enum
# =============================================================================

class ProjectedMilestoneStatus(str, Enum):
    """Categorical status of a temporal milestone or projection evaluated at effective_now."""

    PENDING_FUTURE = "PENDING_FUTURE"
    """Window start has not been reached (T_now < interval.earliest_start)."""

    DUE_IN_WINDOW = "DUE_IN_WINDOW"
    """Currently inside expected window, but unobserved / unconfirmed.
    Remains non-canonical projection; does not imply in-progress fact."""

    ELAPSED_UNVERIFIED = "ELAPSED_UNVERIFIED"
    """Expected completion window has elapsed, and NO explicit observation occurred.
    CRITICAL: Never automatically promoted to CANONICAL. Represents an elapsed expectation."""

    EVIDENCED_IN_PROGRESS = "EVIDENCED_IN_PROGRESS"
    """Inside expected window, AND explicit observation/evidence corroborates activity."""

    CONFIRMED_HISTORICAL = "CONFIRMED_HISTORICAL"
    """Window has elapsed, AND explicit observation or user confirmation grounds it."""


# =============================================================================
# Evaluation Record & Audit DTOs
# =============================================================================

class MilestoneEvaluationRecord(BaseModel):
    """Immutable audit record evaluating a milestone against authoritative clock effective_now."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    milestone_id: str = Field(..., description="Deterministic milestone identifier.")
    label: str = Field(..., description="Descriptive label (e.g. 'Projected Degree Graduation').")
    temporal_position: TemporalPosition = Field(..., description="Physical calendar placement (FUTURE, IN_WINDOW, PAST).")
    epistemic_grounding: EpistemicGrounding = Field(..., description="Original grounding classification.")
    status: ProjectedMilestoneStatus = Field(..., description="Resulting milestone progression status.")
    interval: TemporalInterval = Field(..., description="Milestone temporal boundary interval.")
    effective_now: datetime = Field(..., description="Authoritative clock evaluation timestamp.")
    evidence_keys: tuple[str, ...] = Field(default_factory=tuple, description="Corroborating evidence keys, if any.")
    is_canonical: bool = Field(default=False, description="Canonical authority status.")
    explanation: str = Field(..., description="Human-readable audit explanation.")


class TemporalLapseSignal(BaseModel):
    """Immutable advisory signal emitted when a candidate's temporal window has elapsed (Lock 4).

    Constitutional Invariant:
    8C emits this signal to notify the 8A candidate system. 8C NEVER modifies
    the character_candidate_facts database table directly.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    signal_id: str = Field(..., description="Deterministic signal identifier.")
    candidate_id: str = Field(..., description="Target candidate identifier from 8A.")
    slot_name: str = Field(..., description="Target biography slot (e.g. 'education.undergraduate_intake').")
    proposed_value: Any = Field(..., description="The value proposed by the candidate.")
    expired_window_end: date = Field(..., description="Date when the candidate's window elapsed.")
    effective_now: datetime = Field(..., description="Authoritative clock evaluation timestamp.")
    reason: str = Field(default="TIME_WINDOW_ELAPSED", description="Lapse rationale.")
    explanation: str = Field(default="", description="Detailed human-readable explanation.")
    is_advisory: bool = Field(default=True, description="Strictly True; advisory signal only.")


class TrajectoryRealignmentResult(BaseModel):
    """Immutable result of realigning trajectory plurality under longitudinal time advancement."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    effective_now: datetime = Field(..., description="Authoritative clock evaluation timestamp.")
    active_trajectories: tuple[LifeTrajectory, ...] = Field(
        ...,
        description="Trajectories whose forward nodes remain feasible under effective_now.",
    )
    lapsed_trajectories: tuple[LifeTrajectory, ...] = Field(
        ...,
        description="Trajectories whose prospective entry or prerequisite windows elapsed without evidence.",
    )
    elapsed_milestones_count: int = Field(default=0, ge=0, description="Count of elapsed milestones.")
    explanation: str = Field(..., description="Audit summary of the realignment.")


# =============================================================================
# Milestone Lapse & Trajectory Realignment Engine
# =============================================================================

class MilestoneLapseEngine:
    """Pure, stateless engine evaluating milestone evolution, candidate lapses, and trajectory realignment (Phase 8C.4).

    Guarantees:
    1. Anti-Magical-Promotion (Lock 1): An elapsed unverified projection is ELAPSED_UNVERIFIED,
       never CONFIRMED_HISTORICAL or CANONICAL.
    2. Candidate Boundary (Lock 4): Emits TemporalLapseSignal; zero DB writes to candidate tables.
    3. Trajectory Realignment: Prunes elapsed unconfirmed prospective pathways;
       never fabricates alternative personal histories.
    4. Singularity (Lock 7): Zero set_fact() calls.
    """

    @classmethod
    def evaluate_milestone(
        cls,
        node_id: str,
        label: str,
        interval: TemporalInterval,
        epistemic_grounding: EpistemicGrounding,
        effective_now: datetime,
        corroborating_evidence: Optional[Sequence[str]] = None,
        canonicality: Canonicality = Canonicality.NON_CANONICAL,
    ) -> MilestoneEvaluationRecord:
        """Evaluate a temporal node or milestone against authoritative clock effective_now.

        Enforces:
        - FUTURE -> PENDING_FUTURE
        - IN_WINDOW + no evidence -> DUE_IN_WINDOW
        - IN_WINDOW + evidence -> EVIDENCED_IN_PROGRESS
        - PAST + no evidence -> ELAPSED_UNVERIFIED (CRITICAL: Never automatically CANONICAL!)
        - PAST + confirmed evidence -> CONFIRMED_HISTORICAL
        """
        if effective_now.tzinfo is None:
            raise ValueError(f"effective_now '{effective_now}' must be timezone-aware (UTC).")

        now_date = effective_now.date()
        ev_tuple = tuple(corroborating_evidence) if corroborating_evidence else ()
        has_evidence = len(ev_tuple) > 0 or epistemic_grounding in (
            EpistemicGrounding.USER_CONFIRMED,
            EpistemicGrounding.OBSERVED,
        )

        # ---------------------------------------------------------------------
        # 1. Determine Physical Temporal Position
        # ---------------------------------------------------------------------
        if interval.is_unknown():
            pos = TemporalPosition.FUTURE
        elif interval.earliest_start is not None and now_date < interval.earliest_start:
            pos = TemporalPosition.FUTURE
        elif interval.latest_end is not None and now_date > interval.latest_end:
            pos = TemporalPosition.PAST
        else:
            pos = TemporalPosition.IN_WINDOW

        # ---------------------------------------------------------------------
        # 2. Evaluate Status (Decoupled Temporal Position vs Epistemic Grounding)
        # ---------------------------------------------------------------------
        if pos == TemporalPosition.FUTURE:
            status = ProjectedMilestoneStatus.PENDING_FUTURE
            explanation = f"Milestone '{label}' is in the future relative to {now_date}."
            is_canon = False
        elif pos == TemporalPosition.IN_WINDOW:
            if has_evidence:
                status = ProjectedMilestoneStatus.EVIDENCED_IN_PROGRESS
                explanation = f"Milestone '{label}' is active and corroborated by evidence: {ev_tuple}."
                is_canon = canonicality == Canonicality.CANONICAL
            else:
                status = ProjectedMilestoneStatus.DUE_IN_WINDOW
                explanation = f"Milestone '{label}' expected window has arrived, but lacks factual corroboration."
                is_canon = False
        else:  # PAST
            if has_evidence:
                status = ProjectedMilestoneStatus.CONFIRMED_HISTORICAL
                explanation = f"Milestone '{label}' window has elapsed and was confirmed by evidence."
                is_canon = canonicality == Canonicality.CANONICAL or len(ev_tuple) > 0
            else:
                # THE CORE LOCK: Anti-Magical-Promotion!
                status = ProjectedMilestoneStatus.ELAPSED_UNVERIFIED
                explanation = (
                    f"Milestone '{label}' expected window has elapsed ({interval.latest_end}), "
                    f"but ZERO observation/confirmation occurred. Marked as unverified elapsed expectation; "
                    f"NEVER automatically promoted to canonical historical fact."
                )
                is_canon = False

        return MilestoneEvaluationRecord(
            milestone_id=node_id,
            label=label,
            temporal_position=pos,
            epistemic_grounding=epistemic_grounding,
            status=status,
            interval=interval,
            effective_now=effective_now,
            evidence_keys=ev_tuple,
            is_canonical=is_canon,
            explanation=explanation,
        )

    @classmethod
    def detect_candidate_lapses(
        cls,
        candidates: Sequence[Any],
        effective_now: datetime,
    ) -> tuple[TemporalLapseSignal, ...]:
        """Scan candidate hypotheses and emit read-only TemporalLapseSignals for elapsed windows (Lock 4).

        Zero database side-effects: Returns signals only; does NOT mutate candidate records.
        """
        if effective_now.tzinfo is None:
            raise ValueError(f"effective_now '{effective_now}' must be timezone-aware (UTC).")

        now_date = effective_now.date()
        signals: list[TemporalLapseSignal] = []

        for cand in candidates:
            # Extract candidate fields gracefully
            cid = getattr(cand, "candidate_id", None) or getattr(cand, "id", str(uuid.uuid4()))
            slot = getattr(cand, "slot_name", "")
            val = getattr(cand, "proposed_value", None)

            # Check if candidate has a date-bound window
            window_end = cls._extract_candidate_window_end(val, slot)
            if window_end is not None:
                if now_date > window_end:
                    sig_id = f"lapse_{cid}_{now_date.isoformat()}"
                    signals.append(
                        TemporalLapseSignal(
                            signal_id=sig_id,
                            candidate_id=str(cid),
                            slot_name=slot,
                            proposed_value=val,
                            expired_window_end=window_end,
                            effective_now=effective_now,
                            reason="TIME_WINDOW_ELAPSED",
                            explanation=f"Candidate proposed window '{window_end}' elapsed before effective_now '{now_date}'.",
                            is_advisory=True,
                        )
                    )

        return tuple(signals)

    @staticmethod
    def _extract_candidate_window_end(value: Any, slot_name: str) -> Optional[date]:
        """Extract latest completion date for candidate values tied to academic/temporal slots."""
        if value is None:
            return None

        val_str = str(value).strip()

        # Format: "YYYY-MM" (e.g. "2025-10" intake)
        m_ym = re.match(r"^(\d{4})-(\d{2})$", val_str)
        if m_ym:
            y, m = int(m_ym.group(1)), int(m_ym.group(2))
            # Window end is the last day of that month
            import calendar
            last_day = calendar.monthrange(y, m)[1]
            return date(y, m, last_day)

        # Format: "YYYY" (e.g. 2023 SPM year)
        m_y = re.match(r"^(\d{4})$", val_str)
        if m_y:
            y = int(m_y.group(1))
            return date(y, 12, 31)

        # Format: "YYYY-MM-DD"
        m_ymd = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", val_str)
        if m_ymd:
            return date(int(m_ymd.group(1)), int(m_ymd.group(2)), int(m_ymd.group(3)))

        return None

    @classmethod
    def realign_trajectories(
        cls,
        trajectories: Sequence[LifeTrajectory],
        effective_now: datetime,
    ) -> TrajectoryRealignmentResult:
        """Realign trajectory plurality by identifying pathways whose prospective windows have elapsed.

        Guarantees:
        - Identifies pathways whose entry/prerequisite nodes were unconfirmed and elapsed.
        - Prunes them into lapsed_trajectories without fabricating replacement histories.
        """
        if effective_now.tzinfo is None:
            raise ValueError(f"effective_now '{effective_now}' must be timezone-aware (UTC).")

        now_date = effective_now.date()
        active: list[LifeTrajectory] = []
        lapsed: list[LifeTrajectory] = []
        elapsed_milestones = 0

        for traj in trajectories:
            has_unverified_elapsed_node = False

            for node in traj.nodes:
                # Check if this node is projected and its window has passed
                if node.epistemic_grounding == EpistemicGrounding.PROJECTED:
                    if node.interval.latest_end is not None and now_date > node.interval.latest_end:
                        has_unverified_elapsed_node = True
                        elapsed_milestones += 1

            if has_unverified_elapsed_node:
                # This pathway's prospective timeline elapsed without evidence
                lapsed.append(traj)
            else:
                active.append(traj)

        explanation = (
            f"Realigned {len(trajectories)} trajectories at {now_date.isoformat()}: "
            f"{len(active)} active, {len(lapsed)} lapsed due to elapsed unverified windows."
        )

        return TrajectoryRealignmentResult(
            effective_now=effective_now,
            active_trajectories=tuple(active),
            lapsed_trajectories=tuple(lapsed),
            elapsed_milestones_count=elapsed_milestones,
            explanation=explanation,
        )
