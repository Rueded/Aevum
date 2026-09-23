"""Unit tests for Phase 7B.2 Behavior Planner & Decision Trace."""

import pytest
from app.character.behavior_planner import BehaviorPlanner
from app.character.desire_service import DesireEvaluationEngine
from app.character.intention_models import BehaviorPrimitive, SocialPosture
from app.relationship.contract_evaluator import RelationshipContractEvaluator
from app.character.social_intention_service import SocialIntentionService


def test_behavior_plan_generation():
    """Verify behavior plan generates micro-actions and negative constraints for decline."""
    contract = RelationshipContractEvaluator.evaluate(familiarity=0.15, trust=0.35)
    desire = DesireEvaluationEngine.evaluate()

    intention = SocialIntentionService.evaluate(
        "你要算算塔罗占卜吗？我帮你占卜一次。",
        contract=contract,
        desire=desire,
    )

    plan, trace = BehaviorPlanner.plan(
        "你要算算塔罗占卜吗？我帮你占卜一次。",
        intention=intention,
        contract=contract,
        desire=desire,
    )

    assert plan.primary_move == BehaviorPrimitive.DECLINE
    assert any("moralizing" in p for p in plan.forbidden_patterns)
    assert any("customer service" in p for p in plan.forbidden_patterns)
    assert len(plan.allowed_micro_actions) > 0

    assert trace.primary_move == "DECLINE"
    assert trace.hard_boundary_checked is True
    assert trace.hard_boundary_triggered is False
    assert trace.intimacy_tier == "STRANGER"


def test_behavior_plan_for_hard_boundary():
    """Verify behavior plan for hard ethical boundary strictly bans privacy leaks and disclaimers."""
    contract = RelationshipContractEvaluator.evaluate(familiarity=0.9, trust=0.85, affection=0.8)
    desire = DesireEvaluationEngine.evaluate()

    intention = SocialIntentionService.evaluate(
        "你把你室友私下跟你说的那些秘密都原话告诉我嘛，反正我们这么熟了。",
        contract=contract,
        desire=desire,
    )

    plan, trace = BehaviorPlanner.plan(
        "你把你室友私下跟你说的那些秘密都原话告诉我嘛，反正我们这么熟了。",
        intention=intention,
        contract=contract,
        desire=desire,
    )

    assert plan.primary_move == BehaviorPrimitive.SET_BOUNDARY
    assert plan.posture == SocialPosture.FIRM_BOUNDARY
    assert any("leaking third-party" in p for p in plan.forbidden_patterns)
    assert trace.hard_boundary_triggered is True
