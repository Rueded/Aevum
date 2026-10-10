"""Domain models and epistemic contracts for Phase 8B Dynamic Life Timeline.

Hard Architectural Invariants (Constitutional Invariants A–H):
- Invariant A (Constraint, Not Certainty): Temporal inference constrains reality;
  it does not manufacture certainty or invent arbitrary microsecond schedules.
  Rejects datetime instances with synthetic hour/minute/second precision.
- Invariant B (Past Occurrence != Epistemic Confirmation): Past occurrence does not
  imply epistemic confirmation. A reconstructed past remains DERIVED unless
  independently evidenced.
- Invariant C (Projection is Never Canonical Reality): Future projections carry
  status PROJECTED and are strictly prohibited from entering canonical reality.
- Invariant D (TCG is a Reasoning Structure, Not a Fact Store): Ephemeral in-memory
  models; zero direct database writes, zero mutation authority.
- Invariant E (Bounded, Deterministic & Traceable): Bounded propagation depth
  (MAX_TEMPORAL_PROPAGATION_HOPS = 2). MAX_PROJECTED_NODES = 4.
- Invariant F (World Temporal Rules != Personal Temporal Facts): World rules are
  evaluative constraints, never copied as personal core facts.
- Invariant G (Trajectory Plurality & Temporal Ambiguity Preservation): When multiple
  temporal trajectories satisfy constraints, Phase 8B preserves the compatible set
  (bounded by MAX_COMPATIBLE_TRAJECTORIES = 3) rather than arbitrarily choosing one.
- Invariant H (Delegation to Phase 7 Minimal Repair): Retrospective contradictions
  delegate to RealityRepairService Level 2 (TEMPORAL_REINTERPRETATION); zero second
  repair authority; zero compensatory biography.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime
import enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


# =============================================================================
# Architectural Bounds & Cardinality Constants (Implementation Locks 1 & 6)
# =============================================================================

MAX_COMPATIBLE_TRAJECTORIES: int = 3
"""Maximum number of discrete compatible trajectories retained concurrently.
If compatible trajectories exceed this bound, the engine produces
TEMPORAL_AMBIGUITY_UNRESOLVED rather than arbitrarily picking one."""

MAX_TEMPORAL_PROPAGATION_HOPS: int = 2
"""Maximum derivation hops from an authoritative origin fact in a single turn.
Hop 0: Authoritative fact -> Hop 1: Direct constraint -> Hop 2: Adjacent state."""

MAX_PROJECTED_NODES: int = 4
"""Maximum total projected nodes (LifeStates + LifeEvents combined) per trajectory.
Projected nodes cannot serve as inputs to generate further projected nodes."""


# =============================================================================
# Categorical Enums: The Three Orthogonal Epistemic Dimensions
# =============================================================================

class TemporalGranularity(str, enum.Enum):
    """Categorical precision of temporal boundaries (Invariant A: No fake precision)."""

    EXACT_DATE = "EXACT_DATE"          # e.g., 2025-10-06 (specific known day)
    MONTH = "MONTH"                    # e.g., 2025-10 (intake month known)
    DATE_RANGE = "DATE_RANGE"          # e.g., 2028-06 to 2028-09 (internship period)
    YEAR = "YEAR"                      # e.g., 2025 (exam year known)
    APPROXIMATE_YEAR = "APPROXIMATE_YEAR" # e.g., ~2029 (derived graduation window)
    UNKNOWN = "UNKNOWN"                # Constraint exists, exact timing unrecorded


class TemporalHorizon(str, enum.Enum):
    """Temporal direction relative to the current conversation turn."""

    PAST = "PAST"
    PRESENT = "PRESENT"
    FUTURE = "FUTURE"


class EpistemicGrounding(str, enum.Enum):
    """Evidence origin and grounding of a temporal fact or inference."""

    USER_CONFIRMED = "USER_CONFIRMED"  # Grounded in explicit user statement
    OBSERVED = "OBSERVED"              # Grounded in system baseline / authoritative truth
    DERIVED = "DERIVED"                # Inferred from canonical facts via temporal constraints
    PROJECTED = "PROJECTED"            # Tentative forward continuation without factual certainty
    UNKNOWN = "UNKNOWN"                # Insufficient temporal information


class Canonicality(str, enum.Enum):
    """Authority status regarding character canonical reality."""

    CANONICAL = "CANONICAL"
    NON_CANONICAL = "NON_CANONICAL"


class LifeStage(str, enum.Enum):
    """Categorical life and education development stages."""

    PRIMARY_EDUCATION = "PRIMARY_EDUCATION"
    SECONDARY_EDUCATION = "SECONDARY_EDUCATION"
    PRE_UNIVERSITY = "PRE_UNIVERSITY"
    DIPLOMA = "DIPLOMA"
    UNDERGRADUATE = "UNDERGRADUATE"
    INTERNSHIP = "INTERNSHIP"
    POSTGRADUATE = "POSTGRADUATE"
    EARLY_CAREER = "EARLY_CAREER"
    CAREER = "CAREER"
    TRANSITIONAL = "TRANSITIONAL"       # e.g. gap year, sabbatical, career break


# =============================================================================
# Epistemic Combination Validity Matrix (Implementation Lock 3)
# =============================================================================

def validate_epistemic_canonicality_combination(
    grounding: EpistemicGrounding,
    canonicality: Canonicality,
) -> None:
    """Validate orthogonal epistemic grounding against canonicality authority.

    Implementation Lock 3 Rules:
    - DERIVED + CANONICAL = INVALID
    - PROJECTED + CANONICAL = INVALID
    - UNKNOWN + CANONICAL = INVALID
    - USER_CONFIRMED / OBSERVED may be CANONICAL or NON_CANONICAL.
    """
    if canonicality == Canonicality.CANONICAL:
        if grounding in (
            EpistemicGrounding.DERIVED,
            EpistemicGrounding.PROJECTED,
            EpistemicGrounding.UNKNOWN,
        ):
            raise ValueError(
                f"Invalid Epistemic-Canonicality combination: EpistemicGrounding.{grounding.value} "
                f"cannot be paired with Canonicality.CANONICAL. "
                f"Derived inferences, future projections, and unknown states are strictly "
                f"non-canonical reasoning structures."
            )


# =============================================================================
# TemporalInterval (Implementation Lock 2)
# =============================================================================

class TemporalInterval(BaseModel):
    """Immutable interval model representing temporal boundaries without pseudo-probabilities.

    Hard Invariants (Implementation Lock 2):
    - Zero confidence / probability float.
    - Zero datetime instances: all boundaries must be datetime.date.
    - Strict boundary ordering:
      - earliest_start <= latest_start (when both known)
      - earliest_end <= latest_end (when both known)
      - earliest_start <= latest_end (when both known)
    - UNKNOWN semantics:
      - UNKNOWN represents 'insufficient temporal information', NOT an unconstrained
        universal interval. It does NOT universally satisfy date containment or overlap.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    earliest_start: Optional[date] = Field(default=None, description="Lower bound of start window")
    latest_start: Optional[date] = Field(default=None, description="Upper bound of start window")
    earliest_end: Optional[date] = Field(default=None, description="Lower bound of completion window")
    latest_end: Optional[date] = Field(default=None, description="Upper bound of completion window")
    granularity: TemporalGranularity = Field(..., description="Categorical temporal precision")
    is_ongoing: bool = Field(default=False, description="True if currently active (PRESENT horizon)")

    @model_validator(mode="before")
    @classmethod
    def reject_synthetic_precision(cls, data: Any) -> Any:
        """Reject datetime instances to enforce Invariant A (no fake hour/minute/second precision)."""
        if isinstance(data, dict):
            for field_name in ("earliest_start", "latest_start", "earliest_end", "latest_end"):
                val = data.get(field_name)
                if val is not None and isinstance(val, datetime):
                    raise ValueError(
                        f"Field '{field_name}' must be a datetime.date instance, not datetime.datetime. "
                        f"Synthetic hour/minute/second precision is strictly forbidden."
                    )
        return data

    @model_validator(mode="after")
    def validate_boundary_invariants(self) -> TemporalInterval:
        """Validate boundary ordering invariants."""
        # 1. Start window ordering
        if self.earliest_start is not None and self.latest_start is not None:
            if self.earliest_start > self.latest_start:
                raise ValueError(
                    f"Invalid boundary ordering: earliest_start ({self.earliest_start}) "
                    f"cannot be after latest_start ({self.latest_start})."
                )

        # 2. End window ordering
        if self.earliest_end is not None and self.latest_end is not None:
            if self.earliest_end > self.latest_end:
                raise ValueError(
                    f"Invalid boundary ordering: earliest_end ({self.earliest_end}) "
                    f"cannot be after latest_end ({self.latest_end})."
                )

        # 3. Overall span ordering (earliest start must precede latest end)
        if self.earliest_start is not None and self.latest_end is not None:
            if self.earliest_start > self.latest_end:
                raise ValueError(
                    f"Invalid boundary ordering: earliest_start ({self.earliest_start}) "
                    f"cannot be after latest_end ({self.latest_end})."
                )

        # 4. Exact date consistency
        if (
            self.earliest_start is not None
            and self.latest_start is not None
            and self.earliest_end is not None
            and self.latest_end is not None
            and self.earliest_start == self.latest_start
            and self.earliest_end == self.latest_end
        ):
            if self.earliest_start > self.earliest_end:
                raise ValueError(
                    f"Invalid interval: start date ({self.earliest_start}) "
                    f"cannot be after end date ({self.earliest_end})."
                )

        # 5. UNKNOWN semantics enforcement
        if self.granularity == TemporalGranularity.UNKNOWN:
            if (
                self.earliest_start is not None
                or self.latest_start is not None
                or self.earliest_end is not None
                or self.latest_end is not None
            ):
                raise ValueError(
                    "TemporalGranularity.UNKNOWN requires all date boundary fields to be None. "
                    "UNKNOWN represents insufficient temporal information."
                )

        return self

    # -------------------------------------------------------------------------
    # Epistemic Query Helpers (UNKNOWN is NOT an unconstrained universal interval)
    # -------------------------------------------------------------------------

    def is_unknown(self) -> bool:
        """Return True if this interval represents insufficient temporal information."""
        return self.granularity == TemporalGranularity.UNKNOWN

    def contains_date(self, target: date) -> bool:
        """Check if target date falls unambiguously within the known interval boundaries.

        Invariant: If interval is UNKNOWN, returns False! UNKNOWN represents lack of
        information and does NOT universal-match arbitrary dates.
        """
        if self.is_unknown():
            return False

        if self.earliest_start is not None and target < self.earliest_start:
            return False

        if self.latest_end is not None and target > self.latest_end:
            return False

        if self.latest_start is not None and self.earliest_end is not None:
            # Fully bounded interval
            return self.earliest_start <= target <= self.latest_end if self.earliest_start else True

        return True

    def overlaps(self, other: TemporalInterval) -> bool:
        """Check if two intervals overlap.

        Invariant: If either interval is UNKNOWN, returns False. UNKNOWN cannot assert
        temporal overlap.
        """
        if self.is_unknown() or other.is_unknown():
            return False

        # If self ends before other starts
        if self.latest_end is not None and other.earliest_start is not None:
            if self.latest_end < other.earliest_start:
                return False

        # If other ends before self starts
        if other.latest_end is not None and self.earliest_start is not None:
            if other.latest_end < self.earliest_start:
                return False

        return True

    # -------------------------------------------------------------------------
    # Factory Constructors
    # -------------------------------------------------------------------------

    @classmethod
    def create_exact(
        cls,
        start: date,
        end: Optional[date] = None,
        is_ongoing: bool = False,
    ) -> TemporalInterval:
        """Construct an exact date interval."""
        return cls(
            earliest_start=start,
            latest_start=start,
            earliest_end=end,
            latest_end=end,
            granularity=TemporalGranularity.EXACT_DATE,
            is_ongoing=is_ongoing,
        )

    @classmethod
    def create_date_range(cls, start: date, end: date) -> TemporalInterval:
        """Construct a bounded date range interval."""
        return cls(
            earliest_start=start,
            latest_start=start,
            earliest_end=end,
            latest_end=end,
            granularity=TemporalGranularity.DATE_RANGE,
            is_ongoing=False,
        )

    @classmethod
    def create_month(cls, year: int, month: int, is_ongoing: bool = False) -> TemporalInterval:
        """Construct a calendar month interval spanning from 1st to last day of month."""
        start_d = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_d = date(year, month, last_day)
        return cls(
            earliest_start=start_d,
            latest_start=start_d,
            earliest_end=end_d,
            latest_end=end_d,
            granularity=TemporalGranularity.MONTH,
            is_ongoing=is_ongoing,
        )

    @classmethod
    def create_year(cls, year: int, is_ongoing: bool = False) -> TemporalInterval:
        """Construct a full calendar year interval spanning Jan 1 to Dec 31."""
        return cls(
            earliest_start=date(year, 1, 1),
            latest_start=date(year, 1, 1),
            earliest_end=date(year, 12, 31),
            latest_end=date(year, 12, 31),
            granularity=TemporalGranularity.YEAR,
            is_ongoing=is_ongoing,
        )

    @classmethod
    def create_approximate_year(cls, year: int, is_ongoing: bool = False) -> TemporalInterval:
        """Construct an approximate year interval."""
        return cls(
            earliest_start=date(year, 1, 1),
            latest_start=date(year, 1, 1),
            earliest_end=date(year, 12, 31),
            latest_end=date(year, 12, 31),
            granularity=TemporalGranularity.APPROXIMATE_YEAR,
            is_ongoing=is_ongoing,
        )

    @classmethod
    def create_unknown(cls) -> TemporalInterval:
        """Construct an UNKNOWN interval representing insufficient temporal information."""
        return cls(
            earliest_start=None,
            latest_start=None,
            earliest_end=None,
            latest_end=None,
            granularity=TemporalGranularity.UNKNOWN,
            is_ongoing=False,
        )


