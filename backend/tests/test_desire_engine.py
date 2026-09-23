"""Unit tests for Phase 7B.2 Desire & Need Engine."""

import pytest
from app.character.desire_models import CharacterDesireState, PrimaryDesire
from app.character.desire_service import DesireEvaluationEngine


def test_default_desire_state():
    """Verify default desire state evaluation with neutral baseline inputs."""
    desire = DesireEvaluationEngine.evaluate()
    assert isinstance(desire, CharacterDesireState)
    assert desire.primary_desire == PrimaryDesire.QUIET_CONTEMPLATION
    assert 0.0 <= desire.social_need <= 1.0
    assert 0.0 <= desire.solitude_need <= 1.0
    assert 0.0 <= desire.attention_availability <= 1.0


def test_solitary_reading_activity():
    """Verify reading activity elevates solitude need and constrains attention availability."""
    desire = DesireEvaluationEngine.evaluate(current_activity="reading")
    assert desire.primary_desire == PrimaryDesire.SOLITARY_FOCUS
    assert desire.current_focus == "reading"
    assert desire.solitude_need >= 0.70
    assert desire.attention_availability <= 0.40


def test_low_energy_rest_desire():
    """Verify low energy triggers REST_AND_RECHARGE desire."""
    desire = DesireEvaluationEngine.evaluate(energy=0.2, current_activity="REST")
    assert desire.primary_desire == PrimaryDesire.REST_AND_RECHARGE
    assert desire.solitude_need >= 0.60
    assert desire.energy == 0.2


def test_explicit_desire_overrides():
    """Verify explicit fixture strings correctly tune desires and focus."""
    # Chapter finish
    d1 = DesireEvaluationEngine.evaluate(override_desire="finish_current_chapter")
    assert d1.primary_desire == PrimaryDesire.SOLITARY_FOCUS
    assert "chapter" in (d1.current_focus or "")
    assert d1.solitude_need >= 0.75

    # Stay home
    d2 = DesireEvaluationEngine.evaluate(override_desire="stay_home")
    assert d2.primary_desire == PrimaryDesire.REST_AND_RECHARGE

    # Casual greeting
    d3 = DesireEvaluationEngine.evaluate(override_desire="open_to_casual_greeting")
    assert d3.primary_desire == PrimaryDesire.CASUAL_ENGAGEMENT
    assert d3.attention_availability >= 0.80


def test_desire_state_immutability():
    """Verify CharacterDesireState is frozen and rejects mutations."""
    desire = DesireEvaluationEngine.evaluate()
    with pytest.raises(Exception):
        desire.primary_desire = PrimaryDesire.PLAYFUL_DISTRACTION  # type: ignore
