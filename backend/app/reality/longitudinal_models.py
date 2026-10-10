"""Longitudinal Reality Subsystem Contracts & Temporal DTOs (Phase 8C.1).

Constitutional Invariants Enforced:
- Lock 1 & Lock 8: Decoupled TemporalPosition enum (FUTURE, IN_WINDOW, PAST)
  independent of epistemic grounding; single authoritative effective_now representation.
- Lock 5: Path-invariant advancement specification.
- Lock 9: Monotonic time invariant (effective_now_new >= effective_now_old).
- Lock 12: Atomic advancement contract (TimeAdvanceRequest validates before commit).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator


# =============================================================================
# Temporal Position (Decoupled from Epistemic Grounding)
# =============================================================================

class TemporalPosition(str, Enum):
    """Categorical temporal position relative to the authoritative clock effective_now.

    Constitutional Invariant (Lock 1):
    TemporalPosition represents physical calendar placement relative to effective_now,
    completely decoupled from EpistemicGrounding.
    - FUTURE: Window start has not been reached (T_now < interval.earliest_start).
    - IN_WINDOW: Currently inside window (interval.earliest_start <= T_now <= interval.latest_end).
    - PAST: Window end has elapsed (T_now > interval.latest_end).
    PAST does NOT imply verified history; an elapsed unverified projection is PAST + UNKNOWN.
    """

    FUTURE = "FUTURE"
    IN_WINDOW = "IN_WINDOW"
    PAST = "PAST"


# =============================================================================
# Clock Advance DTOs
# =============================================================================

class TimeAdvanceRequest(BaseModel):
    """Immutable request specification for advancing the authoritative life clock.

    Constitutional Invariants:
    - Lock 9: Monotonic advancement. advance_duration must be >= 0;
      target_time must not retroactively precede the current clock time.
    - Lock 12: Atomic evaluation. The request specifies intent; it is validated
      against the captured old clock state before any time is mutated.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    target_time: Optional[datetime] = Field(
        default=None,
        description="Explicit target UTC datetime to advance to. Mutually exclusive with advance_duration.",
    )
    advance_duration: Optional[timedelta] = Field(
        default=None,
        description="Relative duration to advance clock by. Mutually exclusive with target_time.",
    )
    reason: str = Field(
        default="MANUAL_STEP",
        description="Auditable operational reason for temporal advancement (e.g. 'CALENDAR_ADVANCE', 'SIMULATION_STEP').",
    )

    @model_validator(mode="after")
    def validate_request_specification(self) -> TimeAdvanceRequest:
        """Validate specification completeness, mutual exclusivity, and non-negativity."""
        has_target = self.target_time is not None
        has_duration = self.advance_duration is not None

        if not has_target and not has_duration:
            raise ValueError(
                "TimeAdvanceRequest must specify either 'target_time' or 'advance_duration'."
            )
        if has_target and has_duration:
            raise ValueError(
                "TimeAdvanceRequest cannot specify both 'target_time' and 'advance_duration'. "
                "Specify exactly one."
            )

        # Enforce UTC timezone awareness for explicit target
        if has_target and self.target_time is not None:
            if self.target_time.tzinfo is None:
                raise ValueError(
                    f"target_time '{self.target_time}' must be timezone-aware (UTC)."
                )

        # Enforce non-negative relative duration (Lock 9: Monotonic advancement)
        if has_duration and self.advance_duration is not None:
            if self.advance_duration < timedelta(0):
                raise ValueError(
                    f"advance_duration '{self.advance_duration}' cannot be negative. "
                    "Time cannot move backwards under standard advance (Lock 9)."
                )

        return self


class TimeAdvanceResult(BaseModel):
    """Immutable audit outcome of an authoritative clock advancement operation.

    Constitutional Invariants:
    - Lock 5: Path-invariant audit result.
    - Lock 12: Atomic advancement outcome. On failure, effective_now_new == effective_now_old
      and success is False.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    effective_now_old: datetime = Field(
        ...,
        description="Captured authoritative clock time prior to the advancement attempt.",
    )
    effective_now_new: datetime = Field(
        ...,
        description="Authoritative clock time resulting from the operation.",
    )
    elapsed_duration: timedelta = Field(
        ...,
        description="Actual duration advanced (effective_now_new - effective_now_old).",
    )
    reason: str = Field(
        ...,
        description="Operational rationale associated with the advance request.",
    )
    success: bool = Field(
        default=True,
        description="True if advancement succeeded and passed all monotonic invariants.",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Detailed failure reason if advancement was rejected.",
    )


# =============================================================================
# Clock Protocol
# =============================================================================

@runtime_checkable
class LifeClockProtocol(Protocol):
    """Protocol for authoritative life simulation clock providers (Lock 8)."""

    @property
    def effective_now(self) -> datetime:
        """Return the current authoritative simulation time as a timezone-aware UTC datetime."""
        ...

    def now(self) -> datetime:
        """Return the current authoritative simulation time (alias for effective_now)."""
        ...

    def advance(self, request: TimeAdvanceRequest) -> TimeAdvanceResult:
        """Atomically advance the authoritative clock according to request specification."""
        ...

    def advance_by(self, duration: timedelta, reason: str = "MANUAL_STEP") -> TimeAdvanceResult:
        """Convenience method to advance clock by relative duration."""
        ...

    def advance_to(self, target_time: datetime, reason: str = "CALENDAR_ADVANCE") -> TimeAdvanceResult:
        """Convenience method to advance clock to absolute target time."""
        ...
