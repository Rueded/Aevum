"""Derived Age & Calendar Boundary Engine (Phase 8C.2).

Constitutional Invariants & Guardrails Enforced:
- Lock 2: Age Derivation Singularity.
  identity.birth_date is the sole canonical temporal anchor.
  current_age is a pure mathematical function of (birth_date, effective_now).
  Clock and boundary detectors MUST NEVER call set_fact("identity.age") or write age to DB.
- Lock 10: Deterministic Boundary Ordering.
  When a time advance crosses multiple calendar boundaries, events are sequenced
  in strict chronological order with deterministic categorical tie-breaking.
- Lock 11: World Calendar != Personal Reality.
  World calendar intake/session boundaries indicate that an external calendar window
  has arrived, NOT that a personal life-stage transition has occurred.
- Guardrail: 8C.2 may determine that a temporal/calendar boundary has been crossed;
  it must NOT determine that a personal life-stage transition has occurred.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional, Sequence
from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Pure Age Derivation Function (Lock 2: Zero DB / Zero set_fact)
# =============================================================================

def calendar_age(birth_date: date, effective_now: datetime) -> int:
    """Compute exact chronological age in completed calendar years (Lock 2).

    Pure deterministic mathematical function:
    - Ground truth anchor: birth_date.
    - Evaluated at: effective_now (timezone-aware UTC).
    - Accrual rule: Exactly full completed years.
      For leap-year births (Feb 29), age increments on March 1 in non-leap years.
    - Zero persistence side-effects: NEVER writes to CharacterCore or database.

    Args:
        birth_date: Authoritative calendar birth date.
        effective_now: Authoritative current UTC datetime.

    Returns:
        Exact integer age in completed years.

    Raises:
        ValueError: If effective_now strictly precedes birth_date.
    """
    if effective_now.tzinfo is None:
        raise ValueError(f"effective_now '{effective_now}' must be timezone-aware (UTC).")

    now_date = effective_now.date()
    if now_date < birth_date:
        raise ValueError(
            f"Chronological Invariant Violated: effective_now date '{now_date}' "
            f"cannot precede canonical birth_date '{birth_date}'."
        )

    # Resolve this year's birthday date, handling Feb 29 leap day
    try:
        birthday_this_year = date(now_date.year, birth_date.month, birth_date.day)
    except ValueError:
        # Feb 29 in a non-leap year: increments on March 1 (365 complete days)
        birthday_this_year = date(now_date.year, 3, 1)

    has_birthday_occurred = now_date >= birthday_this_year
    years_diff = now_date.year - birth_date.year

    return years_diff if has_birthday_occurred else (years_diff - 1)


# =============================================================================
# Categorical Boundary Types & Immutable Events
# =============================================================================

class CalendarBoundaryType(str, Enum):
    """Categorical classification of calendar and institutional temporal boundaries.

    Constitutional Invariant (Lock 11):
    These represent objective external calendar landmarks, NOT personal life transitions.
    """

    CALENDAR_YEAR = "CALENDAR_YEAR"                    # Crossing Dec 31 23:59:59 -> Jan 1 00:00:00
    CALENDAR_MONTH = "CALENDAR_MONTH"                  # Crossing end of month -> 1st of new month
    BIRTHDAY = "BIRTHDAY"                              # Crossing character birthday (increments derived age)
    ACADEMIC_SESSION_BOUNDARY = "ACADEMIC_SESSION_BOUNDARY"  # Academic year start or end window
    ACADEMIC_INTAKE_WINDOW = "ACADEMIC_INTAKE_WINDOW"        # Institutional intake opening (e.g. USM Oct 1)


# Deterministic tie-breaker priority when boundaries fall on the exact same timestamp
_BOUNDARY_PRIORITY_ORDER: dict[CalendarBoundaryType, int] = {
    CalendarBoundaryType.CALENDAR_YEAR: 1,
    CalendarBoundaryType.CALENDAR_MONTH: 2,
    CalendarBoundaryType.BIRTHDAY: 3,
    CalendarBoundaryType.ACADEMIC_SESSION_BOUNDARY: 4,
    CalendarBoundaryType.ACADEMIC_INTAKE_WINDOW: 5,
}


class CalendarBoundaryEvent(BaseModel):
    """Immutable audit record of a calendar boundary crossed during temporal advancement.

    Constitutional Invariant:
    Deterministic, Pydantic frozen (extra='forbid').
    Represents calendar boundary occurrence only; confers zero personal stage advancement.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    boundary_type: CalendarBoundaryType = Field(
        ...,
        description="Categorical type of boundary crossed.",
    )
    boundary_timestamp: datetime = Field(
        ...,
        description="Exact UTC timestamp when the boundary point was crossed.",
    )
    label: str = Field(
        ...,
        description="Human-readable descriptive label for audit trails.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Associated structured metadata (e.g. {'derived_age': 21}, {'institution': 'usm'}).",
    )


# =============================================================================
# Pure Boundary Detector (Lock 10: Deterministic Boundary Ordering)
# =============================================================================

