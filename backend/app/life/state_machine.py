from enum import Enum
from typing import Set, Tuple
from app.life.models import LifeActivityStatus, LifePlanStatus

class InvalidStateTransitionError(ValueError):
    """Raised when an illegal state transition is attempted on Life entities."""
    pass

class LifeStateMachine:
    """
    Authoritative state machine governing LifeActivity and LifePlan lifecycles.
    Enforces Invariant 11: Transitions are strictly unidirectional and idempotent.
    """

    _VALID_ACTIVITY_TRANSITIONS: Set[Tuple[LifeActivityStatus, LifeActivityStatus]] = {
        (LifeActivityStatus.ONGOING, LifeActivityStatus.COMPLETED),
        (LifeActivityStatus.ONGOING, LifeActivityStatus.CANCELLED),
    }

    _VALID_PLAN_TRANSITIONS: Set[Tuple[LifePlanStatus, LifePlanStatus]] = {
        (LifePlanStatus.PLANNED, LifePlanStatus.IN_PROGRESS),
        (LifePlanStatus.PLANNED, LifePlanStatus.CANCELLED),
        (LifePlanStatus.IN_PROGRESS, LifePlanStatus.COMPLETED),
        (LifePlanStatus.IN_PROGRESS, LifePlanStatus.CANCELLED),
    }

    @classmethod
    def is_activity_terminal(cls, status: LifeActivityStatus) -> bool:
        """Return True if activity is in a terminal state (COMPLETED or CANCELLED)."""
        return status in (LifeActivityStatus.COMPLETED, LifeActivityStatus.CANCELLED)

    @classmethod
    def is_plan_terminal(cls, status: LifePlanStatus) -> bool:
        """Return True if plan is in a terminal state (COMPLETED or CANCELLED)."""
        return status in (LifePlanStatus.COMPLETED, LifePlanStatus.CANCELLED)

    @classmethod
    def validate_activity_transition(
        cls, current_status: LifeActivityStatus, target_status: LifeActivityStatus
    ) -> bool:
        """
        Validate transition from current_status to target_status for LifeActivity.
        Returns:
            True if state must be updated.
            False if it's an idempotent no-op (current == target).
        Raises:
            InvalidStateTransitionError if the transition violates lifecycle rules.
        """
        if current_status == target_status:
            return False  # Idempotent no-op

        if (current_status, target_status) in cls._VALID_ACTIVITY_TRANSITIONS:
            return True

        raise InvalidStateTransitionError(
            f"Invalid LifeActivity transition from {current_status.value} to {target_status.value}. "
            f"Terminal states cannot be reverted or changed."
        )

    @classmethod
    def validate_plan_transition(
        cls, current_status: LifePlanStatus, target_status: LifePlanStatus
    ) -> bool:
        """
        Validate transition from current_status to target_status for LifePlan.
        Returns:
            True if state must be updated.
            False if it's an idempotent no-op (current == target).
        Raises:
            InvalidStateTransitionError if the transition violates lifecycle rules.
        """
        if current_status == target_status:
            return False  # Idempotent no-op

        if (current_status, target_status) in cls._VALID_PLAN_TRANSITIONS:
            return True

        raise InvalidStateTransitionError(
            f"Invalid LifePlan transition from {current_status.value} to {target_status.value}. "
            f"Plan transitions are strictly unidirectional."
        )
