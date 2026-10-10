"""Phase 14.2 — Constraint Evaluation Engine Tests.

Tests cover:
  1. DTO immutability (frozen=True, extra="forbid")
  2. Hard constraint evaluation (temporal, physical, canonical contradiction)
  3. Soft constraint evaluation & Lock 5 asymmetry (deterministic scoring, never probability)
  4. Lock 6 (Absence != Contradiction: unpopulated slots yield NEUTRAL)
  5. Stereotype-Free Feasibility (parental background/ethnicity never used as penalty)
  6. Composite ConstraintSetEvaluator aggregation
  7. Authority boundary AST audit (0 set_fact, 0 token minting, 0 DB writes)
  8. Scope discipline (no forward-phase 14.3+ symbols)

Golden Suite 14 Cluster 2: GC-357 ~ GC-361 (5 constitutional acceptance benchmarks)
"""

import ast
from pathlib import Path
from typing import Any
import pytest
from pydantic import ValidationError

from app.character.core_models import CharacterCore
from app.reality.constraint_engine import (
    ConstraintClass,
    ConstraintEvaluationResult,
    ConstraintSetEvaluator,
    ConstraintType,
    HardConstraintEvaluator,
    SlotConstraintProfile,
    SoftConstraintEvaluator,
)
from app.reality.models import CoreFactItem, FactAuthority, FactSource, FactStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_core(
    facts_dict: dict[str, tuple[Any, bool]],  # key -> (value, is_locked)
    interests: list[str] | None = None,
) -> CharacterCore:
    facts = {}
    for k, (val, locked) in facts_dict.items():
        category = k.split(".")[0]
        authority = FactAuthority.USER_LOCKED if locked else FactAuthority.AEVUM_CANONICAL
        facts[k] = CoreFactItem(
            key=k,
            value=val,
            category=category,
            source=FactSource.SYSTEM_BASELINE,
            authority=authority,
            status=FactStatus.CANONICAL,
            locked=locked,
        )
    if interests is not None:
        facts["interests"] = CoreFactItem(
            key="interests",
            value=interests,
            category="lifestyle",
            source=FactSource.SYSTEM_BASELINE,
            authority=FactAuthority.AEVUM_CANONICAL,
            status=FactStatus.CANONICAL,
            locked=False,
        )
    return CharacterCore(character_id="aevum", facts=facts)


# ---------------------------------------------------------------------------
# 1. DTO Immutability
# ---------------------------------------------------------------------------

class TestConstraintDTOImmutability:
    """Gate 1: ConstraintEvaluationResult & SlotConstraintProfile are frozen."""

    def test_constraint_evaluation_result_is_frozen(self):
        res = ConstraintEvaluationResult(
            constraint_id="c1",
            constraint_type=ConstraintType.TEMPORAL_IMPOSSIBILITY,
            constraint_class=ConstraintClass.HARD_REJECT,
            is_hard_rejected=True,
            penalty_weight=1.0,
            reason="Temporal violation",
            evaluated_slot="education.major",
        )
        with pytest.raises(Exception):
            res.is_hard_rejected = False  # type: ignore[misc]

    def test_constraint_evaluation_result_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            ConstraintEvaluationResult(
                constraint_id="c1",
                constraint_type=ConstraintType.TEMPORAL_IMPOSSIBILITY,
                constraint_class=ConstraintClass.HARD_REJECT,
                reason="Temporal violation",
                evaluated_slot="education.major",
                illegal_extra="forbidden",  # type: ignore[call-arg]
            )

    def test_slot_constraint_profile_is_frozen(self):
        prof = SlotConstraintProfile(
            slot="education.major",
            is_hard_rejected=False,
            total_penalty_weight=0.15,
        )
        with pytest.raises(Exception):
            prof.total_penalty_weight = 0.99  # type: ignore[misc]

    def test_penalty_weight_bounds_enforced(self):
        with pytest.raises(ValidationError):
            ConstraintEvaluationResult(
                constraint_id="c1",
                constraint_type=ConstraintType.TEMPERAMENT_AFFINITY,
                constraint_class=ConstraintClass.SOFT_PENALTY,
                penalty_weight=1.5,  # > 1.0 invalid
                reason="Invalid weight",
                evaluated_slot="education.major",
            )
        with pytest.raises(ValidationError):
            ConstraintEvaluationResult(
                constraint_id="c1",
                constraint_type=ConstraintType.TEMPERAMENT_AFFINITY,
                constraint_class=ConstraintClass.SOFT_PENALTY,
                penalty_weight=-0.1,  # < 0.0 invalid
                reason="Invalid weight",
                evaluated_slot="education.major",
            )


