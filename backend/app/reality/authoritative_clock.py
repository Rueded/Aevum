"""Authoritative Life Clock Implementation (Phase 8C.1).

Constitutional Invariants Enforced:
- Lock 5: Path-invariant advancement (Advance(T0->Tn) == Advance(T0->T1->...->Tn)).
- Lock 8: Singular authoritative life clock holding effective_now.
- Lock 9: Monotonic time invariant (effective_now_new >= effective_now_old).
- Lock 12: Atomic advancement (validation against captured old state; failure leaves
  effective_now completely unmodified).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.reality.longitudinal_models import (
    LifeClockProtocol,
    TimeAdvanceRequest,
    TimeAdvanceResult,
)


class MonotonicTimeViolationError(ValueError):
    """Raised when an advancement request violates the Monotonic Time Invariant (Lock 9)."""
    pass


class AuthoritativeLifeClock(LifeClockProtocol):
    """Singular authoritative clock engine for longitudinal life progression (Lock 8).

    Guarantees:
    1. Single authority: effective_now is the sole time anchor for all reality modules.
    2. Monotonicity: Time strictly advances forward; retroactive adjustments are rejected.
    3. Atomicity (Lock 12): Requests are validated against old state before commit;
       on failure, clock state is untouched.
    4. Path-Invariance (Lock 5): Any sequence of discrete steps summing to duration D
       yields the exact same final clock state as a single step of duration D.
    """

    def __init__(self, initial_time: Optional[datetime] = None) -> None:
        """Initialize authoritative clock with timezone-aware UTC datetime."""
        if initial_time is None:
            self._effective_now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        else:
            if initial_time.tzinfo is None:
                self._effective_now = initial_time.replace(tzinfo=timezone.utc)
            else:
                self._effective_now = initial_time.astimezone(timezone.utc)

    @property
    def effective_now(self) -> datetime:
        """Return the current authoritative simulation time as UTC datetime."""
        return self._effective_now

    def now(self) -> datetime:
        """Alias for effective_now to conform to standard clock protocols."""
        return self._effective_now

    def advance(
        self,
        request: TimeAdvanceRequest,
        raise_on_error: bool = False,
    ) -> TimeAdvanceResult:
        """Atomically advance the authoritative clock according to request specification (Lock 12).

        Args:
            request: Immutable advance specification.
            raise_on_error: If True, raises exception on failure; otherwise returns
              TimeAdvanceResult(success=False, error_message=...).

        Returns:
            TimeAdvanceResult capturing audit metrics and success/failure status.
        """
        # Step 1: Capture old clock state before any evaluation (Lock 10 & Lock 12)
        effective_now_old = self._effective_now

        try:
            # Step 2: Compute candidate target time
            if request.target_time is not None:
                candidate_target = request.target_time
                if candidate_target.tzinfo is None:
                    candidate_target = candidate_target.replace(tzinfo=timezone.utc)
                else:
                    candidate_target = candidate_target.astimezone(timezone.utc)
            elif request.advance_duration is not None:
                candidate_target = effective_now_old + request.advance_duration
            else:
                raise ValueError("TimeAdvanceRequest must specify target_time or advance_duration.")

            # Step 3: Enforce Monotonic Time Invariant (Lock 9)
            if candidate_target < effective_now_old:
                raise MonotonicTimeViolationError(
                    f"Monotonic Time Invariant (Lock 9) violated: Cannot advance backwards from "
                    f"'{effective_now_old.isoformat()}' to retroactive time '{candidate_target.isoformat()}'. "
                    f"Delta is {candidate_target - effective_now_old}."
                )

            # Step 4: Commit new state only after all validations pass (Atomic Advance - Lock 12)
            self._effective_now = candidate_target
            elapsed = self._effective_now - effective_now_old

            return TimeAdvanceResult(
                effective_now_old=effective_now_old,
                effective_now_new=self._effective_now,
                elapsed_duration=elapsed,
                reason=request.reason,
                success=True,
            )

        except Exception as exc:
            # Step 5: On any failure, clock state is strictly unchanged (Lock 12)
            assert self._effective_now == effective_now_old, "Invariant violation: partial clock advancement detected!"

            if raise_on_error:
                raise

            return TimeAdvanceResult(
                effective_now_old=effective_now_old,
                effective_now_new=effective_now_old,
                elapsed_duration=timedelta(0),
                reason=request.reason,
                success=False,
                error_message=str(exc),
            )

    def advance_by(
        self,
        duration: timedelta,
        reason: str = "MANUAL_STEP",
        raise_on_error: bool = False,
    ) -> TimeAdvanceResult:
        """Convenience method to advance clock by relative timedelta."""
        request = TimeAdvanceRequest(advance_duration=duration, reason=reason)
        return self.advance(request, raise_on_error=raise_on_error)

    def advance_to(
        self,
        target_time: datetime,
        reason: str = "CALENDAR_ADVANCE",
        raise_on_error: bool = False,
    ) -> TimeAdvanceResult:
        """Convenience method to advance clock to explicit target UTC datetime."""
        request = TimeAdvanceRequest(target_time=target_time, reason=reason)
        return self.advance(request, raise_on_error=raise_on_error)

    def reset_for_simulation_fixture(
        self,
        new_initial_time: datetime,
        is_simulation_fixture: bool = False,
    ) -> None:
        """Explicitly reset clock state for testing fixtures ONLY.

        Standard production advances must strictly use advance() to preserve
        monotonicity and audit logging.
        """
        if not is_simulation_fixture:
            raise PermissionError(
                "AuthoritativeLifeClock.reset_for_simulation_fixture is strictly restricted "
                "to automated testing fixtures. Production clock resets are forbidden (Lock 9)."
            )
        if new_initial_time.tzinfo is None:
            self._effective_now = new_initial_time.replace(tzinfo=timezone.utc)
        else:
            self._effective_now = new_initial_time.astimezone(timezone.utc)
