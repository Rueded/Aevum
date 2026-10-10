"""Phase 8C.2: Derived Age & Calendar Boundary Engine Acceptance Tests.

Validates:
1. Lock 2: Pure deterministic calendar_age calculation (accurate to day, handles Feb 29 leap day).
2. Lock 2: Zero DB mutation, zero set_fact calls for age.
3. Lock 10: Deterministic boundary ordering over large multi-year jumps.
4. Lock 11: World calendar intake detection without personal life-stage mutation.
5. Path-invariance: Single-step boundary detection matches step-by-step concatenation.
6. AST boundary audit: Zero un-injected datetime.now(), zero DB, zero network, zero LLM.
"""

from __future__ import annotations

import ast
from datetime import date, datetime, timedelta, timezone
import pathlib
import pytest
from pydantic import ValidationError

from app.reality.calendar_boundary_engine import (
    CalendarBoundaryDetector,
    CalendarBoundaryEvent,
    CalendarBoundaryType,
    calendar_age,
)


class TestPhase8C2CalendarBoundaries:
    """Acceptance test suite for Phase 8C.2 Derived Age and Calendar Boundary Engine."""

    # -------------------------------------------------------------------------
    # 1. Lock 2: Pure calendar_age Mathematical Calculation
    # -------------------------------------------------------------------------

    def test_calendar_age_standard_birthday_transitions(self):
        """Verify calendar_age transitions exactly on the day of birth."""
        birth = date(2006, 5, 12)

        # Day before 20th birthday -> 19
        dt_before = datetime(2026, 5, 11, 23, 59, 59, tzinfo=timezone.utc)
        assert calendar_age(birth, dt_before) == 19

        # Exact day of 20th birthday at midnight -> 20
        dt_on = datetime(2026, 5, 12, 0, 0, 0, tzinfo=timezone.utc)
        assert calendar_age(birth, dt_on) == 20

        # Day after 20th birthday -> 20
        dt_after = datetime(2026, 5, 13, 12, 0, 0, tzinfo=timezone.utc)
        assert calendar_age(birth, dt_after) == 20

    def test_calendar_age_leap_day_birth(self):
        """Verify calendar_age for leap day births (Feb 29)."""
        leap_birth = date(2004, 2, 29)

        # 1. In a leap year (2028):
        dt_leap_before = datetime(2028, 2, 28, 23, 59, tzinfo=timezone.utc)
        assert calendar_age(leap_birth, dt_leap_before) == 23

        dt_leap_on = datetime(2028, 2, 29, 0, 0, tzinfo=timezone.utc)
        assert calendar_age(leap_birth, dt_leap_on) == 24

        # 2. In a non-leap year (2027):
        # 365 full days complete on March 1
        dt_nonleap_feb28 = datetime(2027, 2, 28, 23, 59, tzinfo=timezone.utc)
        assert calendar_age(leap_birth, dt_nonleap_feb28) == 22

        dt_nonleap_mar1 = datetime(2027, 3, 1, 0, 0, tzinfo=timezone.utc)
        assert calendar_age(leap_birth, dt_nonleap_mar1) == 23

    def test_calendar_age_rejects_retroactive_or_naive_time(self):
        """Verify calendar_age rejects time preceding birth date or lacking timezone info."""
        birth = date(2006, 5, 12)

        # Preceding birth date
        dt_preceding = datetime(2005, 1, 1, 0, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="cannot precede canonical birth_date"):
            calendar_age(birth, dt_preceding)

        # Naive datetime
        dt_naive = datetime(2026, 6, 1, 0, 0)
        with pytest.raises(ValueError, match="must be timezone-aware"):
            calendar_age(birth, dt_naive)

    # -------------------------------------------------------------------------
    # 2. Calendar Boundary Detection & Discrete Milestones
    # -------------------------------------------------------------------------

    def test_detect_month_and_year_boundaries(self):
        """Verify detector identifies month and year transitions accurately."""
        t_old = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)
        t_new = datetime(2027, 2, 10, 15, 0, tzinfo=timezone.utc)

        events = CalendarBoundaryDetector.detect_boundaries(t_old, t_new)

        # Expected boundaries crossed:
        # - 2026-12-01 (Month start)
        # - 2027-01-01 (New year + month start)
        # - 2027-02-01 (Month start)
        event_types = [e.boundary_type for e in events]
        assert CalendarBoundaryType.CALENDAR_MONTH in event_types
        assert CalendarBoundaryType.CALENDAR_YEAR in event_types

        # Verify Dec 1, Jan 1, Feb 1 timestamps
        timestamps = [e.boundary_timestamp for e in events if e.boundary_type == CalendarBoundaryType.CALENDAR_MONTH]
        assert timestamps == [
            datetime(2026, 12, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2027, 1, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2027, 2, 1, 0, 0, tzinfo=timezone.utc),
        ]

    def test_detect_birthday_boundary_milestone(self):
        """Verify birthday crossing is detected and contains correct derived age metadata."""
        birth = date(2006, 5, 12)
        t_old = datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc)
        t_new = datetime(2026, 5, 20, 0, 0, tzinfo=timezone.utc)

        events = CalendarBoundaryDetector.detect_boundaries(t_old, t_new, birth_date=birth)

        birthday_events = [e for e in events if e.boundary_type == CalendarBoundaryType.BIRTHDAY]
        assert len(birthday_events) == 1
        b_ev = birthday_events[0]
        assert b_ev.boundary_timestamp == datetime(2026, 5, 12, 0, 0, tzinfo=timezone.utc)
        assert b_ev.metadata["derived_age"] == 20
        assert b_ev.metadata["birth_date"] == "2006-05-12"

    def test_detect_academic_intake_window_lock11(self):
        """Verify academic intake window arrival is detected without personal stage mutation (Lock 11)."""
        t_old = datetime(2026, 9, 15, 0, 0, tzinfo=timezone.utc)
        t_new = datetime(2026, 10, 15, 0, 0, tzinfo=timezone.utc)

        events = CalendarBoundaryDetector.detect_boundaries(
            t_old,
            t_new,
            institutional_scopes=("world.usm.main_campus",),
        )

        intake_events = [e for e in events if e.boundary_type == CalendarBoundaryType.ACADEMIC_INTAKE_WINDOW]
        assert len(intake_events) == 1
        ev = intake_events[0]
        assert ev.boundary_timestamp == datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
        assert ev.metadata["institution_ref"] == "world.usm.main_campus"
        assert ev.metadata["intake_month"] == 10

        # Guardrail check: Event is an immutable factual calendar milestone only
        assert isinstance(ev, CalendarBoundaryEvent)
        assert not hasattr(ev, "student_id")
        assert not hasattr(ev, "academic_stage")

    # -------------------------------------------------------------------------
    # 3. Lock 10: Deterministic Boundary Ordering Over Multi-Year Leap
    # -------------------------------------------------------------------------

    def test_multi_year_leap_deterministic_ordering_lock10(self):
        """Lock 10: Verify multi-year leap produces strictly sorted chronological boundary events."""
        birth = date(2006, 5, 12)
        t_old = datetime(2025, 8, 1, 0, 0, tzinfo=timezone.utc)
        t_new = datetime(2027, 11, 1, 0, 0, tzinfo=timezone.utc)  # spans > 2 years

        events = CalendarBoundaryDetector.detect_boundaries(
            t_old,
            t_new,
            birth_date=birth,
            institutional_scopes=("world.usm.main_campus",),
        )

        assert len(events) > 10

        # 1. Strictly non-decreasing timestamp order
        for i in range(len(events) - 1):
            assert events[i].boundary_timestamp <= events[i + 1].boundary_timestamp

        # 2. Coinciding timestamps tie-break deterministically (Year before Month on Jan 1)
        jan1_events = [
            e for e in events
            if e.boundary_timestamp == datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
        ]
        assert len(jan1_events) == 2
        assert jan1_events[0].boundary_type == CalendarBoundaryType.CALENDAR_YEAR
        assert jan1_events[1].boundary_type == CalendarBoundaryType.CALENDAR_MONTH

    # -------------------------------------------------------------------------
    # 4. Path-Invariance on Boundary Detection
    # -------------------------------------------------------------------------

    def test_boundary_detection_path_invariance(self):
        """Verify boundary detection over 1 large interval equals concatenation of sub-intervals."""
        birth = date(2006, 5, 12)
        t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
        t_end = datetime(2027, 1, 1, 0, 0, tzinfo=timezone.utc)

        # Single large interval
        events_single = CalendarBoundaryDetector.detect_boundaries(t0, t_end, birth_date=birth)

        # Step-by-step intermediate intervals (e.g. 4 quarters)
        t_q1 = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)
        t_q2 = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)
        t_q3 = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)

        ev_1 = CalendarBoundaryDetector.detect_boundaries(t0, t_q1, birth_date=birth)
        ev_2 = CalendarBoundaryDetector.detect_boundaries(t_q1, t_q2, birth_date=birth)
        ev_3 = CalendarBoundaryDetector.detect_boundaries(t_q2, t_q3, birth_date=birth)
        ev_4 = CalendarBoundaryDetector.detect_boundaries(t_q3, t_end, birth_date=birth)

        events_concatenated = ev_1 + ev_2 + ev_3 + ev_4

        assert len(events_single) == len(events_concatenated)
        for e_a, e_b in zip(events_single, events_concatenated):
            assert e_a.boundary_type == e_b.boundary_type
            assert e_a.boundary_timestamp == e_b.boundary_timestamp
            assert e_a.label == e_b.label
            assert e_a.metadata == e_b.metadata

    # -------------------------------------------------------------------------
    # 5. Lock 2 & AST Audit: Zero DB / Zero set_fact() / Zero Rogue Clocks
    # -------------------------------------------------------------------------

    def test_ast_audit_pure_boundary_module(self):
        """Lock 2 AST Audit: Verify calendar_boundary_engine is 100% pure and uncoupled from DB/LLM."""
        mod_path = pathlib.Path("app/reality/calendar_boundary_engine.py")
        assert mod_path.exists()
        tree = ast.parse(mod_path.read_text(encoding="utf-8"))

        banned_calls = {"now", "today", "utcnow"}

        for node in ast.walk(tree):
            # Check for rogue clock calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr in banned_calls:
                    if isinstance(node.func.value, ast.Name) and node.func.value.id in ("datetime", "date"):
                        pytest.fail(
                            f"AST Violation: Rogue un-injected clock call in {mod_path}:{node.lineno}"
                        )
                # Check for set_fact calls
                if isinstance(node.func, ast.Attribute) and node.func.attr == "set_fact":
                    pytest.fail(
                        f"AST Violation (Lock 2): Direct set_fact() mutation call found in {mod_path}:{node.lineno}."
                    )

            # Check for forbidden imports (DB, Network, LLM)
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mod_name = node.module or ""
                for alias in node.names:
                    full_name = f"{mod_name}.{alias.name}" if mod_name else alias.name
                    for forbidden in ("sqlalchemy", "sqlite3", "httpx", "aiohttp", "google.genai", "openai"):
                        if forbidden in full_name:
                            pytest.fail(
                                f"AST Violation: Forbidden import '{full_name}' in {mod_path}:{node.lineno}"
                            )
