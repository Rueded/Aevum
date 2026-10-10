"""Phase 19.2 — Prospective Thread Events & Transition Audit Records.

Defines the typed domain events, transition records, and payloads governing
the cognitive lifecycle of unresolved prospective threads.

Constitutional Locks:
- State Transition ≠ Semantic Progress (transitions only alter accessibility,
  never silently mutating preference, familiarity, or truth).
- Time as Context, NOT Trigger (time elapsed provides eligibility, but transition
  requires an authoritative domain event).
- Full Provenance: Every transition produces an immutable ThreadTransitionRecord.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.prospective.contracts import ClosureReasonKind, ThreadLifecycleState


class ThreadEventKind(str, Enum):
    """Categorical event types that can trigger thread state transitions."""
    CONTEXTUAL_ENCOUNTER = "CONTEXTUAL_ENCOUNTER"        # Semantic contextual encounter re-engages the thread
    SESSION_RECEDE = "SESSION_RECEDE"                    # Interaction focus recedes; thread settles into background
    REALITY_CLOSURE = "REALITY_CLOSURE"                  # Reality outcome or explicit decision settles the thread
    AUTHORITATIVE_SETTLEMENT = "AUTHORITATIVE_SETTLEMENT"  # Authoritative checkpoint (circadian/session) evaluation


class ThreadTransitionRecord(BaseModel):
    """Immutable audit record logging an authoritative state transition of a thread.
    
    Constitutional Invariant:
    Every lifecycle mutation must be captured in an immutable audit record.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    transition_id: str = Field(
        ...,
        min_length=1,
        description="Canonical identifier of the transition record (e.g. 'trns_123').",
    )
    thread_id: str = Field(
        ...,
        min_length=1,
        description="Identifier of the thread undergoing transition.",
    )
    from_state: ThreadLifecycleState = Field(
        ...,
        description="The source lifecycle state before transition.",
    )
    to_state: ThreadLifecycleState = Field(
        ...,
        description="The target lifecycle state after transition.",
    )
    trigger_event_kind: ThreadEventKind = Field(
        ...,
        description="The discrete event category that caused the transition.",
    )
    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Explainable semantic rationale behind the transition.",
    )
    timestamp: datetime = Field(
        ...,
        description="Authoritative timestamp when the transition was settled.",
    )
    origin_turn_id: Optional[str] = Field(
        default=None,
        description="Origin dialogue turn ID if triggered by conversational interaction.",
    )
    settlement_id: Optional[str] = Field(
        default=None,
        description="Authoritative settlement cycle ID if triggered by lifecycle settlement.",
    )


class ThreadEncounterPayload(BaseModel):
    """Payload representing a contextual encounter that touches an existing thread."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    thread_id: str = Field(..., min_length=1)
    context_summary: str = Field(..., min_length=1, max_length=500)
    encounter_timestamp: datetime = Field(...)
    turn_id: Optional[str] = Field(default=None)
    foreground: bool = Field(
        default=True,
        description="If True, awakens to ACTIVE focal foreground; if False, wakes lightly to QUIET.",
    )


class ThreadClosurePayload(BaseModel):
    """Payload representing an explicit resolution or termination of an unresolved thread."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    thread_id: str = Field(..., min_length=1)
    closure_reason: ClosureReasonKind = Field(...)
    closure_summary: str = Field(..., min_length=1, max_length=500)
    closed_at: datetime = Field(...)
    turn_id: Optional[str] = Field(default=None)


class SettlementContextPayload(BaseModel):
    """Payload representing an authoritative checkpoint for background recede evaluation."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    settlement_id: str = Field(..., min_length=1)
    settlement_timestamp: datetime = Field(...)
    character_id: str = Field(..., min_length=1)
