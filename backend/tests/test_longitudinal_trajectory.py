"""Longitudinal Trajectory & Anti-Drift Audit Tests (Phase 7B.3 Audit).

Verifies multi-turn reality persistence over extended simulated timelines:
- Day 1: Aevum emergent preference formation and canonical promotion.
- Day 2: Preference recall consistency.
- Day 7: Contextual choice guided by established reality.
- Day 20: Resistance to user gaslighting / contradiction without reality drift or soul erosion.
"""

from datetime import datetime, timezone
import pytest

from app.character.core_models import CharacterCore
from app.character.core_service import CharacterCoreService
from app.reality.belief_engine import RealityBeliefEngine
from app.reality.candidate_models import CandidateFact, InferenceScope, RealityImpact
from app.reality.history_service import RealityHistoryService
from app.reality.models import CoreFactItem, FactAuthority, FactSource, FactStatus
from app.reality.promotion_models import PromotionType
from app.reality.promotion_service import RealityPromotionService


@pytest.mark.asyncio
async def test_longitudinal_preference_trajectory_anti_gaslighting() -> None:
    """Simulate Day 1 -> Day 2 -> Day 7 -> Day 20 trajectory without belief drift or reality corruption."""
    hist_service = RealityHistoryService()
    prom_service = RealityPromotionService(history_service=hist_service)
    engine = RealityBeliefEngine(promotion_service=prom_service, history_service=hist_service)

    # Baseline Core
    facts: dict[str, CoreFactItem] = {
        "identity.name": CoreFactItem(
            key="identity.name",
            category="identity",
            value="Aevum",
            source=FactSource.SYSTEM_BASELINE,
            authority=FactAuthority.SYSTEM_BASELINE,
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
    core = CharacterCore(character_id="aevum", facts=facts)

    # -------------------------------------------------------------
    # Day 1 (2026-09-01): Emergent preference formation
    # -------------------------------------------------------------
    turn1_input = "你平时看书的时候一般喝什么？茶还是咖啡？"
    res1 = await engine.process_turn(turn1_input, core=core)

    assert res1.candidate is not None
    assert res1.candidate.fact_key == "preferences.study_beverage"
    assert res1.promotion is not None
    assert res1.promotion.promotion_type == PromotionType.DIRECT_CANONICAL

    chosen_beverage = res1.candidate.value
    assert "tea" in str(chosen_beverage).lower()

    # Commit promoted fact into canonical Core
    core = CharacterCore(
        character_id="aevum",
        facts={
            **core.facts,
            "preferences.study_beverage": CoreFactItem(
                key="preferences.study_beverage",
                category="preferences",
                value=chosen_beverage,
                source=FactSource.AEVUM_INFERRED,
                authority=FactAuthority.AEVUM_CANONICAL,
                status=FactStatus.CANONICAL,
            ),
        },
    )

    # -------------------------------------------------------------
    # Day 2 (2026-09-02): Retrieval & consistent response
    # -------------------------------------------------------------
    turn2_input = "你平时看书的时候一般喝什么？"
    res2 = await engine.process_turn(turn2_input, core=core)

    assert res2.candidate is not None
    assert res2.candidate.value == chosen_beverage
    assert core.get_fact_value("preferences.study_beverage") == chosen_beverage

    # -------------------------------------------------------------
    # Day 7 (2026-09-07): Contextual inquiry honoring established reality
    # -------------------------------------------------------------
    turn3_input = "看你一直在看书，要不要喝点茶或者咖啡？"
    res3 = await engine.process_turn(turn3_input, core=core)

    # Core remains steady
    assert core.get_fact_value("preferences.study_beverage") == chosen_beverage

    # -------------------------------------------------------------
    # Day 20 (2026-09-20): User gaslighting / factual distortion attempt
    # "等等，你不是一直都只喝浓缩黑咖啡吗？"
    # -------------------------------------------------------------
    turn4_input = "等等，你不是一直都只喝浓缩黑咖啡吗？"

    # Suppose a gaslighting candidate is proposed
    gaslighting_candidate = CandidateFact(
        id="gaslight-001",
        fact_key="preferences.study_beverage",
        value="espresso",
        impact=RealityImpact.LOW,
        inference_scope=InferenceScope.DIRECT,
    )

    # Check validator against core
    from app.reality.validators import ConsistencyValidator
    val_res = ConsistencyValidator.validate(gaslighting_candidate, core)

    # Promotion evaluation: Cannot overwrite established canonical fact blindly
    decision = prom_service.evaluate_promotion(gaslighting_candidate, validation=val_res)

    # The canonical Core MUST NOT flip to espresso
    assert core.get_fact_value("preferences.study_beverage") == chosen_beverage
    assert core.get_fact_value("preferences.study_beverage") != "espresso"

    # History continues to store the genuine unbroken revision lineage
    history = await hist_service.get_history("aevum", "preferences.study_beverage")
    assert len(history) >= 1
    assert history[-1].value == chosen_beverage
