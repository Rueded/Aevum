"""Unit tests for Reality Promotion Engine (Phase 7B.3.5).

Verifies dynamic promotion scoring, policy gating (LOW/MED/HIGH/VERY_HIGH),
anti-snowballing boundaries, and user profile patch application.
"""

import pytest
from app.reality.candidate_models import CandidateFact, InferenceScope, RealityImpact
from app.reality.belief_models import BeliefClaim, EpistemicStatus, FactSubject
from app.reality.contradiction_models import (
    ContradictionResolution,
    ContradictionType,
    RepairStrategy,
)
from app.reality.models import FactAuthority, FactStatus
from app.reality.promotion_models import PromotionType
from app.reality.promotion_service import RealityPromotionService
from app.reality.validators import ValidationResult


def test_low_impact_grounded_fact_direct_promotion() -> None:
    service = RealityPromotionService()
    cand = CandidateFact(
        id="c-bev",
        subject=FactSubject.AEVUM,
        fact_key="preferences.study_beverage",
        value="chamomile tea",
        impact=RealityImpact.LOW,
        inference_scope=InferenceScope.DIRECT,
    )
    belief = BeliefClaim(
        belief_id="b-bev",
        subject=FactSubject.AEVUM,
        fact_key="preferences.study_beverage",
        proposed_value="chamomile tea",
        epistemic_status=EpistemicStatus.PLAUSIBLE,
        confidence=0.95,
    )
    validation = ValidationResult(is_valid=True, reasons=["consistency check passed"])

    decision = service.evaluate_promotion(cand, belief, validation)
    assert decision.promotion_type == PromotionType.DIRECT_CANONICAL
    assert decision.authority == FactAuthority.AEVUM_CANONICAL
    assert decision.status == FactStatus.CANONICAL
    assert decision.promotion_score >= 0.9


def test_high_impact_fact_manual_gated() -> None:
    service = RealityPromotionService()
    cand = CandidateFact(
        id="c-trauma",
        subject=FactSubject.AEVUM,
        fact_key="biography.major_event",
        value="near fatal car crash in childhood",
        impact=RealityImpact.HIGH,
        inference_scope=InferenceScope.DIRECT,
    )
    decision = service.evaluate_promotion(cand)
    assert decision.promotion_type == PromotionType.MANUAL_USER_GATED
    assert "High impact" in decision.rationale


def test_speculative_fact_rejected_anti_snowballing() -> None:
    service = RealityPromotionService()
    cand = CandidateFact(
        id="c-snowball",
        subject=FactSubject.AEVUM,
        fact_key="possessions.guitar_model",
        value="1962 Vintage Fender Stratocaster gifted by grandfather",
        impact=RealityImpact.LOW,
        inference_scope=InferenceScope.SPECULATIVE,
    )
    decision = service.evaluate_promotion(cand)
    assert decision.promotion_type == PromotionType.REJECT
    assert "Anti-Snowballing" in decision.rationale


def test_contradiction_blocks_promotion() -> None:
    service = RealityPromotionService()
    cand = CandidateFact(
        id="c-haze",
        subject=FactSubject.WORLD,
        fact_key="life.schedule.haze_closure",
        value="1_month",
        impact=RealityImpact.HIGH,
    )
    contradiction = ContradictionResolution(
        contradiction_type=ContradictionType.ANOMALOUS_HIGH_IMPACT,
        repair_strategy=RepairStrategy.DEMAND_VERIFICATION,
        canonical_mutated=False,
        rationale="Haze closure unverified",
    )
    decision = service.evaluate_promotion(cand, contradiction=contradiction)
    assert decision.promotion_type == PromotionType.MANUAL_USER_GATED
    assert decision.promotion_score == 0.0


@pytest.mark.asyncio
async def test_apply_user_profile_patch_synchronization() -> None:
    service = RealityPromotionService()
    patch = {"age": 24, "education.university": "UM"}
    updates = await service.apply_user_profile_patch("aevum", patch)

    assert updates["identity.age"] == 24
    assert updates["education.university"] == "UM"

    # Check temporal history is recorded
    hist = await service._history_service.get_history("aevum", "identity.age")
    assert len(hist) == 1
    assert hist[0].value == 24
