"""
verification_policy_engine.py — Consequence-Aware Verification Policy Engine

Phase 9.2 Deliverable under Architecture Gate v0.2:
- Evaluates whether, when, and under what constraints external verification may be requested.
- Decision-only policy engine: zero execution authority, zero network calls, zero DB operations.
- Enforces AGENTS.md Rule 17 (Rate limits, Quiet hours, Autonomous constraints) and Rule 18 (Privacy & Consent).
- Strict categorical gating: maps consequence tiers to required source authority classes.
- World vs. Personal domain authority guard (Lock 4):
    - World claims cannot be dictated by personal dialogue alone.
    - Personal claims cannot be dictated by unverified external web data (Lock 8).
- Strict non-probabilistic representation: zero float scores or pseudo-probabilities.

Zero network calls, zero database writes, zero LLM dependencies, zero mutation authority.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field

from app.reality.verification_models import (
    ClaimDomain,
    SourceAuthority,
    SourceKind,
    VerificationScope,
    VerificationUrgency,
    ConsequenceTier,
    VerificationRequest,
)


# ==============================================================================
# 1. Policy Gating Enums
# ==============================================================================


class VerificationPrivacyScope(str, Enum):
    """Categorical privacy boundary for verification lookups (Rule 18)."""
    PUBLIC_DATA_ONLY = "PUBLIC_DATA_ONLY"              # Open institutional websites, public registers
    FIRST_PARTY_CONSENTED = "FIRST_PARTY_CONSENTED"    # Personal data explicitly authorized by user
    FORBIDDEN_PRIVATE = "FORBIDDEN_PRIVATE"            # Strictly private/unconsented information


class QuietHoursBehavior(str, Enum):
    """Behavior applied when verification is triggered during quiet hours (Rule 17)."""
    PROCEED_SILENT_BACKGROUND = "PROCEED_SILENT_BACKGROUND"  # Silent background job without user notification
    DEFER_UNTIL_ACTIVE_HOURS = "DEFER_UNTIL_ACTIVE_HOURS"    # Queue and defer until quiet hours end
    SUPPRESS_TERMINAL = "SUPPRESS_TERMINAL"                  # Discard request during quiet hours


class RateLimitClass(str, Enum):
    """Execution pace class for rate limiting and cost control."""
    STANDARD = "STANDARD"            # Normal background pacing
    THROTTLED = "THROTTLED"          # Constrained resource or high frequency pacing
    BURST_PERMITTED = "BURST_PERMITTED"  # High-priority blocker for immediate turn


# ==============================================================================
# 2. Policy Input Context & Decision Contracts
# ==============================================================================


class VerificationCostBudget(BaseModel):
    """Bounded operational budget for an authorized verification request."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_queries: int = Field(default=1, ge=1, le=5, description="Maximum discrete queries allowed")
    timeout_seconds: int = Field(default=10, ge=1, le=60, description="Max execution duration in seconds")
    rate_limit_class: RateLimitClass = Field(default=RateLimitClass.STANDARD)


class VerificationPolicyContext(BaseModel):
    """
    Environmental and governance context supplied to the policy engine.
    Encapsulates current time, quiet hours, user consent, and quota limits.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    current_time: datetime = Field(..., description="Authoritative reference timestamp")
    is_quiet_hours: bool = Field(default=False, description="True if within user-configured quiet hours")
    user_privacy_consented: bool = Field(
        default=False,
        description="True if user explicitly consented to personal factual verification (Rule 18)"
    )
    turn_verification_budget_remaining: int = Field(
        default=2,
        ge=0,
        description="Remaining verification requests allowed in the current reality turn"
    )
    daily_verification_count: int = Field(
        default=0,
        ge=0,
        description="Number of verification lookups already performed today"
    )
    daily_verification_cap: int = Field(
        default=10,
        ge=1,
        description="Maximum daily verification lookups permitted"
    )


class VerificationDecision(BaseModel):
    """
    Immutable outcome of the policy engine evaluation.
    Dictates IF and HOW verification may be executed by downstream components.
    Possesses ZERO execution authority (Lock 2).
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_id: str = Field(..., description="Unique deterministic identifier for this policy decision")
    request_id: str = Field(..., description="Origin VerificationRequest identifier")
    claim_key: str = Field(..., description="Target claim key")
    claim_domain: ClaimDomain = Field(..., description="Domain of claim")
    consequence_tier: ConsequenceTier = Field(..., description="Assessed consequence tier")
    should_verify: bool = Field(..., description="True if verification is authorized to proceed")
    suppression_reason: Optional[str] = Field(None, description="Reason code if verification is suppressed or deferred")
    target_scope: VerificationScope = Field(..., description="Target scope alignment required")
    urgency: VerificationUrgency = Field(..., description="Assigned execution urgency")
    privacy_scope: VerificationPrivacyScope = Field(..., description="Permitted privacy boundary")
    allowed_authorities: tuple[SourceAuthority, ...] = Field(..., description="Permitted source authorities")
    allowed_source_kinds: tuple[SourceKind, ...] = Field(..., description="Permitted source operational kinds")
    cost_budget: VerificationCostBudget = Field(..., description="Allocated operational budget")
    quiet_hours_behavior: QuietHoursBehavior = Field(..., description="Behavior under quiet hours")
    policy_rule_id: str = Field(..., description="Triggered policy rule identifier")
    rationale: str = Field(..., description="Explanatory rationale for the decision")
    evaluated_at: datetime = Field(..., description="Timestamp of evaluation")


