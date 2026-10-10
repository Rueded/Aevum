"""
verification_dispatcher.py — Phase 15.4 Verification Dispatcher Bridge

Phase 15.4 Deliverable under ADR-026 (Architecture Gate Approved & Frozen):
- Evaluates whether an utterance requires routing to Phase 9 Epistemic Verification.
- Generates deterministic, strictly typed `VerificationDispatchEnvelope` with `VerificationRequest`.
- Constitutional Lock 4: External Verification != Automatic Truth Mutation.
  (Phase 15.4 produces verification requests; it NEVER calls set_fact(), mints tokens,
  or modifies canonical reality).
- Zero Autonomous Network Execution: Strictly delegates to Phase 9 Gateway; zero HTTP
  or web search imports.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
import re
from typing import Optional

from app.reality.epistemic_policy_models import EpistemicTreatmentKind
from app.reality.verification_dispatcher_models import (
    VerificationDispatcherContext,
    VerificationDispatchEnvelope,
    VerificationDispatchStatus,
)
from app.reality.verification_models import (
    ClaimDomain,
    ConsequenceTier,
    VerificationRequest,
    VerificationUrgency,
)


def _canonical_key_from_text(text: str) -> str:
    """Generate a clean, deterministic claim key from text."""
    clean = re.sub(r"[^a-zA-Z0-9_\u4e00-\u9fa5]+", ".", text.strip().lower())
    clean = clean.strip(".")
    if not clean:
        clean = "claim.unspecified"
    parts = clean.split(".")[:4]
    return ".".join(parts)


class VerificationDispatcher:
    """
    Dispatcher bridge connecting Phase 15 social pragmatics to Phase 9 epistemic verification.
    """

    @classmethod
    def create_dispatch_envelope(
        cls,
        context: VerificationDispatcherContext,
        now: Optional[datetime] = None,
    ) -> VerificationDispatchEnvelope:
        """
        Formulate a VerificationDispatchEnvelope for Phase 9 handoff.
        """
        eval_time = now or datetime.now(timezone.utc)
        decision = context.treatment_decision
        interp = context.pragmatic_interpretation

        # Step 1: Check if verification was recommended by EpistemicPolicyEngine
        if not decision.dispatch_verification_recommended:
            return VerificationDispatchEnvelope(
                envelope_id=f"env_skip_{context.turn_id}_{interp.primary_act.value}",
                dispatch_status=VerificationDispatchStatus.SKIPPED_NOT_RECOMMENDED,
                verification_request=None,
                originating_turn_text=context.user_text,
                pragmatic_act=interp.primary_act,
                rationale="Epistemic treatment policy did not recommend external verification.",
            )

        # Step 2: Formulate deterministic claim key and value
        claim_key = context.claim_key or f"external.{_canonical_key_from_text(context.user_text)}"
        claim_value = interp.literal_proposition or context.user_text.strip()

        # Step 3: Compute deterministic request ID
        hash_digest = hashlib.sha256(f"{context.turn_id}:{claim_key}:{claim_value}".encode("utf-8")).hexdigest()[:12]
        request_id = f"vreq_{context.turn_id}_{hash_digest}"

        # Step 4: Construct Phase 9 VerificationRequest (pure, immutable, extra="forbid")
        verification_request = VerificationRequest(
            request_id=request_id,
            created_at=eval_time,
            claim_domain=context.claim_domain,
            claim_key=claim_key,
            claim_value=claim_value,
            consequence_tier=context.consequence_tier,
            urgency=context.urgency,
            entity_binding_anchor=context.entity_binding_anchor,
            initiating_turn_id=context.turn_id,
        )

        envelope_id = f"env_disp_{request_id}"

        return VerificationDispatchEnvelope(
            envelope_id=envelope_id,
            dispatch_status=VerificationDispatchStatus.DISPATCHED,
            verification_request=verification_request,
            originating_turn_text=context.user_text,
            pragmatic_act=interp.primary_act,
            rationale=(
                f"High-consequence proposition '{claim_key}' successfully packaged for Phase 9 "
                "Epistemic Verification Gateway."
            ),
        )
