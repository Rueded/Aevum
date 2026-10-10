"""Unit tests for Phase 8A.2 InferenceOpportunityDetector.

Verifies:
1. Empty HIGH-value slot with sufficient relevant premises triggers request.
2. Already canonical slot is skipped (Gate 1).
3. User-locked slot is skipped (Gate 1).
4. Active candidate hypothesis prevents duplicate opportunity (Gate 2).
5. LOW-value slot is skipped (Gate 4).
6. ZERO-value slot is skipped (Gate 4).
7. HIGH-value slot with insufficient premises is skipped (Gate 5).
8. Irrelevant lifestyle facts (beverage, color, transit) do not satisfy premise sufficiency.
9. Single pivotal premise satisfies simple supported slot (education.pathway).
10. Complex slot (education.major) requires converging dimensions (>= 2 distinct functional dimensions).
11. Inferred-only premises cannot satisfy primary-anchor requirement (Gate 6).
12. Mixed primary + inferred premises satisfy primary-anchor requirement.
13. Cycle budget: At most one target slot emitted per detector invocation.
14. Cooldown prevents opportunity (Gate 3).
15. Bounded proposal request exposes no raw transcripts or unrestricted biography.
16. Premise snapshots in request are strictly bounded.
17. Proof: Detector performs no canonical mutation (zero set_fact, zero tokens).
18. Proof: Detector performs no LLM or tool calls.
19. Repeated invocation is 100% deterministic.
20. Async convenience method correctly pre-fetches active candidate slots.
"""

import ast
from pathlib import Path
import pytest

from app.character.core_models import CharacterCore
from app.reality.candidate_models import (
    CandidateHypothesis,
    CandidateLifecycleState,
    InferenceEdgeType,
    PlausibilityBreakdown,
    ProvenanceLineage,
    RealityTaxonomy,
)
from app.reality.inference_opportunity_detector import InferenceOpportunityDetector
from app.reality.models import CoreFactItem, FactAuthority, FactSource, FactStatus


def _create_core(facts: dict[str, CoreFactItem]) -> CharacterCore:
    return CharacterCore(character_id="aevum", facts=facts)


def _fact(
    key: str,
    category: str,
    value: object,
    source: FactSource = FactSource.USER_CONFIGURED,
    authority: FactAuthority = FactAuthority.USER_CONFIGURED,
    status: FactStatus = FactStatus.CANONICAL,
    locked: bool = False,
) -> CoreFactItem:
    return CoreFactItem(
        key=key,
        category=category,
        value=value,
        source=source,
        authority=authority,
        status=status,
        locked=locked,
    )


# =============================================================================
# 1. Gate 1: Slot State (Canonical / User-Locked)
# =============================================================================


def test_detector_skips_already_canonical_slot() -> None:
    core = _create_core({
        "education.major": _fact("education.major", "education", "computer_science"),
        "traits.musical_talent": _fact("traits.musical_talent", "traits", True),
        "academics.spm_math_grade": _fact("academics.spm_math_grade", "academics", "A"),
    })
    res = InferenceOpportunityDetector.detect_opportunity(core, requested_slot="education.major")
    assert res is None


def test_detector_skips_user_locked_slot() -> None:
    core = _create_core({
        "education.major": _fact(
            "education.major",
            "education",
            "music_performance",
            authority=FactAuthority.USER_LOCKED,
            locked=True,
        ),
        "traits.musical_talent": _fact("traits.musical_talent", "traits", True),
    })
    res = InferenceOpportunityDetector.detect_opportunity(core, requested_slot="education.major")
    assert res is None


# =============================================================================
# 2. Gate 2: Active Candidate Prevention
# =============================================================================


def test_detector_skips_slot_with_active_candidate() -> None:
    core = _create_core({
        "traits.musical_talent": _fact("traits.musical_talent", "traits", True),
        "academics.spm_math_grade": _fact("academics.spm_math_grade", "academics", "A"),
    })
    # Active candidate exists for education.major
    active_slots = {"education.major"}
    res = InferenceOpportunityDetector.detect_opportunity(
        core,
        active_candidate_slots=active_slots,
        requested_slot="education.major",
    )
    assert res is None


