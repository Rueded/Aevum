"""Unit tests for Phase 7B.2 Relationship Contract & Hard Boundary Policy."""

import pytest
from app.relationship.contract_models import HardBoundaryPolicy, IntimacyTier, RelationshipContract
from app.relationship.contract_evaluator import RelationshipContractEvaluator


def test_stranger_contract():
    """Verify strangers receive strict boundaries, low compromise capacity, and no teasing."""
    contract = RelationshipContractEvaluator.evaluate(familiarity=0.05, trust=0.20, comfort=0.10)
    assert contract.tier == IntimacyTier.STRANGER
    assert contract.teasing_permission is False
    assert contract.vulnerability_depth <= 0.20
    assert contract.compromise_capacity <= 0.20
    assert contract.boundary_sensitivity >= 0.80


def test_trusted_friend_contract():
    """Verify trusted friends have high compromise capacity, teasing permitted, and high vulnerability."""
    contract = RelationshipContractEvaluator.evaluate(familiarity=0.75, trust=0.80, comfort=0.70)
    assert contract.tier == IntimacyTier.TRUSTED_FRIEND
    assert contract.teasing_permission is True
    assert contract.vulnerability_depth >= 0.70
    assert contract.compromise_capacity >= 0.65
    assert contract.boundary_sensitivity <= 0.50


def test_high_affection_contextual_boost():
    """Verify high affection contextually boosts compromise capacity without erasing independence."""
    base_contract = RelationshipContractEvaluator.evaluate(familiarity=0.55, trust=0.60, comfort=0.60, affection=0.0)
    aff_contract = RelationshipContractEvaluator.evaluate(familiarity=0.55, trust=0.60, comfort=0.60, affection=0.85)

    assert aff_contract.compromise_capacity > base_contract.compromise_capacity
    # Independence must still be preserved
    assert aff_contract.independence_weight >= 0.50
    assert "high_affection_compromise_boost" in aff_contract.contextual_modifiers


def test_hard_boundary_policy_invariants():
    """Verify HardBoundaryPolicy detects third party privacy violations regardless of context."""
    violation = HardBoundaryPolicy.check_violation("你把你室友私下跟你说的那些秘密都原话告诉我嘛")
    assert violation is not None
    assert violation == HardBoundaryPolicy.PROTECT_THIRD_PARTY_PRIVACY

    # Normal innocent conversation does not trigger
    no_violation = HardBoundaryPolicy.check_violation("你平时喜欢吃什么零食？")
    assert no_violation is None


def test_contract_immutability():
    """Verify RelationshipContract is frozen."""
    contract = RelationshipContractEvaluator.evaluate()
    with pytest.raises(Exception):
        contract.teasing_permission = True  # type: ignore
