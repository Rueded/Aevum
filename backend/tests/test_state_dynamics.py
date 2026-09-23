import pytest
from datetime import datetime, timezone
from app.life.physiological_models import (
    ActivityPhysiologicalProfile,
    CANONICAL_ACTIVITY_PROFILES,
    CharacterPhysiologicalState,
    PhysiologicalBand,
    StateTransitionTrigger,
    map_activity_to_profile,
)
from app.life.state_dynamics import (
    PhysiologicalBandClassifier,
    StateDynamicsEngine,
)
from app.character.desire_service import DesireEvaluationEngine
from app.character.desire_models import PrimaryDesire

def test_physiological_band_classifier():
    # 1. Refreshed
    assert PhysiologicalBandClassifier.classify(
        energy=0.85, fatigue=0.10, stress=0.10, sleep_pressure=0.20
    ) == PhysiologicalBand.REFRESHED

    # 2. Steady
    assert PhysiologicalBandClassifier.classify(
        energy=0.60, fatigue=0.35, stress=0.25, sleep_pressure=0.35
    ) == PhysiologicalBand.STEADY

    # 3. Fatigued
    assert PhysiologicalBandClassifier.classify(
        energy=0.25, fatigue=0.65, stress=0.30, sleep_pressure=0.40
    ) == PhysiologicalBand.FATIGUED

    # 4. Drowsy
    assert PhysiologicalBandClassifier.classify(
        energy=0.50, fatigue=0.40, stress=0.20, sleep_pressure=0.80
    ) == PhysiologicalBand.DROWSY

    # 5. Overloaded
    assert PhysiologicalBandClassifier.classify(
        energy=0.30, fatigue=0.75, stress=0.65, sleep_pressure=0.60
    ) == PhysiologicalBand.OVERLOADED

def test_state_dynamics_study_interval():
    # Moderate cognitive activity (1 hour)
    before = CharacterPhysiologicalState(
        energy=0.80, fatigue=0.10, stress=0.10, sleep_pressure=0.20
    )
    profile = CANONICAL_ACTIVITY_PROFILES["MODERATE_COGNITIVE"]
    
    after, record = StateDynamicsEngine.evaluate_interval(
        before_state=before,
        duration_seconds=3600.0,
        profile=profile,
        circadian_modifier=0.5,
    )
    
    # Energy should decrease (-0.12)
    assert round(after.energy, 2) == 0.68
    # Fatigue should increase (+0.14)
    assert round(after.fatigue, 2) == 0.24
    # Stress should increase (+0.04)
    assert round(after.stress, 2) == 0.14
    # Sleep pressure should increase (+0.06)
    assert round(after.sleep_pressure, 2) == 0.26
    
    # Audit record check
    assert record.rule_id == "profile.MODERATE_COGNITIVE.v1"
    assert record.time_interval_seconds == 3600.0
    assert record.delta["energy"] < 0
    assert record.delta["fatigue"] > 0

def test_state_dynamics_sleep_interval():
    # Sleep activity (7 hours)
    before = CharacterPhysiologicalState(
        energy=0.30, fatigue=0.70, stress=0.50, sleep_pressure=0.85
    )
    profile = CANONICAL_ACTIVITY_PROFILES["SLEEP"]
    
    after, record = StateDynamicsEngine.evaluate_interval(
        before_state=before,
        duration_seconds=7 * 3600.0,
        profile=profile,
        trigger_type=StateTransitionTrigger.SLEEP_CYCLE,
    )
    
    # Sleep clears sleep pressure
    assert after.sleep_pressure < 0.10
    # Sleep restores energy
    assert after.energy > 0.80
    # Sleep clears fatigue
    assert after.fatigue < 0.20
    # Sleep reduces stress
    assert after.stress < 0.20
    assert after.qualitative_band == PhysiologicalBand.REFRESHED
    assert record.rule_id == "profile.SLEEP.v1"

def test_state_dynamics_no_double_counting():
    # Invariant 17: Routine activity completion produces zero acute wear
    before = CharacterPhysiologicalState(
        energy=0.60, fatigue=0.40, stress=0.30, sleep_pressure=0.40
    )
    after, record = StateDynamicsEngine.evaluate_acute_event(
        before_state=before,
        event_type_str="ACTIVITY_COMPLETED",
        significance=0.8,
    )
    assert after.energy == before.energy
    assert after.fatigue == before.fatigue
    assert after.stress == before.stress
    assert record is None

def test_state_dynamics_acute_shocks():
    before = CharacterPhysiologicalState(
        energy=0.70, fatigue=0.20, stress=0.20, sleep_pressure=0.30
    )
    
    # Setback raises stress
    after_setback, rec_setback = StateDynamicsEngine.evaluate_acute_event(
        before_state=before,
        event_type_str="SETBACK",
        significance=0.8,
    )
    assert after_setback.stress > before.stress
    assert rec_setback.rule_id == "acute.setback.v1"
    
    # Success reduces stress
    after_success, rec_success = StateDynamicsEngine.evaluate_acute_event(
        before_state=after_setback,
        event_type_str="SUCCESS",
        significance=0.8,
    )
    assert after_success.stress < after_setback.stress
    assert rec_success.rule_id == "acute.success.v1"

def test_desire_service_physiological_integration():
    # 1. Drowsy state drives REST_AND_RECHARGE
    drowsy_state = CharacterPhysiologicalState(
        energy=0.40, fatigue=0.50, stress=0.20, sleep_pressure=0.80,
        qualitative_band=PhysiologicalBand.DROWSY
    )
    desire = DesireEvaluationEngine.evaluate(
        physiological_state=drowsy_state,
        current_activity="REST",
    )
    assert desire.primary_desire == PrimaryDesire.REST_AND_RECHARGE
    assert desire.attention_availability <= 0.25

    # 2. Refreshed state enables high attention availability
    refreshed_state = CharacterPhysiologicalState(
        energy=0.85, fatigue=0.10, stress=0.10, sleep_pressure=0.15,
        qualitative_band=PhysiologicalBand.REFRESHED
    )
    desire_refreshed = DesireEvaluationEngine.evaluate(
        physiological_state=refreshed_state,
        current_activity="reading",
    )
    assert desire_refreshed.attention_availability >= 0.70