# =============================================================================
# 3. Gate 3: Cooldown
# =============================================================================


def test_detector_skips_slot_in_cooldown() -> None:
    core = _create_core({
        "traits.musical_talent": _fact("traits.musical_talent", "traits", True),
        "academics.spm_math_grade": _fact("academics.spm_math_grade", "academics", "A"),
    })
    res = InferenceOpportunityDetector.detect_opportunity(
        core,
        cooldown_slots={"education.major"},
        requested_slot="education.major",
    )
    assert res is None


# =============================================================================
# 4. Gate 4: Inference Value (LOW / ZERO Tiers)
# =============================================================================


def test_detector_skips_low_value_slot() -> None:
    core = _create_core({
        "preferences.study_beverage": _fact("preferences.study_beverage", "preferences", "tea"),
    })
    res = InferenceOpportunityDetector.detect_opportunity(
        core,
        requested_slot="preferences.study_beverage",
    )
    assert res is None


def test_detector_skips_forbidden_zero_value_slot() -> None:
    core = _create_core({})
    res = InferenceOpportunityDetector.detect_opportunity(
        core,
        requested_slot="identity.name",
    )
    assert res is None


# =============================================================================
# 5. Gate 5: Premise Sufficiency & Irrelevant Fact Exclusion
# =============================================================================


def test_detector_skips_high_value_slot_with_zero_premises() -> None:
    # Empty core with zero facts
    core = _create_core({})
    res = InferenceOpportunityDetector.detect_opportunity(core, requested_slot="education.major")
    assert res is None


def test_irrelevant_lifestyle_facts_do_not_satisfy_sufficiency() -> None:
    # Character only has trivial preferences (beverage, color, transit)
    core = _create_core({
        "preferences.study_beverage": _fact("preferences.study_beverage", "preferences", "matcha"),
        "preferences.favorite_color": _fact("preferences.favorite_color", "preferences", "blue"),
        "lifestyle.transit": _fact("lifestyle.transit", "lifestyle", "lrt"),
    })
    res = InferenceOpportunityDetector.detect_opportunity(core, requested_slot="education.major")
    assert res is None


def test_single_pivotal_premise_satisfies_education_pathway() -> None:
    # For education.pathway, high school / SPM academic readiness is a single pivotal fact!
    core = _create_core({
        "academics.spm_overall": _fact("academics.spm_overall", "academics", "8A 1B"),
    })
    res = InferenceOpportunityDetector.detect_opportunity(core, requested_slot="education.pathway")
    assert res is not None
    assert res.target_slot == "education.pathway"
    assert res.domain == "education"
    assert "academics.spm_overall" in res.authorized_premise_keys


def test_complex_slot_requires_converging_dimensions() -> None:
    # For education.major, 1 single fact (e.g. only math grade) is NOT sufficient
    single_fact_core = _create_core({
        "academics.spm_math_grade": _fact("academics.spm_math_grade", "academics", "A"),
    })
    res_single = InferenceOpportunityDetector.detect_opportunity(
        single_fact_core,
        requested_slot="education.major",
    )
    assert res_single is None  # Fails premise sufficiency: only 1 dimension

    # Adding a converging second dimension (e.g. talents_skills: musical_talent) makes it sufficient!
    converging_core = _create_core({
        "academics.spm_math_grade": _fact("academics.spm_math_grade", "academics", "A"),
        "traits.musical_talent": _fact("traits.musical_talent", "traits", True),
    })
    res_converging = InferenceOpportunityDetector.detect_opportunity(
        converging_core,
        requested_slot="education.major",
    )
    assert res_converging is not None
    assert res_converging.target_slot == "education.major"
    assert "academics.spm_math_grade" in res_converging.authorized_premise_keys
    assert "traits.musical_talent" in res_converging.authorized_premise_keys


# =============================================================================
# 6. Gate 6: Primary Canonical Anchor
# =============================================================================


