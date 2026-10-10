"""Phase 19.2 — Prospective Thread State Machine & Transition Rules.

Pure deterministic state machine enforcing legal lifecycle transitions,
temporal context evaluation, and audit record generation.

Constitutional Locks:
- Legal Transition Enclave: Enforces strict transition graph; terminal states
  (CLOSED, FORGOTTEN) are strictly immutable and irreversible.
- State Transition ≠ Semantic Progress: Transitions only change cognitive accessibility,
  never modifying preferences, experiences, or biography facts.
- Time as Context, NOT Trigger: Clock ticks never trigger mutations; transitions occur
  only when an authoritative event (encounter, recede, settlement) is processed.
"""

from datetime import datetime, timezone
from typing import FrozenSet, Optional, Tuple
import uuid

from app.prospective.contracts import (
    ClosureReasonKind,
    ProspectiveThread,
    ThreadEnduranceTier,
    ThreadLifecycleState,
)
from app.prospective.events import (
    SettlementContextPayload,
    ThreadClosurePayload,
    ThreadEncounterPayload,
    ThreadEventKind,
    ThreadTransitionRecord,
)


class InvalidThreadTransitionError(ValueError):
    """Raised when an illegal lifecycle state transition is attempted."""

    def __init__(
        self,
        thread_id: str,
        from_state: ThreadLifecycleState,
        to_state: ThreadLifecycleState,
        reason: str,
    ):
        self.thread_id = thread_id
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
        super().__init__(
            f"Illegal thread transition for '{thread_id}': "
            f"{from_state.value} -> {to_state.value}. Reason: {reason}"
        )


# ============================================================================
# Canonical Legal Transition Set
# ============================================================================

LEGAL_TRANSITIONS: FrozenSet[Tuple[ThreadLifecycleState, ThreadLifecycleState]] = frozenset({
    # From ACTIVE
    (ThreadLifecycleState.ACTIVE, ThreadLifecycleState.QUIET),      # Focus recedes to background
    (ThreadLifecycleState.ACTIVE, ThreadLifecycleState.CLOSED),     # Immediate focal resolution
    # From QUIET
    (ThreadLifecycleState.QUIET, ThreadLifecycleState.ACTIVE),      # Foregrounding via encounter
    (ThreadLifecycleState.QUIET, ThreadLifecycleState.DORMANT),     # Background subduction during settlement
    (ThreadLifecycleState.QUIET, ThreadLifecycleState.CLOSED),      # Background resolution
    (ThreadLifecycleState.QUIET, ThreadLifecycleState.FORGOTTEN),   # Direct dissolution of ephemeral talk
    # From DORMANT
    (ThreadLifecycleState.DORMANT, ThreadLifecycleState.ACTIVE),     # Resurgence to foreground focal awareness
    (ThreadLifecycleState.DORMANT, ThreadLifecycleState.QUIET),      # Faint awakening to background awareness
    (ThreadLifecycleState.DORMANT, ThreadLifecycleState.CLOSED),     # Dormant resolution
    (ThreadLifecycleState.DORMANT, ThreadLifecycleState.FORGOTTEN),  # Longitudinal dissolution into oblivion
})