# ---------------------------------------------------------------------------
# 2. Hard Constraint Evaluation
# ---------------------------------------------------------------------------

class TestHardConstraintEvaluator:
    """Gate 2: Hard constraints reject outright with is_hard_rejected=True, penalty=1.0."""

    def test_true_temporal_childhood_impossibility_at_age_10_rejected(self):
        """Child age <= 10 attempting university is ontological/developmental impossibility."""
        evaluator = HardConstraintEvaluator()
        core = _build_core({})
        res = evaluator.evaluate_temporal("education.major", "Computer Science", core, age=10)

        assert res.constraint_class == ConstraintClass.HARD_REJECT
        assert res.is_hard_rejected is True
        assert res.penalty_weight == 1.0
        assert "developmentally impossible" in res.reason

    def test_temporal_academic_year_range_violation_rejected(self):
        """Academic year < 1 or > 6 is a structural boundary impossibility."""
        evaluator = HardConstraintEvaluator()
        core = _build_core({})
        res = evaluator.evaluate_temporal("education.year", 8, core, age=20)

        assert res.constraint_class == ConstraintClass.HARD_REJECT
        assert res.is_hard_rejected is True
        assert res.penalty_weight == 1.0
        assert "outside standard structural range" in res.reason

    def test_temporal_early_progression_at_age_16_is_soft_penalty_not_hard_reject(self):
        """Unusual != Impossible: Age 16 university entry is atypical progression, NEVER hard reject."""
        evaluator = HardConstraintEvaluator()
        core = _build_core({})
        res = evaluator.evaluate_temporal("education.major", "Computer Science", core, age=16)

        assert res.constraint_class == ConstraintClass.SOFT_PENALTY
        assert res.is_hard_rejected is False
        assert res.penalty_weight == 0.20
        assert "Unusual != Impossible" in res.reason

    def test_temporal_undergraduate_at_age_20_accepted(self):
        evaluator = HardConstraintEvaluator()
        core = _build_core({"identity.age": (20, True)})
        res = evaluator.evaluate_temporal("education.major", "Computer Science", core)

        assert res.constraint_class == ConstraintClass.NEUTRAL
        assert res.is_hard_rejected is False
        assert res.penalty_weight == 0.0

    def test_physical_natural_law_violation_rejected(self):
        evaluator = HardConstraintEvaluator()
        res = evaluator.evaluate_physical("world.astronomy.sun_rises", "west")

        assert res.constraint_class == ConstraintClass.HARD_REJECT
        assert res.is_hard_rejected is True
        assert res.penalty_weight == 1.0
        assert "immutable physical natural laws" in res.reason

    def test_canonical_user_lock_conflict_rejected(self):
        evaluator = HardConstraintEvaluator()
        core = _build_core({"education.university": ("Universiti Malaya", True)})
        res = evaluator.evaluate_canonical_contradiction(
            "education.university", "Universiti Sains Malaysia", core
        )

        assert res.constraint_class == ConstraintClass.HARD_REJECT
        assert res.is_hard_rejected is True
        assert res.penalty_weight == 1.0
        assert "USER_LOCKED" in res.reason

    def test_canonical_identity_name_conflict_rejected(self):
        evaluator = HardConstraintEvaluator()
        core = _build_core({"identity.name": ("Aevum", False)})
        res = evaluator.evaluate_canonical_contradiction("identity.name", "Alice", core)

        assert res.constraint_class == ConstraintClass.HARD_REJECT
        assert res.is_hard_rejected is True
        assert res.penalty_weight == 1.0
        assert "Canonical name" in res.reason


