"""Unit contract tests for Phase 8B.1 Temporal Data Contracts & Epistemic DTOs.

Verifies:
1. Valid interval construction (exact, date range, month, year, approximate).
2. Boundary ordering validation (earliest_start <= latest_start, earliest_end <= latest_end, earliest_start <= latest_end).
3. Exact start <= end date ordering validation.
4. UNKNOWN semantics:
   - Represents insufficient temporal information, NOT an unconstrained universal interval.
   - contains_date() returns False for UNKNOWN.
   - overlaps() returns False if either interval is UNKNOWN.
   - UNKNOWN requires all date fields to be None.
5. All temporal granularities supported.
6. Temporal horizons (PAST, PRESENT, FUTURE).
7. Ongoing state requires TemporalHorizon.PRESENT.
8. Future states and events require EpistemicGrounding.PROJECTED or UNKNOWN.
9. Epistemic-Canonicality Validity Matrix (Implementation Lock 3):
   - DERIVED + CANONICAL -> INVALID
   - PROJECTED + CANONICAL -> INVALID
   - UNKNOWN + CANONICAL -> INVALID
   - USER_CONFIRMED + CANONICAL -> VALID
   - USER_CONFIRMED + NON_CANONICAL -> VALID
   - OBSERVED + CANONICAL -> VALID
   - OBSERVED + NON_CANONICAL -> VALID
   - DERIVED + NON_CANONICAL -> VALID
   - PROJECTED + NON_CANONICAL -> VALID
10. LifeStateItem field validation and immutability.
11. LifeEventItem field validation and immutability.
12. Extra-field rejection (ConfigDict frozen=True, extra="forbid").
13. Serialization and deserialization round-trip.
14. No synthetic precision: datetime.datetime instances strictly rejected in favor of datetime.date.
15. No confidence or probability float on interval or state models.
16. Propagation depth bounded to <= MAX_TEMPORAL_PROPAGATION_HOPS (2).
17. AST audit: Zero set_fact, zero tokens, zero RBE, zero network imports in temporal_models.py.
"""

from __future__ import annotations

import ast
from datetime import date, datetime
import pathlib
from pydantic import ValidationError
import pytest

from app.reality.temporal_models import (
    Canonicality,
    EpistemicGrounding,
    LifeEventItem,
    LifeStage,
    LifeStateItem,
    MAX_COMPATIBLE_TRAJECTORIES,
    MAX_PROJECTED_NODES,
    MAX_TEMPORAL_PROPAGATION_HOPS,
    TemporalGranularity,
    TemporalHorizon,
    TemporalInterval,
    validate_epistemic_canonicality_combination,
)