class ThreadStateMachine:
    """Deterministic, pure-functional state machine for prospective threads."""

    @classmethod
    def is_transition_legal(
        cls,
        from_state: ThreadLifecycleState,
        to_state: ThreadLifecycleState,
    ) -> bool:
        """Checks if a transition between two states is permitted by the canonical graph."""
        return (from_state, to_state) in LEGAL_TRANSITIONS

    @classmethod
    def recede_to_quiet(
        cls,
        thread: ProspectiveThread,
        turn_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> Tuple[ProspectiveThread, ThreadTransitionRecord]:
        """Settles an ACTIVE thread into background QUIET state as interaction focus concludes."""
        ts = timestamp or datetime.now(timezone.utc)
        target_state = ThreadLifecycleState.QUIET

        if thread.lifecycle_state != ThreadLifecycleState.ACTIVE:
            raise InvalidThreadTransitionError(
                thread_id=thread.thread_id,
                from_state=thread.lifecycle_state,
                to_state=target_state,
                reason="Only ACTIVE threads can recede to QUIET via SESSION_RECEDE.",
            )

        updated_thread = thread.model_copy(
            update={
                "lifecycle_state": target_state,
                "updated_at": ts,
            }
        )

        record = ThreadTransitionRecord(
            transition_id=f"trns_{uuid.uuid4().hex[:12]}",
            thread_id=thread.thread_id,
            from_state=thread.lifecycle_state,
            to_state=target_state,
            trigger_event_kind=ThreadEventKind.SESSION_RECEDE,
            reason="Interaction focus subsided; thread settled into background awareness.",
            timestamp=ts,
            origin_turn_id=turn_id,
        )

        return updated_thread, record

    @classmethod
    def encounter_thread(
        cls,
        thread: ProspectiveThread,
        payload: ThreadEncounterPayload,
    ) -> Tuple[ProspectiveThread, Optional[ThreadTransitionRecord]]:
        """Applies a contextual semantic encounter to an existing thread.
        
        If the thread is in QUIET or DORMANT, transitions it to ACTIVE (or QUIET if faint).
        If the thread is already in ACTIVE, updates last_contextual_contact_at without state change.
        Raises InvalidThreadTransitionError if the thread is CLOSED or FORGOTTEN.
        """
        if thread.lifecycle_state in (ThreadLifecycleState.CLOSED, ThreadLifecycleState.FORGOTTEN):
            raise InvalidThreadTransitionError(
                thread_id=thread.thread_id,
                from_state=thread.lifecycle_state,
                to_state=ThreadLifecycleState.ACTIVE,
                reason="Terminal states (CLOSED, FORGOTTEN) cannot be reactivated by encounter.",
            )

        target_state = (
            ThreadLifecycleState.ACTIVE if payload.foreground else ThreadLifecycleState.QUIET
        )

        # Same-state refresh (e.g. ACTIVE -> ACTIVE or QUIET -> QUIET)
        if thread.lifecycle_state == target_state:
            updated_thread = thread.model_copy(
                update={
                    "last_contextual_contact_at": payload.encounter_timestamp,
                    "updated_at": payload.encounter_timestamp,
                }
            )
            return updated_thread, None

        if not cls.is_transition_legal(thread.lifecycle_state, target_state):
            raise InvalidThreadTransitionError(
                thread_id=thread.thread_id,
                from_state=thread.lifecycle_state,
                to_state=target_state,
                reason=f"Cannot transition from {thread.lifecycle_state.value} to {target_state.value} via encounter.",
            )

        updated_thread = thread.model_copy(
            update={
                "lifecycle_state": target_state,
                "last_contextual_contact_at": payload.encounter_timestamp,
                "updated_at": payload.encounter_timestamp,
            }
        )

        record = ThreadTransitionRecord(
            transition_id=f"trns_{uuid.uuid4().hex[:12]}",
            thread_id=thread.thread_id,
            from_state=thread.lifecycle_state,
            to_state=target_state,
            trigger_event_kind=ThreadEventKind.CONTEXTUAL_ENCOUNTER,
            reason=f"Contextual encounter touched thread: {payload.context_summary}",
            timestamp=payload.encounter_timestamp,
            origin_turn_id=payload.turn_id,
        )

        return updated_thread, record

    @classmethod
    def close_thread(
        cls,
        thread: ProspectiveThread,
        payload: ThreadClosurePayload,
    ) -> Tuple[ProspectiveThread, ThreadTransitionRecord]:
        """Settles an unresolved thread into terminal CLOSED state."""
        target_state = ThreadLifecycleState.CLOSED

        if thread.lifecycle_state in (ThreadLifecycleState.CLOSED, ThreadLifecycleState.FORGOTTEN):
            raise InvalidThreadTransitionError(
                thread_id=thread.thread_id,
                from_state=thread.lifecycle_state,
                to_state=target_state,
                reason="Terminal states (CLOSED, FORGOTTEN) cannot be closed again.",
            )

        updated_thread = thread.model_copy(
            update={
                "lifecycle_state": target_state,
                "closure_reason": payload.closure_reason,
                "closure_summary": payload.closure_summary,
                "closed_at": payload.closed_at,
                "updated_at": payload.closed_at,
            }
        )

        record = ThreadTransitionRecord(
            transition_id=f"trns_{uuid.uuid4().hex[:12]}",
            thread_id=thread.thread_id,
            from_state=thread.lifecycle_state,
            to_state=target_state,
            trigger_event_kind=ThreadEventKind.REALITY_CLOSURE,
            reason=f"Resolved via {payload.closure_reason.value}: {payload.closure_summary}",
            timestamp=payload.closed_at,
            origin_turn_id=payload.turn_id,
        )

        return updated_thread, record

    @classmethod
    def evaluate_settlement_recede(
        cls,
        thread: ProspectiveThread,
        payload: SettlementContextPayload,
        hours_since_contact: float,
    ) -> Optional[Tuple[ProspectiveThread, ThreadTransitionRecord]]:
        """Evaluates background decay eligibility during an authoritative settlement moment.
        
        Constitutional Invariant:
        Time is context, NOT trigger. The transition is triggered by the AUTHORITATIVE_SETTLEMENT
        event, with hours_since_contact providing the contextual eligibility threshold.
        """
        # Terminal threads are immune to settlement recede
        if thread.lifecycle_state in (ThreadLifecycleState.CLOSED, ThreadLifecycleState.FORGOTTEN):
            return None

        # ACTIVE threads do not recede during settlement without an explicit session recede
        if thread.lifecycle_state == ThreadLifecycleState.ACTIVE:
            return None

        # Case 1: QUIET state recede evaluation
        if thread.lifecycle_state == ThreadLifecycleState.QUIET:
            # Ephemeral talk that had no contact for > 48 hours dissolves directly
            if thread.salience.endurance == ThreadEnduranceTier.EPHEMERAL_TALK and hours_since_contact >= 48.0:
                target_state = ThreadLifecycleState.FORGOTTEN
                reason = "Ephemeral thread natural dissolution after 48h without contact."
            elif hours_since_contact >= 72.0:  # > 3 days without contact
                target_state = ThreadLifecycleState.DORMANT
                reason = "Background thread subduction into subconscious dormancy after 72h without contact."
            else:
                return None  # Eligibility threshold not met; stays in QUIET

            updated_thread = thread.model_copy(
                update={
                    "lifecycle_state": target_state,
                    "updated_at": payload.settlement_timestamp,
                }
            )

            record = ThreadTransitionRecord(
                transition_id=f"trns_{uuid.uuid4().hex[:12]}",
                thread_id=thread.thread_id,
                from_state=thread.lifecycle_state,
                to_state=target_state,
                trigger_event_kind=ThreadEventKind.AUTHORITATIVE_SETTLEMENT,
                reason=reason,
                timestamp=payload.settlement_timestamp,
                settlement_id=payload.settlement_id,
            )
            return updated_thread, record

        # Case 2: DORMANT state recede evaluation
        if thread.lifecycle_state == ThreadLifecycleState.DORMANT:
            # Durable arcs resist longitudinal forgetting; seasonal/ephemeral dissolve after 30 days (720h)
            if thread.salience.endurance != ThreadEnduranceTier.DURABLE_ARC and hours_since_contact >= 720.0:
                target_state = ThreadLifecycleState.FORGOTTEN
                reason = "Non-durable dormant thread faded into oblivion after 30 days without contact."

                updated_thread = thread.model_copy(
                    update={
                        "lifecycle_state": target_state,
                        "updated_at": payload.settlement_timestamp,
                    }
                )

                record = ThreadTransitionRecord(
                    transition_id=f"trns_{uuid.uuid4().hex[:12]}",
                    thread_id=thread.thread_id,
                    from_state=thread.lifecycle_state,
                    to_state=target_state,
                    trigger_event_kind=ThreadEventKind.AUTHORITATIVE_SETTLEMENT,
                    reason=reason,
                    timestamp=payload.settlement_timestamp,
                    settlement_id=payload.settlement_id,
                )
                return updated_thread, record

        return None