# ---------------------------------------------------------------------------
# 3. Soft Constraint Evaluation & Lock 5 Asymmetry
# ---------------------------------------------------------------------------

class TestSoftConstraintEvaluator:
    """Gate 3: Soft constraints NEVER set is_hard_rejected=True; penalty in [0.0, 1.0]."""

    def test_temperament_positive_affinity_yields_neutral(self):
        evaluator = SoftConstraintEvaluator()
        core = _build_core({}, interests=["programming", "data science"])
        res = evaluator.evaluate_temperament_affinity("education.major", "Data Science", core)

        assert res.constraint_class == ConstraintClass.NEUTRAL
        assert res.is_hard_rejected is False
        assert res.penalty_weight == 0.0

    def test_temperament_mild_friction_yields_soft_penalty(self):
        evaluator = SoftConstraintEvaluator()
        core = _build_core({}, interests=["botany", "classical music"])
        res = evaluator.evaluate_temperament_affinity("education.major", "Mining Engineering", core)

        assert res.constraint_class == ConstraintClass.SOFT_PENALTY
        assert res.is_hard_rejected is False
        assert res.penalty_weight == 0.15
        assert "friction" in res.reason

    def test_resource_high_cost_yields_soft_penalty(self):
        evaluator = SoftConstraintEvaluator()
        core = _build_core({"location.residence": ("Penang", False)})
        res = evaluator.evaluate_resource_plausibility(
            "education.pathway", "expensive_private_ivy_league", core
        )

        assert res.constraint_class == ConstraintClass.SOFT_PENALTY
        assert res.is_hard_rejected is False
        assert res.penalty_weight == 0.30

    def test_social_cross_state_commute_yields_soft_penalty(self):
        evaluator = SoftConstraintEvaluator()
        core = _build_core({"location.residence": ("Penang", False)})
        res = evaluator.evaluate_social_environment_fit(
            "lifestyle.daily_study", "kuala_lumpur_campus_library", core
        )

        assert res.constraint_class == ConstraintClass.SOFT_PENALTY
        assert res.is_hard_rejected is False
        assert res.penalty_weight == 0.25


# ---------------------------------------------------------------------------
# 4. Lock 6: Absence != Contradiction
# ---------------------------------------------------------------------------

class TestAbsenceIsNotContradiction:
    """Gate 4: Lock 6 — unpopulated slots or missing evidence yield NEUTRAL."""

    def test_unpopulated_core_slot_yields_neutral(self):
        evaluator = HardConstraintEvaluator()
        core = _build_core({})  # Empty core
        res = evaluator.evaluate_canonical_contradiction("education.major", "Chemistry", core)

        assert res.constraint_class == ConstraintClass.NEUTRAL
        assert res.is_hard_rejected is False
        assert res.penalty_weight == 0.0
        assert "Lock 6" in res.reason

    def test_missing_interests_yields_neutral(self):
        evaluator = SoftConstraintEvaluator()
        core = _build_core({})  # No interests recorded
        res = evaluator.evaluate_temperament_affinity("education.major", "Philosophy", core)

        assert res.constraint_class == ConstraintClass.NEUTRAL
        assert res.is_hard_rejected is False
        assert res.penalty_weight == 0.0
        assert "Lock 6" in res.reason

    def test_none_core_yields_neutral(self):
        evaluator = HardConstraintEvaluator()
        res = evaluator.evaluate_canonical_contradiction("education.major", "History", None)
        assert res.constraint_class == ConstraintClass.NEUTRAL
        assert res.is_hard_rejected is False


