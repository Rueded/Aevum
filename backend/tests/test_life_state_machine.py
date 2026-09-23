import pytest
from datetime import datetime, timedelta, timezone
from app.life.models import LifeActivityStatus, LifePlanStatus
from app.life.state_machine import LifeStateMachine, InvalidStateTransitionError
from app.life.clock import RealTimeClock, DeterministicSimulationClock

def test_simulation_clock_realtime():
    clock = RealTimeClock()
    t1 = clock.now()
    assert t1.tzinfo is not None
    assert t1.tzinfo == timezone.utc

def test_deterministic_simulation_clock():
    base_time = datetime(2026, 9, 18, 9, 0, 0, tzinfo=timezone.utc)
    clock = DeterministicSimulationClock(base_time)
    assert clock.now() == base_time
    
    # Advance clock by 2 hours
    clock.advance(timedelta(hours=2))
    assert clock.now() == datetime(2026, 9, 18, 11, 0, 0, tzinfo=timezone.utc)
    
    # Advance clock by 6 hours (total 8 hours)
    clock.advance(timedelta(hours=6))
    assert clock.now() == datetime(2026, 9, 18, 17, 0, 0, tzinfo=timezone.utc)
    
    # Explicitly set time
    new_time = datetime(2026, 9, 19, 0, 0, 0, tzinfo=timezone.utc)
    clock.set_time(new_time)
    assert clock.now() == new_time

def test_deterministic_simulation_clock_naive_handling():
    naive = datetime(2026, 1, 1, 10, 0, 0)
    clock = DeterministicSimulationClock(naive)
    assert clock.now().tzinfo == timezone.utc

def test_activity_state_machine_valid_transitions():
    assert LifeStateMachine.validate_activity_transition(
        LifeActivityStatus.ONGOING, LifeActivityStatus.COMPLETED
    ) is True
    assert LifeStateMachine.validate_activity_transition(
        LifeActivityStatus.ONGOING, LifeActivityStatus.CANCELLED
    ) is True

def test_activity_state_machine_idempotent_noops():
    assert LifeStateMachine.validate_activity_transition(
        LifeActivityStatus.COMPLETED, LifeActivityStatus.COMPLETED
    ) is False
    assert LifeStateMachine.validate_activity_transition(
        LifeActivityStatus.CANCELLED, LifeActivityStatus.CANCELLED
    ) is False
    assert LifeStateMachine.validate_activity_transition(
        LifeActivityStatus.ONGOING, LifeActivityStatus.ONGOING
    ) is False

def test_activity_state_machine_illegal_transitions():
    with pytest.raises(InvalidStateTransitionError):
        LifeStateMachine.validate_activity_transition(
            LifeActivityStatus.COMPLETED, LifeActivityStatus.ONGOING
        )
    with pytest.raises(InvalidStateTransitionError):
        LifeStateMachine.validate_activity_transition(
            LifeActivityStatus.COMPLETED, LifeActivityStatus.CANCELLED
        )
    with pytest.raises(InvalidStateTransitionError):
        LifeStateMachine.validate_activity_transition(
            LifeActivityStatus.CANCELLED, LifeActivityStatus.ONGOING
        )
    with pytest.raises(InvalidStateTransitionError):
        LifeStateMachine.validate_activity_transition(
            LifeActivityStatus.CANCELLED, LifeActivityStatus.COMPLETED
        )

def test_plan_state_machine_valid_transitions():
    assert LifeStateMachine.validate_plan_transition(
        LifePlanStatus.PLANNED, LifePlanStatus.IN_PROGRESS
    ) is True
    assert LifeStateMachine.validate_plan_transition(
        LifePlanStatus.PLANNED, LifePlanStatus.CANCELLED
    ) is True
    assert LifeStateMachine.validate_plan_transition(
        LifePlanStatus.IN_PROGRESS, LifePlanStatus.COMPLETED
    ) is True
    assert LifeStateMachine.validate_plan_transition(
        LifePlanStatus.IN_PROGRESS, LifePlanStatus.CANCELLED
    ) is True

def test_plan_state_machine_idempotent_noops():
    assert LifeStateMachine.validate_plan_transition(
        LifePlanStatus.COMPLETED, LifePlanStatus.COMPLETED
    ) is False
    assert LifeStateMachine.validate_plan_transition(
        LifePlanStatus.CANCELLED, LifePlanStatus.CANCELLED
    ) is False
    assert LifeStateMachine.validate_plan_transition(
        LifePlanStatus.IN_PROGRESS, LifePlanStatus.IN_PROGRESS
    ) is False
    assert LifeStateMachine.validate_plan_transition(
        LifePlanStatus.PLANNED, LifePlanStatus.PLANNED
    ) is False

def test_plan_state_machine_illegal_transitions():
    with pytest.raises(InvalidStateTransitionError):
        LifeStateMachine.validate_plan_transition(
            LifePlanStatus.COMPLETED, LifePlanStatus.IN_PROGRESS
        )
    with pytest.raises(InvalidStateTransitionError):
        LifeStateMachine.validate_plan_transition(
            LifePlanStatus.COMPLETED, LifePlanStatus.PLANNED
        )
    with pytest.raises(InvalidStateTransitionError):
        LifeStateMachine.validate_plan_transition(
            LifePlanStatus.IN_PROGRESS, LifePlanStatus.PLANNED
        )
    with pytest.raises(InvalidStateTransitionError):
        LifeStateMachine.validate_plan_transition(
            LifePlanStatus.CANCELLED, LifePlanStatus.PLANNED
        )

def test_terminal_predicates():
    assert LifeStateMachine.is_activity_terminal(LifeActivityStatus.COMPLETED) is True
    assert LifeStateMachine.is_activity_terminal(LifeActivityStatus.CANCELLED) is True
    assert LifeStateMachine.is_activity_terminal(LifeActivityStatus.ONGOING) is False

    assert LifeStateMachine.is_plan_terminal(LifePlanStatus.COMPLETED) is True
    assert LifeStateMachine.is_plan_terminal(LifePlanStatus.CANCELLED) is True
    assert LifeStateMachine.is_plan_terminal(LifePlanStatus.PLANNED) is False
    assert LifeStateMachine.is_plan_terminal(LifePlanStatus.IN_PROGRESS) is False
