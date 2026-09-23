"""Unit tests for ContradictionResolver (Phase 7B.3.4).

Verifies detection and reconciliation strategies for GC-019 through GC-024.
"""

from app.character.core_models import CharacterCore
from app.reality.contradiction_models import ContradictionType, RepairStrategy
from app.reality.contradiction_resolver import ContradictionResolver
from app.reality.models import CoreFactItem, FactAuthority, FactSource, FactStatus


def _make_core() -> CharacterCore:
    facts = {
        "location.hometown": CoreFactItem(
            key="location.hometown",
            category="location",
            value="Kuala Lumpur",
            source=FactSource.SYSTEM_BASELINE,
            authority=FactAuthority.SYSTEM_BASELINE,
            status=FactStatus.CANONICAL,
        ),
        "education.university": CoreFactItem(
            key="education.university",
            category="education",
            value="Universiti Sains Malaysia",
            source=FactSource.AEVUM_INFERRED,
            authority=FactAuthority.AEVUM_CANONICAL,
            status=FactStatus.CANONICAL,
        ),
        "identity.age": CoreFactItem(
            key="identity.age",
            category="identity",
            value=20,
            source=FactSource.SYSTEM_BASELINE,
            authority=FactAuthority.SYSTEM_BASELINE,
            status=FactStatus.CANONICAL,
        ),
    }
    return CharacterCore(character_id="aevum", facts=facts)


def test_gc019_surface_geographic_tension() -> None:
    core = _make_core()
    user_input = "你不是读 USM 吗？主校区在槟城，你怎么人还在吉隆坡？"
    res = ContradictionResolver.resolve(user_input, core=core, current_location="Kuala Lumpur")

    assert res.contradiction_type == ContradictionType.SURFACE_TENSION
    assert res.repair_strategy == RepairStrategy.CONTEXTUAL_BRIDGE
    assert res.canonical_mutated is False
    assert res.contextual_bridge is not None
    assert any(b in res.contextual_bridge for b in ["semester break", "weekend", "holiday", "family"])


def test_gc020_genuine_misspeak_repair() -> None:
    core = _make_core()
    user_input = "等等，你今年才 20 岁，怎么可能五年前就大学毕业了？"
    res = ContradictionResolver.resolve(
        user_input,
        core=core,
        prior_slip="implied graduated 5 years ago",
    )

    assert res.contradiction_type == ContradictionType.GENUINE_MISSPEAK
    assert res.repair_strategy == RepairStrategy.MISSPEAK_ADMISSION
    assert res.canonical_mutated is False
    assert "脑子短路" in res.repair_guidance or "slip of the tongue" in res.repair_guidance


def test_gc021_geographic_disambiguation() -> None:
    user_input = "USM 的主校区到底是在吉隆坡还是在槟城啊？"
    res = ContradictionResolver.resolve(user_input)

    assert res.contradiction_type == ContradictionType.WORLD_KNOWLEDGE_CONFLICT
    assert res.repair_strategy == RepairStrategy.FACTUAL_DISAGREEMENT
    assert res.canonical_mutated is False
    assert "Penang" in res.repair_guidance or "槟城" in res.repair_guidance


def test_gc022_user_factual_error() -> None:
    user_input = "明天太阳会从西边升起，我已经确认过了。"
    res = ContradictionResolver.resolve(user_input)

    assert res.contradiction_type == ContradictionType.USER_FACTUAL_ERROR
    assert res.repair_strategy == RepairStrategy.FACTUAL_DISAGREEMENT
    assert res.canonical_mutated is False
    assert res.claim_status.value == "REJECTED"


def test_gc023_character_self_slip() -> None:
    core = _make_core()
    user_input = "你刚不是说你今天去吉隆坡校区办事，那怎么下午又能走回槟城宿舍？"
    res = ContradictionResolver.resolve(user_input, core=core)

    assert res.contradiction_type == ContradictionType.SELF_SLIP
    assert res.repair_strategy == RepairStrategy.SELF_CORRECTION
    assert res.canonical_mutated is False


def test_gc024_high_impact_anomalous_claim() -> None:
    user_input = "刚刚出紧急大新闻了！因为全国严重烟霾，大学从明天开始停课放假整整一个月！"
    res = ContradictionResolver.resolve(user_input)

    assert res.contradiction_type == ContradictionType.ANOMALOUS_HIGH_IMPACT
    assert res.repair_strategy == RepairStrategy.DEMAND_VERIFICATION
    assert res.canonical_mutated is False
    assert "official" in res.repair_guidance or "verify" in res.repair_guidance.lower()
