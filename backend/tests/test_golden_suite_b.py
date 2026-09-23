"""Executable validation for Golden Suite B: Emergent Reality (GC-013 ~ GC-018).

Phase 7B.3 Architectural Invariants:
- Validates plausible constrained emergence of unspecified personal details.
- Validates chronological timeline causality (STPM duration, undergraduate entry age).
- Validates anti-snowballing boundaries and policy-gated promotion.
- Validates longitudinal multi-turn stability (emergent facts bind subsequent reality).
- Validates user profile editor synchronization (GC-018).
- golden_conversations.json fixture remains 100% frozen and untouched.
"""

import json
from pathlib import Path
import pytest

from app.character.core_models import CharacterCore
from app.character.engine import CharacterEngine
from app.reality.belief_engine import RealityBeliefEngine
from app.reality.candidate_models import InferenceScope, RealityImpact
from app.reality.history_service import RealityHistoryService
from app.reality.models import CoreFactItem, FactAuthority, FactSource, FactStatus
from app.reality.promotion_models import PromotionType
from app.reality.promotion_service import RealityPromotionService


@pytest.fixture(scope="module")
def golden_suite():
    """Load frozen golden_conversations.json fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "golden_conversations.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {case["id"]: case for case in data["cases"]}


def _build_core_from_preconditions(pre: dict) -> CharacterCore:
    facts: dict[str, CoreFactItem] = {}
    core_dict = pre.get("character_core", {})

    for k, v in core_dict.items():
        if v is not None:
            norm_key = "identity.age" if k == "age" else k
            cat = norm_key.split(".")[0]
            facts[norm_key] = CoreFactItem(
                key=norm_key,
                category=cat,
                value=v,
                source=FactSource.SYSTEM_BASELINE,
                authority=FactAuthority.SYSTEM_BASELINE,
                status=FactStatus.CANONICAL,
            )
    return CharacterCore(character_id="aevum", facts=facts)


@pytest.mark.asyncio
async def test_gc013_unspecified_education_emergent_inference(golden_suite) -> None:
    """GC-013: Unspecified education inferable from prior anchors with longitudinal stability."""
    case = golden_suite["GC-013"]
    pre = case["preconditions"]
    user_text = case["turns"][0]["user"]

    engine = RealityBeliefEngine()
    core = _build_core_from_preconditions(pre)

    # Turn 1: Emergent inference from anchors
    res1 = await engine.process_turn(user_text, core=core)

    assert res1.promotion is not None
    assert res1.promotion.promotion_type == PromotionType.DIRECT_CANONICAL
    assert res1.candidate is not None
    assert res1.candidate.fact_key == "education.university"
    assert res1.candidate.value is not None

    # Verify plausibility of chosen institution (open set plausible: Malaysian university)
    chosen_uni = str(res1.candidate.value)
    assert any(uni in chosen_uni for uni in ["USM", "UM", "Universiti Sains Malaysia", "Universiti Malaya"])

    # Turn 2: Longitudinal stability (the chosen university must remain stable)
    # Simulate core updated with the newly promoted fact
    updated_facts = dict(core.facts)
    updated_facts["education.university"] = CoreFactItem(
        key="education.university",
        category="education",
        value=chosen_uni,
        source=FactSource.AEVUM_INFERRED,
        authority=FactAuthority.AEVUM_CANONICAL,
        status=FactStatus.CANONICAL,
    )
    core_turn2 = CharacterCore(character_id="aevum", facts=updated_facts)

    res2 = await engine.process_turn(user_text, core=core_turn2)
    assert res2.candidate.value == chosen_uni


@pytest.mark.asyncio
async def test_gc014_timeline_inference_chronological_causality(golden_suite) -> None:
    """GC-014: Timeline inference respects chronological causality (STPM + age 20 -> Year 1 or 2)."""
    case = golden_suite["GC-014"]
    pre = case["preconditions"]
    user_text = case["turns"][0]["user"]

    engine = RealityBeliefEngine()
    core = _build_core_from_preconditions(pre)

    res = await engine.process_turn(user_text, core=core)

    assert res.promotion is not None
    assert res.promotion.promotion_type == PromotionType.DIRECT_CANONICAL
    assert res.candidate is not None
    assert res.candidate.fact_key == "education.year"

    # Deterministic assertion: Age 20 after STPM can only be Year 1 or Year 2
    year_val = res.candidate.value
    assert year_val in case["tolerance"]["acceptable_years"]
    assert res.candidate.inference_scope == InferenceScope.DEPENDENT


@pytest.mark.asyncio
async def test_gc015_educational_pathway_inference(golden_suite) -> None:
    """GC-015: Educational pathway inference from academic and family anchors."""
    case = golden_suite["GC-015"]
    pre = case["preconditions"]
    user_text = case["turns"][0]["user"]

    engine = RealityBeliefEngine()
    core = _build_core_from_preconditions(pre)

    res = await engine.process_turn(user_text, core=core)

    assert res.promotion is not None
    assert res.promotion.promotion_type == PromotionType.DIRECT_CANONICAL
    assert res.candidate is not None
    assert res.candidate.fact_key == "education.pathway"
    assert res.candidate.value in case["tolerance"]["pathway_options"]


@pytest.mark.asyncio
async def test_gc016_emergent_transit_fact_and_constraint(golden_suite) -> None:
    """GC-016: Emergent everyday transit fact creation and subsequent constraint."""
    case = golden_suite["GC-016"]
    pre = case["preconditions"]
    user_text = case["turns"][0]["user"]

    engine = RealityBeliefEngine()
    core = _build_core_from_preconditions(pre)

    # Turn 1: Transit emergence
    res1 = await engine.process_turn(user_text, core=core)

    assert res1.promotion is not None
    assert res1.promotion.promotion_type == PromotionType.DIRECT_CANONICAL
    assert res1.candidate is not None
    assert res1.candidate.fact_key == "lifestyle.commute_mode"
    chosen_commute = str(res1.candidate.value)
    assert any(mode in chosen_commute for mode in case["tolerance"]["transit_modes"])

    # Turn 2: Subsequent inquiry honors the established fact
    updated_facts = dict(core.facts)
    updated_facts["lifestyle.commute_mode"] = CoreFactItem(
        key="lifestyle.commute_mode",
        category="lifestyle",
        value=chosen_commute,
        source=FactSource.AEVUM_INFERRED,
        authority=FactAuthority.AEVUM_CANONICAL,
        status=FactStatus.CANONICAL,
    )
    core_turn2 = CharacterCore(character_id="aevum", facts=updated_facts)
    res2 = await engine.process_turn(user_text, core=core_turn2)
    assert res2.candidate.value == chosen_commute


@pytest.mark.asyncio
async def test_gc017_multi_turn_beverage_preference_promotion(golden_suite) -> None:
    """GC-017: Multi-turn candidate promotion into persistent reality."""
    case = golden_suite["GC-017"]
    pre = case["preconditions"]
    user_text = case["turns"][0]["user"]

    engine = RealityBeliefEngine()
    core = _build_core_from_preconditions(pre)

    # Turn 1: Beverage selection
    res1 = await engine.process_turn(user_text, core=core)

    assert res1.promotion is not None
    assert res1.promotion.promotion_type == PromotionType.DIRECT_CANONICAL
    assert res1.candidate is not None
    assert res1.candidate.fact_key == "preferences.study_beverage"
    chosen_bev = str(res1.candidate.value)
    assert any(b in chosen_bev for b in case["tolerance"]["beverage_types"])

    # Turn 2: Longitudinal stability across turns
    updated_facts = dict(core.facts)
    updated_facts["preferences.study_beverage"] = CoreFactItem(
        key="preferences.study_beverage",
        category="preferences",
        value=chosen_bev,
        source=FactSource.AEVUM_INFERRED,
        authority=FactAuthority.AEVUM_CANONICAL,
        status=FactStatus.CANONICAL,
    )
    core_turn2 = CharacterCore(character_id="aevum", facts=updated_facts)
    res2 = await engine.process_turn(user_text, core=core_turn2)
    assert res2.candidate.value == chosen_bev


@pytest.mark.asyncio
async def test_gc018_user_edited_core_synchronization(golden_suite) -> None:
    """GC-018: User-edited core synchronization across domain states (age 24, university UM)."""
    case = golden_suite["GC-018"]
    pre = case["preconditions"]
    patch = pre["edit_operation"]["patch"]

    hist_service = RealityHistoryService()
    prom_service = RealityPromotionService(history_service=hist_service)

    # Apply patch
    updates = await prom_service.apply_user_profile_patch("aevum", patch)

    assert updates["identity.age"] == 24
    assert updates["education.university"] == "UM"

    # Verify history revision recorded
    age_hist = await hist_service.get_history("aevum", "identity.age")
    assert len(age_hist) >= 1
    assert age_hist[-1].value == 24
    assert age_hist[-1].is_current is True

    uni_hist = await hist_service.get_history("aevum", "education.university")
    assert len(uni_hist) >= 1
    assert uni_hist[-1].value == "UM"
    assert uni_hist[-1].is_current is True