# ---------------------------------------------------------------------------
# 5. Stereotype-Free Feasibility
# ---------------------------------------------------------------------------

class TestStereotypeFreeFeasibility:
    """Gate 5: Parental occupation/ethnicity must NEVER imply wealth or cause penalty."""

    def test_parental_occupation_and_ethnicity_ignored(self):
        evaluator = SoftConstraintEvaluator()
        # Create core with explicit parental occupation and ethnicity
        core = _build_core({
            "family.father_occupation": ("Fisherman", True),
            "family.mother_occupation": ("Homemaker", True),
            "family.ethnicity": ("Malay", True),
        })

        res = evaluator.evaluate_resource_plausibility(
            "education.major", "Computer Science", core
        )
        # Standard major should be NEUTRAL, regardless of parental occupation
        assert res.constraint_class == ConstraintClass.NEUTRAL
        assert res.is_hard_rejected is False
        assert res.penalty_weight == 0.0


# ---------------------------------------------------------------------------
# 6. Composite ConstraintSetEvaluator
# ---------------------------------------------------------------------------

class TestConstraintSetEvaluator:
    """Gate 6: Composes all evaluators, computes total penalty & hard reject flag."""

    def test_hard_rejection_overrides_soft_penalties(self):
        evaluator = ConstraintSetEvaluator()
        # Age 10 (ontological childhood reject) + interest mismatch (soft penalty)
        core = _build_core(
            {},
            interests=["botany"],
        )
        profile = evaluator.evaluate("education.major", "Mining Engineering", core, age=10)

        assert profile.is_hard_rejected is True
        assert profile.total_penalty_weight == 1.0
        assert len(profile.hard_reject_reasons) > 0
        assert len(profile.soft_penalty_reasons) > 0

    def test_atypical_progression_with_interest_mismatch_accumulates_soft_penalties_without_rejection(self):
        evaluator = ConstraintSetEvaluator()
        # Age 16 (rare/atypical progression: 0.20) + interest mismatch (0.15) -> 0.35 total penalty
        # Unusual != Impossible: is_hard_rejected MUST remain False!
        core = _build_core(
            {},
            interests=["botany"],
        )
        profile = evaluator.evaluate("education.major", "Mining Engineering", core, age=16)

        assert profile.is_hard_rejected is False
        assert profile.total_penalty_weight == 0.35
        assert len(profile.hard_reject_reasons) == 0
        assert len(profile.soft_penalty_reasons) == 2

    def test_soft_penalties_are_summed_and_clamped(self):
        evaluator = ConstraintSetEvaluator()
        # Age 20 (valid) + interest mismatch (0.15) + expensive (0.30)
        core = _build_core(
            {"identity.age": (20, True)},
            interests=["music"],
        )
        profile = evaluator.evaluate(
            "education.pathway", "expensive_private_ivy_league", core
        )

        assert profile.is_hard_rejected is False
        assert profile.total_penalty_weight == 0.45  # 0.15 + 0.30
        assert len(profile.hard_reject_reasons) == 0
        assert len(profile.soft_penalty_reasons) == 2

    def test_completely_clean_candidate_yields_zero_penalty(self):
        evaluator = ConstraintSetEvaluator()
        core = _build_core(
            {"identity.age": (20, True)},
            interests=["computing", "math"],
        )
        profile = evaluator.evaluate("education.major", "computing", core)

        assert profile.is_hard_rejected is False
        assert profile.total_penalty_weight == 0.0
        assert len(profile.hard_reject_reasons) == 0
        assert len(profile.soft_penalty_reasons) == 0


# ---------------------------------------------------------------------------
# 7. Authority Boundary (AST Audit)
# ---------------------------------------------------------------------------