class CalendarBoundaryDetector:
    """Pure, stateless detector for calendar and world academic boundaries (Phase 8C.2).

    Guarantees:
    1. Inspection-only: Inspects the half-open interval (effective_now_old, effective_now_new].
    2. Deterministic ordering (Lock 10): Events are returned in strict chronological order.
       Identical timestamps are tie-broken by fixed categorical priority and label.
    3. World knowledge non-pollution (Lock 11): Only detects external calendar arrival,
       never personal reality mutation.
    """

    @staticmethod
    def detect_boundaries(
        effective_now_old: datetime,
        effective_now_new: datetime,
        birth_date: Optional[date] = None,
        institutional_scopes: Optional[Sequence[str]] = None,
    ) -> tuple[CalendarBoundaryEvent, ...]:
        """Detect all calendar and academic boundaries crossed in (effective_now_old, effective_now_new].

        Args:
            effective_now_old: Authoritative time before advance (UTC).
            effective_now_new: Authoritative time after advance (UTC).
            birth_date: Optional canonical birth date for birthday boundary detection.
            institutional_scopes: Optional tuple of institution references (e.g. ('world.usm.main_campus',)).

        Returns:
            Tuple of CalendarBoundaryEvent in strict deterministic order.
        """
        if effective_now_old.tzinfo is None or effective_now_new.tzinfo is None:
            raise ValueError("effective_now_old and effective_now_new must be timezone-aware (UTC).")

        if effective_now_new < effective_now_old:
            raise ValueError(
                f"Boundary detection interval cannot be retroactive: "
                f"new '{effective_now_new}' < old '{effective_now_old}'."
            )

        if effective_now_old == effective_now_new:
            return ()

        events: list[CalendarBoundaryEvent] = []

        start_year = effective_now_old.year
        end_year = effective_now_new.year

        # ---------------------------------------------------------------------
        # 1. Calendar Years & Calendar Months
        # ---------------------------------------------------------------------
        # Iterate over all possible month boundaries in [start_year, end_year + 1]
        for y in range(start_year, end_year + 2):
            for m in range(1, 13):
                boundary_dt = datetime(y, m, 1, 0, 0, 0, tzinfo=timezone.utc)

                if effective_now_old < boundary_dt <= effective_now_new:
                    # If January 1, emit both CALENDAR_YEAR and CALENDAR_MONTH
                    if m == 1:
                        events.append(
                            CalendarBoundaryEvent(
                                boundary_type=CalendarBoundaryType.CALENDAR_YEAR,
                                boundary_timestamp=boundary_dt,
                                label=f"New Calendar Year {y}",
                                metadata={"year": y},
                            )
                        )

                    events.append(
                        CalendarBoundaryEvent(
                            boundary_type=CalendarBoundaryType.CALENDAR_MONTH,
                            boundary_timestamp=boundary_dt,
                            label=f"Month Start {y}-{m:02d}",
                            metadata={"year": y, "month": m},
                        )
                    )

        # ---------------------------------------------------------------------
        # 2. Birthdays (Lock 2: Derived age increment landmark)
        # ---------------------------------------------------------------------
        if birth_date is not None:
            for y in range(start_year, end_year + 2):
                try:
                    b_date = date(y, birth_date.month, birth_date.day)
                except ValueError:
                    # Feb 29 leap day in non-leap year -> March 1
                    b_date = date(y, 3, 1)

                b_datetime = datetime(b_date.year, b_date.month, b_date.day, 0, 0, 0, tzinfo=timezone.utc)

                if effective_now_old < b_datetime <= effective_now_new:
                    derived_new_age = calendar_age(birth_date, b_datetime)
                    events.append(
                        CalendarBoundaryEvent(
                            boundary_type=CalendarBoundaryType.BIRTHDAY,
                            boundary_timestamp=b_datetime,
                            label=f"Birthday Milestone (Turning {derived_new_age})",
                            metadata={
                                "birth_date": birth_date.isoformat(),
                                "derived_age": derived_new_age,
                                "milestone_year": y,
                            },
                        )
                    )

        # ---------------------------------------------------------------------
        # 3. Academic Calendar & Institutional Intake Windows (Lock 11)
        # ---------------------------------------------------------------------
        # Check standard Malaysian / USM intake windows (October 1)
        scopes = tuple(institutional_scopes) if institutional_scopes else ("world.usm.main_campus",)
        for inst in scopes:
            if "usm" in inst.lower():
                # USM undergraduate annual intake starts October 1
                for y in range(start_year, end_year + 2):
                    intake_dt = datetime(y, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
                    if effective_now_old < intake_dt <= effective_now_new:
                        events.append(
                            CalendarBoundaryEvent(
                                boundary_type=CalendarBoundaryType.ACADEMIC_INTAKE_WINDOW,
                                boundary_timestamp=intake_dt,
                                label=f"USM Main Undergraduate Intake Window ({y})",
                                metadata={
                                    "institution_ref": inst,
                                    "academic_year": y,
                                    "intake_month": 10,
                                },
                            )
                        )

        # ---------------------------------------------------------------------
        # 4. Enforce Lock 10: Deterministic Boundary Ordering
        # ---------------------------------------------------------------------
        # Primary key: boundary_timestamp ascending
        # Secondary key: _BOUNDARY_PRIORITY_ORDER ascending
        # Tertiary key: label lexicographical
        events.sort(
            key=lambda e: (
                e.boundary_timestamp,
                _BOUNDARY_PRIORITY_ORDER.get(e.boundary_type, 99),
                e.label,
            )
        )

        return tuple(events)