def test_inferred_only_premises_fail_primary_anchor_gate() -> None:
    # All relevant facts were derived/inferred (FactSource.AEVUM_INFERRED)
    core = _create_core({
        "academics.spm_math_grade": _fact(
            "academics.spm_math_grade",
            "academics",
            "A",
            source=FactSource.AEVUM_INFERRED,
            authority=FactAuthority.AEVUM_CANONICAL,
        ),
        "traits.musical_talent": _fact(
            "traits.musical_talent",
            "traits",
            True,
            source=FactSource.AEVUM_INFERRED,
            authority=FactAuthority.AEVUM_CANONICAL,
        ),
    })
    # Must fail Gate 6: purely derived chain without primary canonical anchor is blocked
    res = InferenceOpportunityDetector.detect_opportunity(core, requested_slot="education.major")
    assert res is None


def test_mixed_primary_and_inferred_premises_pass_anchor_gate() -> None:
    # One primary canonical fact + one derived fact
    core = _create_core({
        "academics.spm_math_grade": _fact(
            "academics.spm_math_grade",
            "academics",
            "A",
            source=FactSource.CONVERSATION,  # Primary canonical!
            authority=FactAuthority.AEVUM_CANONICAL,
        ),
        "traits.musical_talent": _fact(
            "traits.musical_talent",
            "traits",
            True,
            source=FactSource.AEVUM_INFERRED,  # Derived
            authority=FactAuthority.AEVUM_CANONICAL,
        ),
    })
    res = InferenceOpportunityDetector.detect_opportunity(core, requested_slot="education.major")
    assert res is not None
    assert "academics.spm_math_grade" in res.authorized_premise_keys
    assert "traits.musical_talent" in res.authorized_premise_keys


# =============================================================================
# 7. Cycle Budget & Bounded Request Structure
# =============================================================================


def test_cycle_budget_emits_at_most_one_slot() -> None:
    # Core has facts qualifying both pathway and major
    core = _create_core({
        "academics.spm_overall": _fact("academics.spm_overall", "academics", "Straight As"),
        "traits.musical_talent": _fact("traits.musical_talent", "traits", True),
        "academics.spm_math_grade": _fact("academics.spm_math_grade", "academics", "A"),
    })
    # Invocation without requested_slot evaluates priority sequence
    res = InferenceOpportunityDetector.detect_opportunity(core, cycle_id="cycle_test_01")
    assert res is not None
    # Strictly returns ONE single slot (first eligible in priority)
    assert res.target_slot in ("education.pathway", "education.major")
    assert isinstance(res.target_slot, str)


def test_request_contains_only_bounded_information() -> None:
    core = _create_core({
        "academics.spm_overall": _fact("academics.spm_overall", "academics", "8A 1B"),
        "preferences.favorite_color": _fact("preferences.favorite_color", "preferences", "blue"),
    })
    res = InferenceOpportunityDetector.detect_opportunity(core, requested_slot="education.pathway")
    assert res is not None
    # Irrelevant facts must NOT appear in premise keys or snapshots
    assert "preferences.favorite_color" not in res.authorized_premise_keys
    assert "preferences.favorite_color" not in res.premise_snapshots
    # Known constraints must be present
    assert len(res.known_constraints) > 0


def test_repeated_invocation_is_deterministic() -> None:
    core = _create_core({
        "academics.spm_overall": _fact("academics.spm_overall", "academics", "8A"),
        "traits.challenge_preference": _fact("traits.challenge_preference", "traits", "HIGH"),
    })
    res1 = InferenceOpportunityDetector.detect_opportunity(core, cycle_id="det_cycle")
    res2 = InferenceOpportunityDetector.detect_opportunity(core, cycle_id="det_cycle")
    assert res1 is not None and res2 is not None
    assert res1.target_slot == res2.target_slot
    assert res1.authorized_premise_keys == res2.authorized_premise_keys
    assert res1.premise_snapshots == res2.premise_snapshots


# =============================================================================
# 8. AST Audits: Zero Canonical Mutation, Zero LLM Calls, Zero Tools
# =============================================================================