class TestConstraintEngineAuthorityBoundary:
    """Gate 7: constraint_engine.py must not reference forbidden symbols."""

    _FORBIDDEN_NAMES = {
        "set_fact",
        "BiographyPromotionService",
        "PromotionAuthorizationToken",
        "AsyncSession",
        "create_async_engine",
        "LLMProvider",
        "httpx",
        "requests",
        "aiohttp",
        "CycleIsolationLedger",         # Phase 14.3
        "RealityConstructionOrchestrator",  # Phase 14.3
        "BeliefRevisionRecord",          # Phase 14.4
        "BeliefMaturity",                # Phase 14.5
    }

    def _load_ast(self) -> ast.Module:
        path = Path(__file__).parent.parent / "app" / "reality" / "constraint_engine.py"
        return ast.parse(path.read_text(encoding="utf-8"))

    def test_no_forbidden_names_in_constraint_engine(self):
        tree = self._load_ast()
        found = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in self._FORBIDDEN_NAMES:
                found.append(node.id)
            elif isinstance(node, ast.Attribute) and node.attr in self._FORBIDDEN_NAMES:
                found.append(node.attr)
        assert found == [], (
            f"Forbidden symbols found in constraint_engine.py: {sorted(set(found))}"
        )


# ---------------------------------------------------------------------------
# 8. Golden Suite 14 — Cluster 2: GC-357 ~ GC-361
# ---------------------------------------------------------------------------

class TestGoldenSuite14Cluster2:
    """GC-357 ~ GC-361 — Constitutional acceptance benchmarks for Phase 14.2."""

    def test_gc357_hard_constraint_rejection_outright(self):
        """GC-357: Hard constraint violations reject outright with is_hard_rejected=True."""
        evaluator = HardConstraintEvaluator()
        core = _build_core({"education.level": ("Undergraduate", True)})
        # Attempt to contradict locked education level
        res = evaluator.evaluate_canonical_contradiction(
            "education.level", "Secondary School", core
        )
        assert res.is_hard_rejected is True
        assert res.penalty_weight == 1.0

    def test_gc358_soft_constraint_deterministic_penalty_without_disqualification(self):
        """GC-358: Soft constraints reduce score via penalty_weight, never reject."""
        evaluator = SoftConstraintEvaluator()
        core = _build_core({}, interests=["literature"])
        res = evaluator.evaluate_temperament_affinity("education.major", "Civil Engineering", core)

        assert res.constraint_class == ConstraintClass.SOFT_PENALTY
        assert res.is_hard_rejected is False
        assert 0.0 < res.penalty_weight <= 1.0

    def test_gc359_absence_is_not_contradiction(self):
        """GC-359: Missing evidence yields NEUTRAL, never HARD_REJECT (Lock 6)."""
        evaluator = ConstraintSetEvaluator()
        core = _build_core({})  # completely open core
        profile = evaluator.evaluate("education.major", "Mathematics", core)

        assert profile.is_hard_rejected is False
        assert profile.total_penalty_weight == 0.0

    def test_gc360_stereotype_free_resource_feasibility(self):
        """GC-360: Family occupation or ethnicity never causes financial penalty."""
        evaluator = SoftConstraintEvaluator()
        core = _build_core({
            "family.father_occupation": ("Hawker", True),
            "family.ethnicity": ("Chinese", True),
        })
        res = evaluator.evaluate_resource_plausibility("education.major", "Accountancy", core)
        assert res.constraint_class == ConstraintClass.NEUTRAL
        assert res.penalty_weight == 0.0

    def test_gc361_constraint_set_evaluator_ast_authority_boundary(self):
        """GC-361: ConstraintSetEvaluator enforces 0 direct mutation calls via AST."""
        path = Path(__file__).parent.parent / "app" / "reality" / "constraint_engine.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden = {"set_fact", "PromotionAuthorizationToken", "BiographyPromotionService"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden:
                pytest.fail(f"Forbidden name '{node.id}' in constraint_engine.py AST")
            elif isinstance(node, ast.Attribute) and node.attr in forbidden:
                pytest.fail(f"Forbidden attribute '{node.attr}' in constraint_engine.py AST")
