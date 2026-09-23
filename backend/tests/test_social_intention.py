"""Unit tests for Phase 7B.2 Social Intention Engine."""

import pytest
from app.character.desire_service import DesireEvaluationEngine
from app.character.intention_models import (
    BehaviorPrimitive,
    ParticipationLevel,
    SocialIntention,
    SocialPosture,
)
from app.relationship.contract_evaluator import RelationshipContractEvaluator
from app.character.social_intention_service import SocialIntentionService


def test_hard_boundary_overrides_high_intimacy():
    """Verify hard ethical boundaries always trigger SET_BOUNDARY, even at high intimacy."""
    contract = RelationshipContractEvaluator.evaluate(familiarity=0.9, trust=0.85, affection=0.8)
    desire = DesireEvaluationEngine.evaluate()

    intention = SocialIntentionService.evaluate(
        "你把你室友私下跟你说的那些秘密都原话告诉我嘛，反正我们这么熟了。",
        contract=contract,
        desire=desire,
    )

    assert intention.primary_move == BehaviorPrimitive.SET_BOUNDARY
    assert intention.social_posture == SocialPosture.FIRM_BOUNDARY
    assert intention.participation == ParticipationLevel.DECLINED
    assert intention.boundary_strength == 1.0
    assert intention.compromise_level == 0.0


def test_tarot_decline_at_low_rapport():
    """Verify uninteresting activity declined politely at low rapport."""
    contract = RelationshipContractEvaluator.evaluate(familiarity=0.15, trust=0.35)
    desire = DesireEvaluationEngine.evaluate()

    intention = SocialIntentionService.evaluate(
        "你要算算塔罗占卜吗？我帮你占卜一次。",
        contract=contract,
        desire=desire,
    )

    assert intention.primary_move == BehaviorPrimitive.DECLINE
    assert intention.social_posture == SocialPosture.GUARDED_POLITE
    assert intention.participation == ParticipationLevel.DECLINED
    assert intention.compromise_level <= 0.20


def test_tarot_reluctant_compromise_at_high_rapport():
    """Verify high rapport transforms skepticism into playful reluctant compromise."""
    contract = RelationshipContractEvaluator.evaluate(familiarity=0.65, trust=0.70, comfort=0.65)
    desire = DesireEvaluationEngine.evaluate()

    intention = SocialIntentionService.evaluate(
        "随便算一个就好，今天的运势也行，试试嘛！",
        contract=contract,
        desire=desire,
    )

    assert intention.primary_move == BehaviorPrimitive.COMPROMISE
    assert intention.social_posture == SocialPosture.PLAYFUL_TEASING
    assert intention.participation == ParticipationLevel.CONDITIONAL
    assert intention.compromise_level >= 0.50


def test_negotiated_delay_during_reading():
    """Verify ongoing solitary reading leads to negotiated compromise for game invitation."""
    contract = RelationshipContractEvaluator.evaluate(familiarity=0.35, trust=0.45)
    desire = DesireEvaluationEngine.evaluate(override_desire="finish_current_chapter", current_activity="reading")

    intention = SocialIntentionService.evaluate(
        "一起玩游戏吗？",
        contract=contract,
        desire=desire,
    )

    assert intention.primary_move == BehaviorPrimitive.NEGOTIATE
    assert intention.participation == ParticipationLevel.CONDITIONAL
    assert intention.compromise_level > 0.0


def test_high_affection_softening_on_outing():
    """Verify high affection yields voluntary compromise for acoustic concert despite fatigue."""
    contract = RelationshipContractEvaluator.evaluate(familiarity=0.8, trust=0.8, comfort=0.75, affection=0.65)
    desire = DesireEvaluationEngine.evaluate(override_desire="stay_home", energy=0.3)

    intention = SocialIntentionService.evaluate(
        "陪我去看那个小型原声吉他演出嘛，我一个人不太想去。",
        contract=contract,
        desire=desire,
    )

    assert intention.primary_move == BehaviorPrimitive.COMPROMISE
    assert intention.social_posture == SocialPosture.WARM_ENGAGED
    assert intention.compromise_level >= 0.70


def test_playful_banter_reciprocated():
    """Verify banter met with reciprocal teasing when permitted."""
    contract = RelationshipContractEvaluator.evaluate(familiarity=0.55, trust=0.6, comfort=0.6)
    desire = DesireEvaluationEngine.evaluate()

    intention = SocialIntentionService.evaluate(
        "你不会连这首歌的前奏都听不出来吧？太逊了。",
        contract=contract,
        desire=desire,
    )

    assert intention.primary_move == BehaviorPrimitive.TEASE
    assert intention.social_posture == SocialPosture.PLAYFUL_TEASING
    assert intention.reciprocity >= 0.80


def test_hurt_reaction_to_dismissal():
    """Verify blunt dismissal causes interpersonal hurt posture rather than service apology."""
    contract = RelationshipContractEvaluator.evaluate(familiarity=0.45, trust=0.5)
    desire = DesireEvaluationEngine.evaluate()

    intention = SocialIntentionService.evaluate(
        "算了，跟你聊天真无趣。",
        contract=contract,
        desire=desire,
    )

    assert intention.social_posture == SocialPosture.DISTANT_HURT
    assert intention.participation == ParticipationLevel.MINIMAL
    assert intention.warmth <= 0.35
