"""
verification_dispatcher_models.py — Verification Dispatcher Contracts & Schemas

Phase 15.4 Deliverable under ADR-026 (Architecture Gate Approved & Frozen):
- Bridges Phase 15.2 DISPATCH_VERIFICATION decisions to Phase 9 VerificationRequest.
- Pure immutable DTOs: VerificationDispatchStatus, VerificationDispatchEnvelope,
  VerificationDispatcherContext.
- Constitutional Lock 4: External Verification != Automatic Truth Mutation.
  (Verification findings remain external evidence; 0 direct set_fact() authority.)
- Permanent Note A: Zero float confidence scores or pseudo-probabilities.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.reality.epistemic_policy_models import EpistemicTreatmentDecision
from app.reality.speech_act_models import PragmaticInterpretation, SpeechActKind
from app.reality.verification_models import (
    ClaimDomain,
    ConsequenceTier,
    VerificationRequest,
    VerificationUrgency,
)


class VerificationDispatchStatus(str, Enum):
    """Lifecycle status of the verification dispatch attempt."""

    DISPATCHED = "DISPATCHED"                           # Successfully packaged and routed for Phase 9 verification
    SKIPPED_NOT_RECOMMENDED = "SKIPPED_NOT_RECOMMENDED"  # Decision did not recommend verification
    SKIPPED_LOW_CONSEQUENCE = "SKIPPED_LOW_CONSEQUENCE"  # Trivial proposition deemed unnecessary to verify
    SUPPRESSED_BY_CONTEXT = "SUPPRESSED_BY_CONTEXT"      # Suppressed due to lack of verifiable proposition


class VerificationDispatcherContext(BaseModel):
    """
    Immutable context supplied to the VerificationDispatcher.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    turn_id: str = Field(..., description="ID of current conversation turn")
    user_text: str = Field(..., description="Raw user utterance")
    treatment_decision: EpistemicTreatmentDecision = Field(..., description="Epistemic treatment decision from Phase 15.2")
    pragmatic_interpretation: PragmaticInterpretation = Field(..., description="Pragmatic interpretation from Phase 15.1")
    consequence_tier: ConsequenceTier = Field(
        default=ConsequenceTier.HIGH,
        description="Consequence tier for Phase 9 policy evaluation",
    )
    urgency: VerificationUrgency = Field(
        default=VerificationUrgency.IMMEDIATE_TURN,
        description="Verification urgency priority",
    )
    claim_domain: ClaimDomain = Field(
        default=ClaimDomain.WORLD_REALITY,
        description="Target claim domain (WORLD_REALITY for external institutional claims)",
    )
    claim_key: Optional[str] = Field(None, description="Explicit structured claim key if known")
    entity_binding_anchor: Optional[str] = Field(
        None,
        description="Entity anchor for personal reality claims (Lock 8)",
    )


class VerificationDispatchEnvelope(BaseModel):
    """
    Immutable handoff envelope containing the Phase 9 VerificationRequest.
    Possesses zero execution or promotion authority.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    envelope_id: str = Field(..., description="Unique deterministic identifier for this dispatch envelope")
    dispatch_status: VerificationDispatchStatus = Field(..., description="Outcome of dispatch packaging")
    verification_request: Optional[VerificationRequest] = Field(
        None,
        description="Constructed Phase 9 VerificationRequest if dispatched, None if skipped",
    )
    originating_turn_text: str = Field(..., description="Verbatim user utterance that triggered dispatch")
    pragmatic_act: SpeechActKind = Field(..., description="Speech act that motivated dispatch")
    rationale: str = Field(..., description="Deterministic architectural explanation of dispatch decision")