# =============================================================================
# Domain Schemas: Life State vs Life Event
# =============================================================================

class LifeStateItem(BaseModel):
    """An ongoing condition occupied across a temporal duration.

    Strict Invariants:
    - Immutable (frozen=True, extra="forbid").
    - Epistemic-Canonicality combination validity enforced.
    - Propagation depth bounded to <= MAX_TEMPORAL_PROPAGATION_HOPS (2).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    state_id: str = Field(..., description="Deterministic state identifier")
    character_id: str = Field(default="aevum", description="Character entity identifier")
    stage: LifeStage = Field(..., description="Categorical developmental stage")
    title: str = Field(..., description="Descriptive title (e.g. 'Undergraduate Student (Year 2)')")
    institution_ref: Optional[str] = Field(default=None, description="Ref to WorldKnowledge institution")
    domain_detail: Optional[str] = Field(default=None, description="Major, department, or company")
    interval: TemporalInterval = Field(..., description="Temporal boundary interval")
    temporal_horizon: TemporalHorizon = Field(..., description="Temporal direction relative to current turn")
    epistemic_grounding: EpistemicGrounding = Field(..., description="Evidence grounding classification")
    canonicality: Canonicality = Field(default=Canonicality.NON_CANONICAL, description="Canonical authority status")
    origin_fact_key: Optional[str] = Field(default=None, description="Canonical core fact triggering this state")
    propagation_depth: int = Field(
        default=0,
        ge=0,
        le=MAX_TEMPORAL_PROPAGATION_HOPS,
        description="Derivation hop depth from authoritative origin fact",
    )
    constraint_chain: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Tuple of rule IDs applied to materialize this state",
    )

    @model_validator(mode="after")
    def validate_state_invariants(self) -> LifeStateItem:
        """Enforce epistemic-canonicality and horizon invariants."""
        # 1. Epistemic-Canonicality Combination Matrix
        validate_epistemic_canonicality_combination(self.epistemic_grounding, self.canonicality)

        # 2. Ongoing state must align with PRESENT horizon
        if self.interval.is_ongoing and self.temporal_horizon != TemporalHorizon.PRESENT:
            raise ValueError(
                f"LifeStateItem with ongoing interval must have TemporalHorizon.PRESENT, "
                f"got {self.temporal_horizon.value}."
            )

        # 3. Future state must have PROJECTED or UNKNOWN grounding
        if self.temporal_horizon == TemporalHorizon.FUTURE:
            if self.epistemic_grounding not in (EpistemicGrounding.PROJECTED, EpistemicGrounding.UNKNOWN):
                raise ValueError(
                    f"Future states must have EpistemicGrounding.PROJECTED or UNKNOWN, "
                    f"got {self.epistemic_grounding.value}. Future cannot be observed or confirmed."
                )

        return self


class LifeEventItem(BaseModel):
    """A discrete milestone, intake, exit, or stage transition point.

    Strict Invariants:
    - Immutable (frozen=True, extra="forbid").
    - Epistemic-Canonicality combination validity enforced.
    - Propagation depth bounded to <= MAX_TEMPORAL_PROPAGATION_HOPS (2).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str = Field(..., description="Deterministic event identifier")
    character_id: str = Field(default="aevum", description="Character entity identifier")
    event_type: str = Field(..., description="e.g. 'EXAM_COMPLETION', 'UNIVERSITY_INTAKE', 'GRADUATION'")
    source_state_id: Optional[str] = Field(default=None, description="Preceding state ID, if transition")
    target_state_id: Optional[str] = Field(default=None, description="Succeeding state ID, if transition")
    interval: TemporalInterval = Field(..., description="Event timestamp or discrete date range")
    temporal_horizon: TemporalHorizon = Field(..., description="Temporal direction relative to current turn")
    epistemic_grounding: EpistemicGrounding = Field(..., description="Evidence grounding classification")
    canonicality: Canonicality = Field(default=Canonicality.NON_CANONICAL, description="Canonical authority status")
    origin_fact_key: Optional[str] = Field(default=None, description="Canonical core fact triggering this event")
    propagation_depth: int = Field(
        default=0,
        ge=0,
        le=MAX_TEMPORAL_PROPAGATION_HOPS,
        description="Derivation hop depth from authoritative origin fact",
    )
    constraint_chain: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Tuple of rule IDs applied to materialize this event",
    )

    @model_validator(mode="after")
    def validate_event_invariants(self) -> LifeEventItem:
        """Enforce epistemic-canonicality and horizon invariants."""
        # 1. Epistemic-Canonicality Combination Matrix
        validate_epistemic_canonicality_combination(self.epistemic_grounding, self.canonicality)

        # 2. Future events must have PROJECTED or UNKNOWN grounding
        if self.temporal_horizon == TemporalHorizon.FUTURE:
            if self.epistemic_grounding not in (EpistemicGrounding.PROJECTED, EpistemicGrounding.UNKNOWN):
                raise ValueError(
                    f"Future events must have EpistemicGrounding.PROJECTED or UNKNOWN, "
                    f"got {self.epistemic_grounding.value}. Future cannot be observed or confirmed."
                )

        return self