def test_detector_ast_audit_zero_mutation_and_zero_llm() -> None:
    detector_path = Path("d:/Aevum/Aevum/backend/app/reality/inference_opportunity_detector.py")
    assert detector_path.exists()
    tree = ast.parse(detector_path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            # Prohibit set_fact
            if isinstance(func, ast.Attribute) and func.attr == "set_fact":
                pytest.fail(f"Unauthorized set_fact() found in detector:{node.lineno}")
            # Prohibit PromotionAuthorizationToken.create
            if isinstance(func, ast.Attribute) and func.attr == "create":
                if isinstance(func.value, ast.Name) and func.value.id == "PromotionAuthorizationToken":
                    pytest.fail(f"Unauthorized token creation in detector:{node.lineno}")
            # Prohibit DB commit/flush
            if isinstance(func, ast.Attribute) and func.attr in ("commit", "flush", "rollback"):
                pytest.fail(f"Unauthorized DB transaction in detector:{node.lineno}")
            # Prohibit LLM generation calls
            if isinstance(func, ast.Attribute) and func.attr in ("generate_content", "chat", "create_completion"):
                pytest.fail(f"Unauthorized LLM call in detector:{node.lineno}")


# =============================================================================
# 9. Additional Domain & Stereotype Boundaries
# =============================================================================


def test_career_aspiration_pivotal_and_converging() -> None:
    # 1. Pivotal: established major satisfies career aspiration
    major_core = _create_core({
        "education.major": _fact("education.major", "education", "computer_science"),
    })
    res_major = InferenceOpportunityDetector.detect_opportunity(
        major_core,
        requested_slot="career.aspiration",
    )
    assert res_major is not None
    assert res_major.target_slot == "career.aspiration"
    assert "education.major" in res_major.authorized_premise_keys

    # 2. Converging: skills + interests (without major) satisfies career aspiration
    skills_core = _create_core({
        "skills.programming": _fact("skills.programming", "skills", "Python"),
        "interests": _fact("interests", "interests", ["gaming", "coding"]),
    })
    res_skills = InferenceOpportunityDetector.detect_opportunity(
        skills_core,
        requested_slot="career.aspiration",
    )
    assert res_skills is not None
    assert res_skills.target_slot == "career.aspiration"


def test_parent_occupation_alone_does_not_satisfy_sufficiency() -> None:
    # Parental occupation alone is not financial capacity and does not satisfy premise sufficiency
    core = _create_core({
        "family.background": _fact("family.background", "family", "Parents are doctors"),
    })
    res = InferenceOpportunityDetector.detect_opportunity(core, requested_slot="education.major")
    assert res is None


def test_unsupported_slot_returns_none() -> None:
    core = _create_core({
        "identity.age": _fact("identity.age", "identity", 20),
    })
    res = InferenceOpportunityDetector.detect_opportunity(
        core,
        requested_slot="unsupported.custom_slot",
    )
    assert res is None


@pytest.mark.asyncio
async def test_async_convenience_method_filters_active_candidates() -> None:
    from unittest.mock import AsyncMock, MagicMock
    from app.reality.candidate_models import CandidateHypothesis, CandidateLifecycleState

    core = _create_core({
        "traits.musical_talent": _fact("traits.musical_talent", "traits", True),
        "academics.spm_math_grade": _fact("academics.spm_math_grade", "academics", "A"),
    })

    # Mock candidate repository returning an active candidate for education.major
    mock_repo = MagicMock()
    mock_candidate = MagicMock(spec=CandidateHypothesis)
    mock_candidate.slot_name = "education.major"
    mock_candidate.is_quarantined = False
    mock_candidate.lifecycle_state = CandidateLifecycleState.ACTIVE
    mock_repo.get_all_active_candidates = AsyncMock(return_value=[mock_candidate])

    res = await InferenceOpportunityDetector.detect_opportunity_async(
        core=core,
        candidate_repo=mock_repo,
        requested_slot="education.major",
    )
    assert res is None  # Blocked by active candidate!

