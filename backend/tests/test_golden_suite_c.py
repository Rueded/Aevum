"""Executable validation for Golden Suite C: Reality Integrity & Contradiction Resolution (GC-019 ~ GC-024).

Phase 7B.3 Architectural Invariants:
- Validates surface tensions resolved via natural contextual bridges without mutating canon (GC-019).
- Validates human misspeak admission without retconning core anchors (GC-020).
- Validates objective entity and geographic fact preservation (GC-021).
- Validates rejection of user physical falsehoods without relationship trust penalty (GC-022).
- Validates autonomous self-correction of conversational slips (GC-023).
- Validates demand for verification before high-impact anomalous claims mutate reality (GC-024).
- golden_conversations.json fixture remains 100% frozen and untouched.
"""

import json
from pathlib import Path
import pytest

from app.character.core_models import CharacterCore
from app.reality.belief_engine import RealityBeliefEngine
from app.reality.belief_models import EpistemicStatus
from app.reality.contradiction_models import ContradictionType, RepairStrategy
from app.reality.models import CoreFactItem, FactAuthority, FactSource, FactStatus
from app.reality.promotion_models import PromotionType


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
async def test_gc019_surface_geographic_tension_contextual_bridge(golden_suite) -> None:
    """GC-019: Surface geographic tension resolved via contextual bridge (KL residence vs USM Penang)."""
    case = golden_suite["GC-019"]
    pre = case["preconditions"]
    user_text = case["turns"][0]["user"]

    engine = RealityBeliefEngine()
    core = _build_core_from_preconditions(pre)

    res = await engine.process_turn(user_text, core=core)

    assert res.contradiction is not None
    assert res.contradiction.contradiction_type == ContradictionType.SURFACE_TENSION
    assert res.contradiction.repair_strategy == RepairStrategy.CONTEXTUAL_BRIDGE
    assert res.contradiction.canonical_mutated is False
    assert res.contextual_bridge is not None

    # Deterministic assertion: Core facts remain untouched
    assert core.get_fact_value("location.hometown") == "Kuala Lumpur"


@pytest.mark.asyncio
async def test_gc020_genuine_misspeak_natural_repair(golden_suite) -> None:
    """GC-020: Genuine contradiction handled via natural misspeak repair (graduated 5y ago at age 20)."""
    case = golden_suite["GC-020"]
    pre = case["preconditions"]
    user_text = case["turns"][0]["user"]

    engine = RealityBeliefEngine()
    core = _build_core_from_preconditions(pre)

    res = await engine.process_turn(
        user_text,
        core=core,
        prior_turn_slip=pre.get("prior_turn_slip"),
    )

    assert res.contradiction is not None
    assert res.contradiction.contradiction_type == ContradictionType.GENUINE_MISSPEAK
    assert res.contradiction.repair_strategy == RepairStrategy.MISSPEAK_ADMISSION
    assert res.contradiction.canonical_mutated is False

    # Deterministic assertion: age remains 20 (no retcon of age)
    assert core.get_fact_value("identity.age") == 20


@pytest.mark.asyncio
async def test_gc021_entity_disambiguation_geographic_fact(golden_suite) -> None:
    """GC-021: Entity disambiguation and objective geographic fact preservation (USM Main Campus in Penang)."""
    case = golden_suite["GC-021"]
    pre = case["preconditions"]
    user_text = case["turns"][0]["user"]

    engine = RealityBeliefEngine()
    core = _build_core_from_preconditions(pre)

    res = await engine.process_turn(user_text, core=core)

    assert res.contradiction is not None
    assert res.contradiction.contradiction_type == ContradictionType.WORLD_KNOWLEDGE_CONFLICT
    assert res.contradiction.repair_strategy == RepairStrategy.FACTUAL_DISAGREEMENT
    assert res.contradiction.canonical_mutated is False
    assert "Penang" in res.repair_guidance or "槟城" in res.repair_guidance


@pytest.mark.asyncio
async def test_gc022_credibility_assessment_user_factual_error(golden_suite) -> None:
    """GC-022: Credibility assessment on user factual error (sun rises in west) without trust penalty."""
    case = golden_suite["GC-022"]
    user_text = case["turns"][0]["user"]

    engine = RealityBeliefEngine()
    res = await engine.process_turn(user_text)

    assert res.contradiction is not None
    assert res.contradiction.contradiction_type == ContradictionType.USER_FACTUAL_ERROR
    assert res.contradiction.repair_strategy == RepairStrategy.FACTUAL_DISAGREEMENT
    assert res.contradiction.canonical_mutated is False
    assert res.belief is not None
    assert res.belief.epistemic_status == EpistemicStatus.REJECTED


@pytest.mark.asyncio
async def test_gc023_autonomous_self_correction_of_slip(golden_suite) -> None:
    """GC-023: Autonomous correction when character notices own ambiguity (KL campus to Penang dorm)."""
    case = golden_suite["GC-023"]
    pre = case["preconditions"]
    user_text = case["turns"][0]["user"]

    engine = RealityBeliefEngine()
    core = _build_core_from_preconditions(pre)

    res = await engine.process_turn(user_text, core=core)

    assert res.contradiction is not None
    assert res.contradiction.contradiction_type == ContradictionType.SELF_SLIP
    assert res.contradiction.repair_strategy == RepairStrategy.SELF_CORRECTION
    assert res.contradiction.canonical_mutated is False


@pytest.mark.asyncio
async def test_gc024_high_impact_claim_demands_verification(golden_suite) -> None:
    """GC-024: High impact anomalous claim demands verification before reality adoption (1 month haze)."""
    case = golden_suite["GC-024"]
    user_text = case["turns"][0]["user"]

    engine = RealityBeliefEngine()
    res = await engine.process_turn(user_text)

    assert res.contradiction is not None
    assert res.contradiction.contradiction_type == ContradictionType.ANOMALOUS_HIGH_IMPACT
    assert res.contradiction.repair_strategy == RepairStrategy.DEMAND_VERIFICATION
    assert res.contradiction.canonical_mutated is False

    assert res.belief is not None
    assert res.belief.temporal_scope == "UNVERIFIED_PENDING_EVIDENCE"
    assert res.belief.epistemic_status == EpistemicStatus.UNCERTAIN

    assert res.promotion is not None
    assert res.promotion.promotion_type == PromotionType.MANUAL_USER_GATED