class TestPhase8B1Contracts:
    """Comprehensive test suite for Phase 8B.1 contracts and invariants."""

    # -------------------------------------------------------------------------
    # 1. Valid Interval Constructions
    # -------------------------------------------------------------------------
    def test_valid_exact_date_interval(self):
        """Construct exact single-day and bounded exact range intervals."""
        d = date(2025, 10, 6)
        interval = TemporalInterval.create_exact(start=d)
        assert interval.granularity == TemporalGranularity.EXACT_DATE
        assert interval.earliest_start == d
        assert interval.latest_start == d
        assert interval.earliest_end is None
        assert interval.latest_end is None
        assert interval.is_ongoing is False

    def test_valid_date_range_interval(self):
        """Construct a bounded discrete date range."""
        start = date(2028, 6, 1)
        end = date(2028, 9, 30)
        interval = TemporalInterval.create_date_range(start=start, end=end)
        assert interval.granularity == TemporalGranularity.DATE_RANGE
        assert interval.earliest_start == start
        assert interval.latest_end == end

    def test_valid_month_interval(self):
        """Construct a month interval spanning first to last calendar day."""
        interval = TemporalInterval.create_month(year=2025, month=10)
        assert interval.granularity == TemporalGranularity.MONTH
        assert interval.earliest_start == date(2025, 10, 1)
        assert interval.latest_end == date(2025, 10, 31)

    def test_valid_year_interval(self):
        """Construct a calendar year interval."""
        interval = TemporalInterval.create_year(year=2026, is_ongoing=True)
        assert interval.granularity == TemporalGranularity.YEAR
        assert interval.earliest_start == date(2026, 1, 1)
        assert interval.latest_end == date(2026, 12, 31)
        assert interval.is_ongoing is True

    def test_valid_approximate_year_interval(self):
        """Construct an approximate year interval."""
        interval = TemporalInterval.create_approximate_year(year=2029)
        assert interval.granularity == TemporalGranularity.APPROXIMATE_YEAR
        assert interval.earliest_start == date(2029, 1, 1)
        assert interval.latest_end == date(2029, 12, 31)

    # -------------------------------------------------------------------------
    # 2. Boundary Ordering Validation (Implementation Lock 2)
    # -------------------------------------------------------------------------
    def test_invalid_start_window_ordering_rejected(self):
        """earliest_start > latest_start must raise ValueError."""
        with pytest.raises(ValueError, match="earliest_start.*cannot be after latest_start"):
            TemporalInterval(
                earliest_start=date(2025, 5, 1),
                latest_start=date(2025, 4, 1),
                granularity=TemporalGranularity.MONTH,
            )

    def test_invalid_end_window_ordering_rejected(self):
        """earliest_end > latest_end must raise ValueError."""
        with pytest.raises(ValueError, match="earliest_end.*cannot be after latest_end"):
            TemporalInterval(
                earliest_start=date(2025, 1, 1),
                latest_start=date(2025, 1, 1),
                earliest_end=date(2025, 12, 31),
                latest_end=date(2025, 11, 30),
                granularity=TemporalGranularity.YEAR,
            )

    def test_invalid_overall_span_ordering_rejected(self):
        """earliest_start > latest_end must raise ValueError."""
        with pytest.raises(ValueError, match="earliest_start.*cannot be after latest_end"):
            TemporalInterval(
                earliest_start=date(2026, 1, 1),
                latest_start=date(2026, 6, 1),
                earliest_end=date(2025, 1, 1),
                latest_end=date(2025, 12, 31),
                granularity=TemporalGranularity.YEAR,
            )

    def test_invalid_exact_start_after_end_rejected(self):
        """Exact start date > exact end date must raise ValueError."""
        with pytest.raises(ValueError, match="cannot be after latest_end|cannot be after end date"):
            TemporalInterval(
                earliest_start=date(2026, 5, 1),
                latest_start=date(2026, 5, 1),
                earliest_end=date(2026, 4, 1),
                latest_end=date(2026, 4, 1),
                granularity=TemporalGranularity.EXACT_DATE,
            )

    # -------------------------------------------------------------------------
    # 3. UNKNOWN Interval Semantics (Implementation Lock 2)
    # -------------------------------------------------------------------------
    def test_unknown_interval_properties(self):
        """UNKNOWN interval represents insufficient temporal info, not universal match."""
        unknown = TemporalInterval.create_unknown()
        assert unknown.is_unknown() is True
        assert unknown.granularity == TemporalGranularity.UNKNOWN
        assert unknown.earliest_start is None
        assert unknown.latest_end is None

        # UNKNOWN does NOT universal-match arbitrary dates
        test_d = date(2026, 5, 1)
        assert unknown.contains_date(test_d) is False

        # UNKNOWN does NOT claim universal overlap with known intervals
        known = TemporalInterval.create_year(2026)
        assert unknown.overlaps(known) is False
        assert known.overlaps(unknown) is False

    def test_unknown_interval_rejects_dates(self):
        """UNKNOWN interval cannot carry concrete date boundaries."""
        with pytest.raises(ValueError, match="requires all date boundary fields to be None"):
            TemporalInterval(
                earliest_start=date(2025, 1, 1),
                granularity=TemporalGranularity.UNKNOWN,
            )

    # -------------------------------------------------------------------------
    # 4. No Synthetic Precision Invariant (Invariant A)
    # -------------------------------------------------------------------------
    def test_datetime_instance_rejected_in_favor_of_date(self):
        """Passing datetime.datetime instances is rejected with ValueError."""
        dt = datetime(2025, 10, 6, 8, 30, 0)
        with pytest.raises(ValueError, match="Synthetic hour/minute/second precision is strictly forbidden"):
            TemporalInterval(
                earliest_start=dt,  # type: ignore
                latest_start=dt,    # type: ignore
                granularity=TemporalGranularity.EXACT_DATE,
            )

    # -------------------------------------------------------------------------
    # 5. Epistemic-Canonicality Combination Validity Matrix (Implementation Lock 3)
    # -------------------------------------------------------------------------
    @pytest.mark.parametrize(
        "grounding",
        [
            EpistemicGrounding.DERIVED,
            EpistemicGrounding.PROJECTED,
            EpistemicGrounding.UNKNOWN,
        ],
    )
    def test_invalid_epistemic_canonicality_combinations_rejected(self, grounding: EpistemicGrounding):
        """DERIVED, PROJECTED, and UNKNOWN can NEVER be CANONICAL."""
        with pytest.raises(ValueError, match="cannot be paired with Canonicality.CANONICAL"):
            validate_epistemic_canonicality_combination(grounding, Canonicality.CANONICAL)

    @pytest.mark.parametrize(
        ("grounding", "canonicality"),
        [
            (EpistemicGrounding.USER_CONFIRMED, Canonicality.CANONICAL),
            (EpistemicGrounding.USER_CONFIRMED, Canonicality.NON_CANONICAL),
            (EpistemicGrounding.OBSERVED, Canonicality.CANONICAL),
            (EpistemicGrounding.OBSERVED, Canonicality.NON_CANONICAL),
            (EpistemicGrounding.DERIVED, Canonicality.NON_CANONICAL),
            (EpistemicGrounding.PROJECTED, Canonicality.NON_CANONICAL),
            (EpistemicGrounding.UNKNOWN, Canonicality.NON_CANONICAL),
        ],
    )
    def test_valid_epistemic_canonicality_combinations_accepted(
        self, grounding: EpistemicGrounding, canonicality: Canonicality
    ):
        """Allowed combinations pass validation without raising."""
        validate_epistemic_canonicality_combination(grounding, canonicality)

    # -------------------------------------------------------------------------
    # 6. LifeStateItem Validation & Immutability
    # -------------------------------------------------------------------------
    def test_valid_lifestate_item_construction(self):
        """Construct a valid LifeStateItem."""
        interval = TemporalInterval.create_year(2026, is_ongoing=True)
        state = LifeStateItem(
            state_id="state_undergrad_year2",
            stage=LifeStage.UNDERGRADUATE,
            title="Undergraduate Student (Year 2)",
            institution_ref="world.usm.main_campus",
            domain_detail="Computer Science",
            interval=interval,
            temporal_horizon=TemporalHorizon.PRESENT,
            epistemic_grounding=EpistemicGrounding.DERIVED,
            canonicality=Canonicality.NON_CANONICAL,
            origin_fact_key="education.major",
            propagation_depth=1,
            constraint_chain=("RULE_UNDERGRAD_PROGRESSION",),
        )
        assert state.state_id == "state_undergrad_year2"
        assert state.stage == LifeStage.UNDERGRADUATE
        assert state.epistemic_grounding == EpistemicGrounding.DERIVED
        assert state.canonicality == Canonicality.NON_CANONICAL
        assert state.propagation_depth == 1

    def test_lifestate_item_rejects_derived_canonical(self):
        """LifeStateItem model validator enforces Lock 3 (DERIVED != CANONICAL)."""
        interval = TemporalInterval.create_year(2024)
        with pytest.raises(ValueError, match="cannot be paired with Canonicality.CANONICAL"):
            LifeStateItem(
                state_id="state_invalid_derived_canonical",
                stage=LifeStage.PRE_UNIVERSITY,
                title="STPM Student",
                interval=interval,
                temporal_horizon=TemporalHorizon.PAST,
                epistemic_grounding=EpistemicGrounding.DERIVED,
                canonicality=Canonicality.CANONICAL,  # VIOLATION!
            )

    def test_lifestate_item_ongoing_requires_present_horizon(self):
        """Ongoing interval on LifeStateItem must have TemporalHorizon.PRESENT."""
        interval = TemporalInterval.create_year(2026, is_ongoing=True)
        with pytest.raises(ValueError, match="must have TemporalHorizon.PRESENT"):
            LifeStateItem(
                state_id="state_invalid_horizon",
                stage=LifeStage.UNDERGRADUATE,
                title="Undergrad Student",
                interval=interval,
                temporal_horizon=TemporalHorizon.PAST,  # VIOLATION!
                epistemic_grounding=EpistemicGrounding.DERIVED,
                canonicality=Canonicality.NON_CANONICAL,
            )

    def test_lifestate_item_future_requires_projected_or_unknown(self):
        """Future horizon state must have EpistemicGrounding.PROJECTED or UNKNOWN."""
        interval = TemporalInterval.create_year(2029)
        with pytest.raises(ValueError, match="Future states must have EpistemicGrounding.PROJECTED or UNKNOWN"):
            LifeStateItem(
                state_id="state_invalid_future_grounding",
                stage=LifeStage.EARLY_CAREER,
                title="Junior Software Engineer",
                interval=interval,
                temporal_horizon=TemporalHorizon.FUTURE,
                epistemic_grounding=EpistemicGrounding.USER_CONFIRMED,  # Future cannot be confirmed!
                canonicality=Canonicality.NON_CANONICAL,
            )

    def test_lifestate_item_immutability(self):
        """LifeStateItem is frozen; attribute mutation raises ValidationError."""
        interval = TemporalInterval.create_year(2026, is_ongoing=True)
        state = LifeStateItem(
            state_id="state_immut",
            stage=LifeStage.UNDERGRADUATE,
            title="Student",
            interval=interval,
            temporal_horizon=TemporalHorizon.PRESENT,
            epistemic_grounding=EpistemicGrounding.DERIVED,
            canonicality=Canonicality.NON_CANONICAL,
        )
        with pytest.raises(ValidationError, match="Instance is frozen"):
            state.title = "Altered Title"  # type: ignore

    # -------------------------------------------------------------------------
    # 7. LifeEventItem Validation & Immutability
    # -------------------------------------------------------------------------
    def test_valid_lifeevent_item_construction(self):
        """Construct a valid LifeEventItem."""
        interval = TemporalInterval.create_month(year=2025, month=10)
        event = LifeEventItem(
            event_id="event_usm_intake_2025",
            event_type="UNIVERSITY_INTAKE",
            source_state_id="state_pre_u_stpm",
            target_state_id="state_undergrad_year1",
            interval=interval,
            temporal_horizon=TemporalHorizon.PAST,
            epistemic_grounding=EpistemicGrounding.USER_CONFIRMED,
            canonicality=Canonicality.CANONICAL,
        )
        assert event.event_id == "event_usm_intake_2025"
        assert event.event_type == "UNIVERSITY_INTAKE"
        assert event.canonicality == Canonicality.CANONICAL

    def test_lifeevent_item_rejects_projected_canonical(self):
        """LifeEventItem model validator enforces Lock 3 (PROJECTED != CANONICAL)."""
        interval = TemporalInterval.create_month(year=2028, month=6)
        with pytest.raises(ValueError, match="cannot be paired with Canonicality.CANONICAL"):
            LifeEventItem(
                event_id="event_invalid_projected_canonical",
                event_type="INTERNSHIP_START",
                interval=interval,
                temporal_horizon=TemporalHorizon.FUTURE,
                epistemic_grounding=EpistemicGrounding.PROJECTED,
                canonicality=Canonicality.CANONICAL,  # VIOLATION!
            )

    def test_lifeevent_item_immutability(self):
        """LifeEventItem is frozen; attribute mutation raises error."""
        interval = TemporalInterval.create_month(year=2025, month=10)
        event = LifeEventItem(
            event_id="event_immut",
            event_type="INTAKE",
            interval=interval,
            temporal_horizon=TemporalHorizon.PAST,
            epistemic_grounding=EpistemicGrounding.OBSERVED,
            canonicality=Canonicality.CANONICAL,
        )
        with pytest.raises(ValidationError, match="Instance is frozen"):
            event.event_type = "ALTERED_TYPE"  # type: ignore

    # -------------------------------------------------------------------------
    # 8. Extra-Field Rejection (ConfigDict extra="forbid")
    # -------------------------------------------------------------------------
    def test_extra_field_rejection_interval(self):
        """TemporalInterval rejects unexpected fields."""
        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            TemporalInterval(
                earliest_start=date(2025, 1, 1),
                granularity=TemporalGranularity.YEAR,
                confidence=0.95,  # type: ignore - VIOLATION!
            )

    def test_extra_field_rejection_lifestate(self):
        """LifeStateItem rejects unexpected fields."""
        interval = TemporalInterval.create_year(2026)
        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            LifeStateItem(
                state_id="state_extra",
                stage=LifeStage.UNDERGRADUATE,
                title="Student",
                interval=interval,
                temporal_horizon=TemporalHorizon.PAST,
                epistemic_grounding=EpistemicGrounding.DERIVED,
                canonicality=Canonicality.NON_CANONICAL,
                probability=0.88,  # type: ignore - VIOLATION!
            )

    # -------------------------------------------------------------------------
    # 9. Serialization & Deserialization Round-Trip
    # -------------------------------------------------------------------------
    def test_serialization_round_trip(self):
        """Dump to dict / JSON and revalidate correctly."""
        interval = TemporalInterval.create_date_range(
            start=date(2028, 6, 1), end=date(2028, 9, 30)
        )
        state = LifeStateItem(
            state_id="state_internship",
            stage=LifeStage.INTERNSHIP,
            title="Software Engineering Intern",
            institution_ref="company.tech_corp",
            domain_detail="Full Stack",
            interval=interval,
            temporal_horizon=TemporalHorizon.FUTURE,
            epistemic_grounding=EpistemicGrounding.PROJECTED,
            canonicality=Canonicality.NON_CANONICAL,
            origin_fact_key="career.aspiration",
            propagation_depth=2,
            constraint_chain=("RULE_INTERNSHIP_PLACEMENT",),
        )
        data = state.model_dump()
        reconstituted = LifeStateItem.model_validate(data)
        assert reconstituted == state

    # -------------------------------------------------------------------------
    # 10. Propagation Depth Bound (Invariant E)
    # -------------------------------------------------------------------------
    def test_propagation_depth_exceeding_max_hops_rejected(self):
        """propagation_depth > MAX_TEMPORAL_PROPAGATION_HOPS (2) is rejected by Pydantic."""
        interval = TemporalInterval.create_year(2026)
        with pytest.raises(ValueError, match="Input should be less than or equal to 2"):
            LifeStateItem(
                state_id="state_depth_violation",
                stage=LifeStage.UNDERGRADUATE,
                title="Student",
                interval=interval,
                temporal_horizon=TemporalHorizon.PRESENT,
                epistemic_grounding=EpistemicGrounding.DERIVED,
                canonicality=Canonicality.NON_CANONICAL,
                propagation_depth=3,  # VIOLATION (> 2)!
            )

    # -------------------------------------------------------------------------
    # 11. Constants & Cardinality Limits (Implementation Locks 1 & 6)
    # -------------------------------------------------------------------------
    def test_cardinality_constants_configured(self):
        """Verify architectural lock constants."""
        assert MAX_COMPATIBLE_TRAJECTORIES == 3
        assert MAX_TEMPORAL_PROPAGATION_HOPS == 2
        assert MAX_PROJECTED_NODES == 4

    # -------------------------------------------------------------------------
    # 12. AST Audit: Zero Forbidden Imports & Boundary Violations
    # -------------------------------------------------------------------------
    def test_ast_audit_temporal_models(self):
        """Verify temporal_models.py contains 0 network imports, 0 DB calls, 0 RBE, 0 set_fact."""
        target_path = pathlib.Path(__file__).parent.parent / "app" / "reality" / "temporal_models.py"
        assert target_path.exists(), "temporal_models.py must exist"

        content = target_path.read_text(encoding="utf-8")

        # 1. No RealityBeliefEngine
        assert "RealityBeliefEngine" not in content

        # 2. No set_fact
        assert "set_fact" not in content

        # 3. No token minting
        assert "PromotionAuthorizationToken" not in content

        # 4. No network client imports
        forbidden_modules = {"requests", "httpx", "aiohttp", "urllib", "urllib3", "sqlalchemy"}
        tree = ast.parse(content, filename=str(target_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod_root = alias.name.split(".")[0]
                    assert mod_root not in forbidden_modules, f"Forbidden import: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    mod_root = node.module.split(".")[0]
                    assert mod_root not in forbidden_modules, f"Forbidden import from: {node.module}"
