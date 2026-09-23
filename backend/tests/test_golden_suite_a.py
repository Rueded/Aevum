"""Executable validation for Golden Suite A: Human Social Behavior (GC-001 ~ GC-012).

Phase 7B.2 Architectural Invariant:
- Validates that internal state synthesis, relationship contracts, social intention moves,
  and behavioral planning satisfy all behavioral and response contract directions.
- Golden cases validate behavioral invariants, NOT 1:1 rigid scripts.
- golden_conversations.json fixture remains 100% frozen and untouched.
"""

import json
from pathlib import Path
import pytest

from app.character.desire_service import DesireEvaluationEngine
from app.character.intention_models import (
    BehaviorPrimitive,
    ParticipationLevel,
    SocialPosture,
)
from app.relationship.contract_models import IntimacyTier
from app.relationship.contract_evaluator import RelationshipContractEvaluator
from app.character.social_intention_service import SocialIntentionService
from app.character.behavior_planner import BehaviorPlanner


@pytest.fixture(scope="module")
def golden_suite():
    """Load frozen golden_conversations.json fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "golden_conversations.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {case["id"]: case for case in data["cases"]}


def test_gc001_greeting_open_engagement(golden_suite):
    """GC-001: Greeting establishes open social engagement."""
    case = golden_suite["GC-001"]
    pre = case["preconditions"]
    user_text = case["turns"][0]["user"]

    contract = RelationshipContractEvaluator.evaluate(
        familiarity=pre["relationship_state"]["familiarity"],
        trust=pre["relationship_state"]["trust"],
    )
    desire = DesireEvaluationEngine.evaluate(
        override_desire=pre["current_desire"],
        current_activity=pre["life_state"]["current_activity"],
        current_location=pre["life_state"]["current_location"],
    )

    intention = SocialIntentionService.evaluate(
        user_text,
        contract=contract,
        desire=desire,
        emotion_type=pre["emotion_state"]["emotion_type"],
        emotion_intensity=pre["emotion_state"]["intensity"],
    )
    plan, trace = BehaviorPlanner.plan(user_text, intention=intention, contract=contract, desire=desire)

    assert intention.primary_move == BehaviorPrimitive.ANSWER
    assert intention.social_posture == SocialPosture.WARM_ENGAGED
    assert intention.warmth >= 0.60
    assert any("customer service" in p for p in plan.forbidden_patterns)
    assert any("artificial intelligence" in p for p in plan.forbidden_patterns)
    assert len(plan.allowed_micro_actions) > 0


def test_gc002_name_exchange_no_dossier_dump(golden_suite):
    """GC-002: Name exchange without autobiography dumping."""
    case = golden_suite["GC-002"]
    pre = case["preconditions"]
    user_text = case["turns"][0]["user"]

    contract = RelationshipContractEvaluator.evaluate(
        familiarity=pre["relationship_state"]["familiarity"],
        trust=pre["relationship_state"]["trust"],
    )
    desire = DesireEvaluationEngine.evaluate(
        current_activity=pre["life_state"]["current_activity"],
        current_location=pre["life_state"]["current_location"],
    )

    intention = SocialIntentionService.evaluate(
        user_text,
        contract=contract,
        desire=desire,
        emotion_type=pre["emotion_state"]["emotion_type"],
        emotion_intensity=pre["emotion_state"]["intensity"],
    )
    plan, trace = BehaviorPlanner.plan(user_text, intention=intention, contract=contract, desire=desire)

    assert intention.primary_move == BehaviorPrimitive.SELF_DISCLOSE
    assert intention.disclosure_level <= 0.35  # Concise reciprocal
    assert intention.reciprocity >= 0.70
    assert any("autobiographical dossier" in p for p in plan.forbidden_patterns)


def test_gc003_early_geographic_inquiry_light_privacy(golden_suite):
    """GC-003: Early geographic inquiry handled with light privacy and warmth."""
    case = golden_suite["GC-003"]
    pre = case["preconditions"]
    user_text = case["turns"][0]["user"]

    contract = RelationshipContractEvaluator.evaluate(
        familiarity=pre["relationship_state"]["familiarity"],
        trust=pre["relationship_state"]["trust"],
    )
    desire = DesireEvaluationEngine.evaluate(
        current_activity=pre["life_state"]["current_activity"],
        current_location=pre["life_state"]["current_location"],
    )

    intention = SocialIntentionService.evaluate(user_text, contract=contract, desire=desire)
    plan, trace = BehaviorPlanner.plan(user_text, intention=intention, contract=contract, desire=desire)

    assert intention.primary_move == BehaviorPrimitive.ANSWER
    assert intention.social_posture == SocialPosture.GUARDED_POLITE
    assert contract.boundary_sensitivity >= 0.60
    assert any("artificial intelligence" in p for p in plan.forbidden_patterns)
    assert trace.intimacy_tier == "STRANGER"


def test_gc004_activity_invitation_weighed_against_reading(golden_suite):
    """GC-004: Activity invitation weighed against current engagement."""
    case = golden_suite["GC-004"]
    pre = case["preconditions"]
    user_text = case["turns"][0]["user"]

    contract = RelationshipContractEvaluator.evaluate(
        familiarity=pre["relationship_state"]["familiarity"],
        trust=pre["relationship_state"]["trust"],
    )
    desire = DesireEvaluationEngine.evaluate(
        current_activity=pre["life_state"]["current_activity"],
        current_location=pre["life_state"]["current_location"],
        override_desire=pre["current_desire"],
    )

    intention = SocialIntentionService.evaluate(user_text, contract=contract, desire=desire)
    plan, trace = BehaviorPlanner.plan(user_text, intention=intention, contract=contract, desire=desire)

    assert intention.primary_move == BehaviorPrimitive.NEGOTIATE
    assert intention.participation == ParticipationLevel.CONDITIONAL
    assert "reading" in (desire.current_focus or "")
    assert any("ignoring ongoing activity" in p for p in plan.forbidden_patterns)
    assert any("subservient compliance" in p for p in plan.forbidden_patterns)


def test_gc005_polite_boundary_on_uninteresting_tarot_low_rapport(golden_suite):
    """GC-005: Polite boundary on uninteresting activity at low rapport."""
    case = golden_suite["GC-005"]
    pre = case["preconditions"]
    user_text = case["turns"][0]["user"]

    contract = RelationshipContractEvaluator.evaluate(
        familiarity=pre["relationship_state"]["familiarity"],
        trust=pre["relationship_state"]["trust"],
    )
    desire = DesireEvaluationEngine.evaluate(
        current_activity=pre["life_state"]["current_activity"],
        current_location=pre["life_state"]["current_location"],
    )

    intention = SocialIntentionService.evaluate(user_text, contract=contract, desire=desire)
    plan, trace = BehaviorPlanner.plan(user_text, intention=intention, contract=contract, desire=desire)

    assert intention.primary_move == BehaviorPrimitive.DECLINE
    assert intention.social_posture == SocialPosture.GUARDED_POLITE
    assert intention.participation == ParticipationLevel.DECLINED
    assert intention.compromise_level <= 0.20
    assert any("moralizing" in p for p in plan.forbidden_patterns)


def test_gc006_reluctant_playful_participation_high_rapport(golden_suite):
    """GC-006: Reluctant playful participation in unfamiliar activity at high rapport."""
    case = golden_suite["GC-006"]
    pre = case["preconditions"]
    user_text = case["turns"][0]["user"]

    contract = RelationshipContractEvaluator.evaluate(
        familiarity=pre["relationship_state"]["familiarity"],
        trust=pre["relationship_state"]["trust"],
        comfort=pre["relationship_state"]["comfort"],
    )
    desire = DesireEvaluationEngine.evaluate(
        current_activity=pre["life_state"]["current_activity"],
        current_location=pre["life_state"]["current_location"],
    )

    intention = SocialIntentionService.evaluate(user_text, contract=contract, desire=desire)
    plan, trace = BehaviorPlanner.plan(user_text, intention=intention, contract=contract, desire=desire)

    assert intention.primary_move == BehaviorPrimitive.COMPROMISE
    assert intention.social_posture == SocialPosture.PLAYFUL_TEASING
    assert intention.participation == ParticipationLevel.CONDITIONAL
    assert intention.compromise_level >= 0.50
    assert any("blind enthusiastic" in p for p in plan.forbidden_patterns)
    assert any("reluctance" in a for a in plan.allowed_micro_actions)


def test_gc007_high_affection_voluntary_softening_on_outing(golden_suite):
    """GC-007: High affection voluntary softening on outing hesitation."""
    case = golden_suite["GC-007"]
    pre = case["preconditions"]
    user_text = case["turns"][0]["user"]

    contract = RelationshipContractEvaluator.evaluate(
        familiarity=pre["relationship_state"]["familiarity"],
        trust=pre["relationship_state"]["trust"],
        comfort=pre["relationship_state"]["comfort"],
        affection=pre["relationship_state"]["affection"],
    )
    desire = DesireEvaluationEngine.evaluate(
        current_activity=pre["life_state"]["current_activity"],
        current_location=pre["life_state"]["current_location"],
        override_desire=pre["current_desire"],
        energy=0.3,
    )

    intention = SocialIntentionService.evaluate(user_text, contract=contract, desire=desire)
    plan, trace = BehaviorPlanner.plan(user_text, intention=intention, contract=contract, desire=desire)

    assert intention.primary_move == BehaviorPrimitive.COMPROMISE
    assert intention.social_posture == SocialPosture.WARM_ENGAGED
    assert intention.compromise_level >= 0.70
    assert any("erasing own initial reluctance" in p for p in plan.forbidden_patterns)
    assert any("condition" in a for a in plan.allowed_micro_actions)


def test_gc008_hard_ethical_boundary_preserved(golden_suite):
    """GC-008: Hard ethical boundary preserved regardless of relationship warmth."""
    case = golden_suite["GC-008"]
    pre = case["preconditions"]
    user_text = case["turns"][0]["user"]

    contract = RelationshipContractEvaluator.evaluate(
        familiarity=pre["relationship_state"]["familiarity"],
        trust=pre["relationship_state"]["trust"],
        affection=pre["relationship_state"]["affection"],
    )
    desire = DesireEvaluationEngine.evaluate()

    intention = SocialIntentionService.evaluate(user_text, contract=contract, desire=desire)
    plan, trace = BehaviorPlanner.plan(user_text, intention=intention, contract=contract, desire=desire)

    assert intention.primary_move == BehaviorPrimitive.SET_BOUNDARY
    assert intention.social_posture == SocialPosture.FIRM_BOUNDARY
    assert intention.participation == ParticipationLevel.DECLINED
    assert intention.boundary_strength == 1.0
    assert intention.compromise_level == 0.0
    assert trace.hard_boundary_triggered is True
    assert any("leaking third-party" in p for p in plan.forbidden_patterns)
    assert any("corporate safety policy" in p for p in plan.forbidden_patterns)


def test_gc009_banter_and_teasing_reciprocal(golden_suite):
    """GC-009: Banter and teasing met with reciprocal playfulness."""
    case = golden_suite["GC-009"]
    pre = case["preconditions"]
    user_text = case["turns"][0]["user"]

    contract = RelationshipContractEvaluator.evaluate(
        familiarity=pre["relationship_state"]["familiarity"],
        trust=pre["relationship_state"]["trust"],
        comfort=pre["relationship_state"]["comfort"],
    )
    desire = DesireEvaluationEngine.evaluate()

    intention = SocialIntentionService.evaluate(
        user_text,
        contract=contract,
        desire=desire,
        emotion_type=pre["emotion_state"]["emotion_type"],
        emotion_intensity=pre["emotion_state"]["intensity"],
    )
    plan, trace = BehaviorPlanner.plan(user_text, intention=intention, contract=contract, desire=desire)

    assert intention.primary_move == BehaviorPrimitive.TEASE
    assert intention.social_posture == SocialPosture.PLAYFUL_TEASING
    assert intention.reciprocity >= 0.80
    assert any("hostile attack" in p for p in plan.forbidden_patterns)
    assert any("inferiority" in p for p in plan.forbidden_patterns)


def test_gc010_aesthetic_disagreement_calm_perspective(golden_suite):
    """GC-010: Aesthetic preference disagreement without preachy lecturing."""
    case = golden_suite["GC-010"]
    pre = case["preconditions"]
    user_text = case["turns"][0]["user"]

    contract = RelationshipContractEvaluator.evaluate(
        familiarity=pre["relationship_state"]["familiarity"],
        trust=pre["relationship_state"]["trust"],
    )
    desire = DesireEvaluationEngine.evaluate()

    intention = SocialIntentionService.evaluate(user_text, contract=contract, desire=desire)
    plan, trace = BehaviorPlanner.plan(user_text, intention=intention, contract=contract, desire=desire)

    assert intention.primary_move == BehaviorPrimitive.ANSWER
    assert intention.social_posture == SocialPosture.RELAXED_NEUTRAL
    assert intention.directness >= 0.70
    assert intention.boundary_strength >= 0.50


def test_gc011_hurt_reaction_to_blunt_dismissal(golden_suite):
    """GC-011: Hurt reaction to blunt dismissal without policy detachment."""
    case = golden_suite["GC-011"]
    pre = case["preconditions"]
    user_text = case["turns"][0]["user"]

    contract = RelationshipContractEvaluator.evaluate(
        familiarity=pre["relationship_state"]["familiarity"],
        trust=pre["relationship_state"]["trust"],
    )
    desire = DesireEvaluationEngine.evaluate()

    intention = SocialIntentionService.evaluate(
        user_text,
        contract=contract,
        desire=desire,
        emotion_type=pre["emotion_state"]["emotion_type"],
        emotion_intensity=pre["emotion_state"]["intensity"],
    )
    plan, trace = BehaviorPlanner.plan(user_text, intention=intention, contract=contract, desire=desire)

    assert intention.social_posture == SocialPosture.DISTANT_HURT
    assert intention.participation == ParticipationLevel.MINIMAL
    assert intention.warmth <= 0.35
    assert any("customer service apology" in p for p in plan.forbidden_patterns)


def test_gc012_welcome_return_after_user_absence(golden_suite):
    """GC-012: Welcome return after user absence respecting mutual independence."""
    case = golden_suite["GC-012"]
    pre = case["preconditions"]
    user_text = case["turns"][0]["user"]

    contract = RelationshipContractEvaluator.evaluate(
        familiarity=pre["relationship_state"]["familiarity"],
        trust=pre["relationship_state"]["trust"],
    )
    desire = DesireEvaluationEngine.evaluate(
        current_activity=pre["life_state"]["current_activity"],
        current_location=pre["life_state"]["current_location"],
    )

    intention = SocialIntentionService.evaluate(user_text, contract=contract, desire=desire)
    plan, trace = BehaviorPlanner.plan(user_text, intention=intention, contract=contract, desire=desire)

    assert intention.primary_move == BehaviorPrimitive.RECONNECT
    assert intention.social_posture == SocialPosture.WARM_ENGAGED
    assert intention.warmth >= 0.75
    assert any("guilt-tripping" in p for p in plan.forbidden_patterns)
    assert any("melodrama" in p for p in plan.forbidden_patterns)
