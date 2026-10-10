"""Phase 8C.1: Life Clock & Temporal Advancement Contracts Test Suite.

Validates the 5 Core Acceptance Questions & Constitutional Locks:
1. Time Advancement ($T_0 \\to T_1$) via relative duration and absolute target.
2. Monotonicity & Anti-Retroactivity ($T_1 \\to T_0$) rejection (Lock 9).
3. Path-Invariance (Lock 5): Advance(T0->T365) == Advance(T0->T1->...->T365).
4. Atomic Advancement (Lock 12): Failure leaves clock state strictly unmodified.
5. Single Clock Authority & AST Audit (Lock 8): Zero un-injected datetime.now() or
   date.today() in 8C.1 modules; zero DB/network/LLM/mutation imports.
"""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
import pathlib
import pytest
from pydantic import ValidationError

from app.reality.authoritative_clock import (
    AuthoritativeLifeClock,
    MonotonicTimeViolationError,
)
from app.reality.longitudinal_models import (
    LifeClockProtocol,
    TemporalPosition,
    TimeAdvanceRequest,
    TimeAdvanceResult,
)


class TestPhase8C1ClockContracts:
    """Acceptance test suite for Phase 8C.1 Clock and Temporal Advancement Contracts."""

    # -------------------------------------------------------------------------
    # 1. TemporalPosition & DTO Contract Immutability
    # -------------------------------------------------------------------------

    def test_temporal_position_enum_decoupled_from_epistemics(self):
        """Verify TemporalPosition has exactly 3 calendar states independent of grounding."""
        assert set(TemporalPosition) == {
            TemporalPosition.FUTURE,
            TemporalPosition.IN_WINDOW,
            TemporalPosition.PAST,
        }
        for pos in TemporalPosition:
            assert isinstance(pos.value, str)

    def test_time_advance_request_mutual_exclusivity_and_validation(self):
        """Verify TimeAdvanceRequest enforces mutual exclusivity and non-negativity."""
        now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

        # 1. Must specify either target_time or advance_duration
        with pytest.raises(ValidationError, match="must specify either 'target_time' or 'advance_duration'"):
            TimeAdvanceRequest()

        # 2. Cannot specify both
        with pytest.raises(ValidationError, match="cannot specify both"):
            TimeAdvanceRequest(
                target_time=now + timedelta(days=1),
                advance_duration=timedelta(days=1),
            )

        # 3. Target time must be timezone-aware (UTC)
        naive_dt = datetime(2026, 1, 2, 12, 0)
        with pytest.raises(ValidationError, match="must be timezone-aware"):
            TimeAdvanceRequest(target_time=naive_dt)

        # 4. Advance duration cannot be negative (Lock 9: Monotonicity at request level)
        with pytest.raises(ValidationError, match="cannot be negative"):
            TimeAdvanceRequest(advance_duration=timedelta(days=-1))

        # 5. Frozen and extra="forbid"
        valid_req = TimeAdvanceRequest(advance_duration=timedelta(days=5), reason="TEST")
        with pytest.raises(ValidationError):
            valid_req.reason = "MUTATED"
        with pytest.raises(ValidationError):
            TimeAdvanceRequest(advance_duration=timedelta(days=5), rogue_field=123)

    def test_time_advance_result_immutability(self):
        """Verify TimeAdvanceResult is frozen with extra='forbid'."""
        t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        t1 = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)
        res = TimeAdvanceResult(
            effective_now_old=t0,
            effective_now_new=t1,
            elapsed_duration=t1 - t0,
            reason="STEP",
            success=True,
        )
        assert res.success is True
        assert res.elapsed_duration == timedelta(days=1)
        with pytest.raises(ValidationError):
            res.success = False

    # -------------------------------------------------------------------------
    # 2. Acceptance Question 1: Time Can Advance (T0 -> T1)
    # -------------------------------------------------------------------------

    def test_clock_advancement_by_duration_and_target(self):
        """Question 1: Verify clock advances accurately via duration and explicit target."""
        t0 = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        clock = AuthoritativeLifeClock(initial_time=t0)
        assert clock.effective_now == t0
        assert clock.now() == t0

        # Advance by 15 days
        res1 = clock.advance_by(timedelta(days=15), reason="SUMMER_PROGRESSION")
        assert res1.success is True
        assert res1.effective_now_old == t0
        assert res1.effective_now_new == datetime(2026, 6, 16, 0, 0, 0, tzinfo=timezone.utc)
        assert res1.elapsed_duration == timedelta(days=15)
        assert clock.effective_now == res1.effective_now_new

        # Advance to explicit target
        target = datetime(2026, 10, 1, 9, 0, 0, tzinfo=timezone.utc)
        res2 = clock.advance_to(target, reason="OCTOBER_INTAKE")
        assert res2.success is True
        assert res2.effective_now_old == datetime(2026, 6, 16, 0, 0, 0, tzinfo=timezone.utc)
        assert res2.effective_now_new == target
        assert clock.effective_now == target

    # -------------------------------------------------------------------------
    # 3. Acceptance Question 2: Monotonicity & Rejection of Illegal Retroactivity
    # -------------------------------------------------------------------------

    def test_clock_rejects_retroactive_advancement(self):
        """Question 2: Verify clock strictly rejects moving backwards (Lock 9)."""
        t0 = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        clock = AuthoritativeLifeClock(initial_time=t0)

        # Attempt to advance to yesterday
        past_target = t0 - timedelta(days=1)
        req = TimeAdvanceRequest(target_time=past_target, reason="ILLEGAL_REWIND")

        # 1. Non-raising advance returns success=False
        res = clock.advance(req, raise_on_error=False)
        assert res.success is False
        assert "Monotonic Time Invariant" in (res.error_message or "")
        assert clock.effective_now == t0

        # 2. Strict advance raises MonotonicTimeViolationError
        with pytest.raises(MonotonicTimeViolationError, match="Monotonic Time Invariant"):
            clock.advance(req, raise_on_error=True)

        assert clock.effective_now == t0

    # -------------------------------------------------------------------------
    # 4. Acceptance Question 3: Path-Invariance (Advance(T0->Tn) == Sum(steps))
    # -------------------------------------------------------------------------

    def test_clock_path_invariance_365_days(self):
        """Question 3: Advance(T0->T365) in 1 jump vs 365 daily steps yields identical state (Lock 5)."""
        t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        # Clock A: 1 large jump of 365 days
        clock_a = AuthoritativeLifeClock(initial_time=t0)
        res_a = clock_a.advance_by(timedelta(days=365), reason="ANNUAL_JUMP")

        # Clock B: 365 discrete 1-day jumps
        clock_b = AuthoritativeLifeClock(initial_time=t0)
        for d in range(365):
            res_b_step = clock_b.advance_by(timedelta(days=1), reason=f"DAY_{d+1}")
            assert res_b_step.success is True

        # Assert absolute semantic and mathematical equivalence
        assert clock_a.effective_now == clock_b.effective_now
        assert clock_a.effective_now == datetime(2027, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert res_a.elapsed_duration == timedelta(days=365)

    def test_clock_path_invariance_irregular_micro_intervals(self):
        """Verify path invariance holds over irregular durations (hours, minutes, seconds)."""
        t0 = datetime(2026, 3, 15, 8, 30, 0, tzinfo=timezone.utc)
        clock_single = AuthoritativeLifeClock(initial_time=t0)
        clock_multi = AuthoritativeLifeClock(initial_time=t0)

        intervals = [
            timedelta(hours=3, minutes=15),
            timedelta(days=2, hours=7, seconds=45),
            timedelta(minutes=50, seconds=15),
            timedelta(days=10),
        ]
        total_duration = sum(intervals, timedelta(0))

        clock_single.advance_by(total_duration, reason="SINGLE_HOP")

        for inv in intervals:
            clock_multi.advance_by(inv, reason="MULTI_HOP")

        assert clock_single.effective_now == clock_multi.effective_now

    # -------------------------------------------------------------------------
    # 5. Acceptance Question 4: Atomic Clock Advancement (Lock 12)
    # -------------------------------------------------------------------------

    def test_atomic_advancement_failure_leaves_clock_unmodified(self):
        """Question 4: Validation failure leaves clock strictly unmodified (Lock 12)."""
        t0 = datetime(2026, 9, 26, 10, 0, 0, tzinfo=timezone.utc)
        clock = AuthoritativeLifeClock(initial_time=t0)

        # Craft an invalid retroactive target
        bad_req = TimeAdvanceRequest(
            target_time=t0 - timedelta(hours=5),
            reason="BACKWARDS_ATTEMPT",
        )

        res = clock.advance(bad_req, raise_on_error=False)

        assert res.success is False
        assert res.effective_now_old == t0
        assert res.effective_now_new == t0
        assert res.elapsed_duration == timedelta(0)
        assert clock.effective_now == t0  # Pristine state preserved

    # -------------------------------------------------------------------------
    # 6. Reset Boundary Protection
    # -------------------------------------------------------------------------

    def test_reset_forbidden_without_explicit_fixture_flag(self):
        """Verify reset_for_simulation_fixture is guarded against accidental production use."""
        clock = AuthoritativeLifeClock()
        new_time = datetime(2025, 1, 1, tzinfo=timezone.utc)

        with pytest.raises(PermissionError, match="strictly restricted to automated testing fixtures"):
            clock.reset_for_simulation_fixture(new_time, is_simulation_fixture=False)

        # Allowed with explicit fixture flag
        clock.reset_for_simulation_fixture(new_time, is_simulation_fixture=True)
        assert clock.effective_now == new_time

    # -------------------------------------------------------------------------
    # 7. Acceptance Question 5: AST Singularity & Protocol Conformance Audit
    # -------------------------------------------------------------------------

    def test_protocol_runtime_checkable(self):
        """Verify AuthoritativeLifeClock adheres to LifeClockProtocol."""
        clock = AuthoritativeLifeClock()
        assert isinstance(clock, LifeClockProtocol)

    def test_ast_audit_zero_rogue_clock_calls_in_8c1_modules(self):
        """Question 5: Verify zero un-injected datetime.now() or date.today() in 8C.1 source code."""
        modules_to_audit = [
            pathlib.Path("app/reality/longitudinal_models.py"),
            pathlib.Path("app/reality/authoritative_clock.py"),
        ]

        banned_calls = {"now", "today", "utcnow"}

        for mod_path in modules_to_audit:
            assert mod_path.exists(), f"Module {mod_path} missing"
            tree = ast.parse(mod_path.read_text(encoding="utf-8"))

            for node in ast.walk(tree):
                # Inspect any Call nodes: ban datetime.now(), datetime.utcnow(), date.today()
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        attr_name = node.func.attr
                        # If calling now/today/utcnow directly on a datetime or date object
                        if attr_name in banned_calls:
                            # Allow definition of def now(self):
                            # But forbid calling datetime.now() or date.today()
                            if isinstance(node.func.value, ast.Name) and node.func.value.id in ("datetime", "date"):
                                pytest.fail(
                                    f"AST Violation: Rogue un-injected clock call '{node.func.value.id}.{attr_name}()' "
                                    f"found in {mod_path}:{node.lineno}. All 8C modules must receive effective_now."
                                )

                # Inspect any direct DB, network, or LLM imports
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    mod_name = node.module or ""
                    for alias in node.names:
                        full_name = f"{mod_name}.{alias.name}" if mod_name else alias.name
                        for forbidden in ("sqlalchemy", "sqlite3", "httpx", "aiohttp", "google.genai", "openai"):
                            if forbidden in full_name:
                                pytest.fail(
                                    f"AST Boundary Violation: Forbidden import '{full_name}' in {mod_path}:{node.lineno}."
                                )