# ==============================================================================
# 3. Consequence-Aware Policy Engine
# ==============================================================================


class VerificationPolicyEngine:
    """
    Deterministic Policy Engine for External Reality Verification.

    Core Invariant (Lock 2):
    Policy decides IF and UNDER WHAT CONSTRAINTS verification may be sought.
    It NEVER invokes network, web tools, databases, or LLMs.
    """

    def evaluate(
        self,
        request: VerificationRequest,
        context: VerificationPolicyContext,
        decision_id: Optional[str] = None,
    ) -> VerificationDecision:
        """
        Evaluate a VerificationRequest against governance, consequence, and privacy constraints.
        Pure deterministic evaluation with zero side effects.
        """
        now = context.current_time
        effective_decision_id = decision_id or f"vdec-{uuid4().hex[:12]}"

        # ----------------------------------------------------------------------
        # Guard 1: Privacy & Consent Guard (AGENTS.md Rule 18)
        # Personal reality verification strictly requires explicit user consent.
        # ----------------------------------------------------------------------
        if request.claim_domain == ClaimDomain.PERSONAL_REALITY and not context.user_privacy_consented:
            return VerificationDecision(
                decision_id=effective_decision_id,
                request_id=request.request_id,
                claim_key=request.claim_key,
                claim_domain=request.claim_domain,
                consequence_tier=request.consequence_tier,
                should_verify=False,
                suppression_reason="UNCONSENTED_PERSONAL_VERIFICATION",
                target_scope=VerificationScope.UNMATCHED,
                urgency=request.urgency,
                privacy_scope=VerificationPrivacyScope.FORBIDDEN_PRIVATE,
                allowed_authorities=(),
                allowed_source_kinds=(),
                cost_budget=VerificationCostBudget(max_queries=1, timeout_seconds=5),
                quiet_hours_behavior=QuietHoursBehavior.SUPPRESS_TERMINAL,
                policy_rule_id="VPOL-001-PRIVACY-CONSENT",
                rationale="Personal reality verification rejected: user consent not granted (Rule 18).",
                evaluated_at=now,
            )

        # ----------------------------------------------------------------------
        # Guard 2: Per-Turn Rate Limit Budget (AGENTS.md Rule 17)
        # ----------------------------------------------------------------------
        if context.turn_verification_budget_remaining <= 0:
            return VerificationDecision(
                decision_id=effective_decision_id,
                request_id=request.request_id,
                claim_key=request.claim_key,
                claim_domain=request.claim_domain,
                consequence_tier=request.consequence_tier,
                should_verify=False,
                suppression_reason="TURN_BUDGET_EXHAUSTED",
                target_scope=VerificationScope.UNMATCHED,
                urgency=request.urgency,
                privacy_scope=VerificationPrivacyScope.PUBLIC_DATA_ONLY,
                allowed_authorities=(),
                allowed_source_kinds=(),
                cost_budget=VerificationCostBudget(max_queries=1, timeout_seconds=5),
                quiet_hours_behavior=QuietHoursBehavior.SUPPRESS_TERMINAL,
                policy_rule_id="VPOL-002-TURN-BUDGET",
                rationale="Verification request suppressed: per-turn verification quota exhausted.",
                evaluated_at=now,
            )

        # ----------------------------------------------------------------------
        # Guard 3: Daily Rate Limit Budget (AGENTS.md Rule 17)
        # ----------------------------------------------------------------------
        if context.daily_verification_count >= context.daily_verification_cap:
            return VerificationDecision(
                decision_id=effective_decision_id,
                request_id=request.request_id,
                claim_key=request.claim_key,
                claim_domain=request.claim_domain,
                consequence_tier=request.consequence_tier,
                should_verify=False,
                suppression_reason="DAILY_CAP_EXCEEDED",
                target_scope=VerificationScope.UNMATCHED,
                urgency=request.urgency,
                privacy_scope=VerificationPrivacyScope.PUBLIC_DATA_ONLY,
                allowed_authorities=(),
                allowed_source_kinds=(),
                cost_budget=VerificationCostBudget(max_queries=1, timeout_seconds=5),
                quiet_hours_behavior=QuietHoursBehavior.SUPPRESS_TERMINAL,
                policy_rule_id="VPOL-003-DAILY-CAP",
                rationale="Verification request suppressed: daily total verification quota exceeded.",
                evaluated_at=now,
            )

        # ----------------------------------------------------------------------
        # Guard 4: Quiet Hours Gating (AGENTS.md Rule 17)
        # Low/Medium urgency or consequence deferred; High/Critical allowed silent background.
        # ----------------------------------------------------------------------
        quiet_behavior = QuietHoursBehavior.PROCEED_SILENT_BACKGROUND
        if context.is_quiet_hours:
            if request.consequence_tier in (ConsequenceTier.LOW, ConsequenceTier.MEDIUM):
                return VerificationDecision(
                    decision_id=effective_decision_id,
                    request_id=request.request_id,
                    claim_key=request.claim_key,
                    claim_domain=request.claim_domain,
                    consequence_tier=request.consequence_tier,
                    should_verify=False,
                    suppression_reason="QUIET_HOURS_DEFERRED",
                    target_scope=VerificationScope.UNMATCHED,
                    urgency=VerificationUrgency.SCHEDULED_OFFLINE,
                    privacy_scope=VerificationPrivacyScope.PUBLIC_DATA_ONLY,
                    allowed_authorities=(),
                    allowed_source_kinds=(),
                    cost_budget=VerificationCostBudget(max_queries=1, timeout_seconds=5),
                    quiet_hours_behavior=QuietHoursBehavior.DEFER_UNTIL_ACTIVE_HOURS,
                    policy_rule_id="VPOL-004-QUIET-HOURS-DEFERRED",
                    rationale="Verification deferred: quiet hours active for non-critical claim.",
                    evaluated_at=now,
                )
            # High/Critical allowed strictly as silent background job
            quiet_behavior = QuietHoursBehavior.PROCEED_SILENT_BACKGROUND

        # ----------------------------------------------------------------------
        # Guard 5 & 6: Consequence Tiering & Domain Authority Alignment (Lock 3 & Lock 4)
        # Maps ConsequenceTier and ClaimDomain to permitted authorities and budgets.
        # ----------------------------------------------------------------------
        privacy_scope = (
            VerificationPrivacyScope.FIRST_PARTY_CONSENTED
            if request.claim_domain == ClaimDomain.PERSONAL_REALITY
            else VerificationPrivacyScope.PUBLIC_DATA_ONLY
        )

        allowed_authorities, allowed_source_kinds, target_scope, budget, rule_id = (
            self._resolve_consequence_and_domain_rules(request)
        )

        return VerificationDecision(
            decision_id=effective_decision_id,
            request_id=request.request_id,
            claim_key=request.claim_key,
            claim_domain=request.claim_domain,
            consequence_tier=request.consequence_tier,
            should_verify=True,
            suppression_reason=None,
            target_scope=target_scope,
            urgency=request.urgency,
            privacy_scope=privacy_scope,
            allowed_authorities=allowed_authorities,
            allowed_source_kinds=allowed_source_kinds,
            cost_budget=budget,
            quiet_hours_behavior=quiet_behavior,
            policy_rule_id=rule_id,
            rationale=f"Verification authorized under {request.consequence_tier.value} consequence tier.",
            evaluated_at=now,
        )

    def _resolve_consequence_and_domain_rules(
        self,
        request: VerificationRequest,
    ) -> tuple[
        tuple[SourceAuthority, ...],
        tuple[SourceKind, ...],
        VerificationScope,
        VerificationCostBudget,
        str,
    ]:
        """
        Determines allowed authorities, source kinds, scope, and budget
        based on consequence tier and claim domain.
        """
        tier = request.consequence_tier
        domain = request.claim_domain

        # --- CRITICAL TIER ---
        if tier == ConsequenceTier.CRITICAL:
            budget = VerificationCostBudget(
                max_queries=2,
                timeout_seconds=15,
                rate_limit_class=RateLimitClass.STANDARD,
            )
            if domain == ClaimDomain.WORLD_REALITY:
                authorities = (
                    SourceAuthority.PRIMARY_INSTITUTIONAL,
                    SourceAuthority.OFFICIAL_PUBLIC_RECORD,
                )
                kinds = (
                    SourceKind.INSTITUTIONAL_PORTAL,
                    SourceKind.PUBLIC_REGISTRY,
                )
            else:  # PERSONAL_REALITY
                authorities = (
                    SourceAuthority.FIRST_PARTY_PERSONAL,
                    SourceAuthority.OFFICIAL_PUBLIC_RECORD,
                )
                kinds = (
                    SourceKind.USER_DIALOGUE,
                    SourceKind.PUBLIC_REGISTRY,
                )
            return authorities, kinds, VerificationScope.EXACT_MATCH, budget, "VPOL-005-CRITICAL"

        # --- HIGH TIER ---
        if tier == ConsequenceTier.HIGH:
            budget = VerificationCostBudget(
                max_queries=2,
                timeout_seconds=12,
                rate_limit_class=RateLimitClass.STANDARD,
            )
            if domain == ClaimDomain.WORLD_REALITY:
                authorities = (
                    SourceAuthority.PRIMARY_INSTITUTIONAL,
                    SourceAuthority.OFFICIAL_PUBLIC_RECORD,
                    SourceAuthority.CORROBORATED_SECONDARY,
                )
                kinds = (
                    SourceKind.INSTITUTIONAL_PORTAL,
                    SourceKind.PUBLIC_REGISTRY,
                    SourceKind.WEB_DOCUMENT,
                )
            else:  # PERSONAL_REALITY
                authorities = (
                    SourceAuthority.FIRST_PARTY_PERSONAL,
                    SourceAuthority.CORROBORATED_SECONDARY,
                )
                kinds = (
                    SourceKind.USER_DIALOGUE,
                    SourceKind.PUBLIC_REGISTRY,
                )
            return authorities, kinds, VerificationScope.EXACT_MATCH, budget, "VPOL-005-HIGH"

        # --- MEDIUM TIER ---
        if tier == ConsequenceTier.MEDIUM:
            budget = VerificationCostBudget(
                max_queries=1,
                timeout_seconds=10,
                rate_limit_class=RateLimitClass.STANDARD,
            )
            if domain == ClaimDomain.WORLD_REALITY:
                authorities = (
                    SourceAuthority.PRIMARY_INSTITUTIONAL,
                    SourceAuthority.OFFICIAL_PUBLIC_RECORD,
                    SourceAuthority.CORROBORATED_SECONDARY,
                )
                kinds = (
                    SourceKind.INSTITUTIONAL_PORTAL,
                    SourceKind.PUBLIC_REGISTRY,
                    SourceKind.WEB_DOCUMENT,
                )
            else:  # PERSONAL_REALITY
                authorities = (
                    SourceAuthority.FIRST_PARTY_PERSONAL,
                    SourceAuthority.CORROBORATED_SECONDARY,
                )
                kinds = (
                    SourceKind.USER_DIALOGUE,
                    SourceKind.PUBLIC_REGISTRY,
                )
            return authorities, kinds, VerificationScope.PARTIAL_OVERLAP, budget, "VPOL-005-MEDIUM"

        # --- LOW TIER ---
        budget = VerificationCostBudget(
            max_queries=1,
            timeout_seconds=8,
            rate_limit_class=RateLimitClass.THROTTLED,
        )
        if domain == ClaimDomain.WORLD_REALITY:
            # Low consequence world facts allow unverified external web exploration
            authorities = (
                SourceAuthority.PRIMARY_INSTITUTIONAL,
                SourceAuthority.OFFICIAL_PUBLIC_RECORD,
                SourceAuthority.CORROBORATED_SECONDARY,
                SourceAuthority.UNVERIFIED_EXTERNAL,
            )
            kinds = (
                SourceKind.INSTITUTIONAL_PORTAL,
                SourceKind.PUBLIC_REGISTRY,
                SourceKind.WEB_DOCUMENT,
            )
        else:  # PERSONAL_REALITY
            # Even for LOW consequence, personal reality strictly rejects unverified external web data!
            authorities = (
                SourceAuthority.FIRST_PARTY_PERSONAL,
                SourceAuthority.CORROBORATED_SECONDARY,
            )
            kinds = (
                SourceKind.USER_DIALOGUE,
                SourceKind.SYSTEM_INTERNAL,
            )
        return authorities, kinds, VerificationScope.PARTIAL_OVERLAP, budget, "VPOL-005-LOW"
