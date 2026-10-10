"""
epistemic_source_evaluator.py — Epistemic Source Evaluator & Multi-Factor Assessment

Phase 9.3 Deliverable under Architecture Gate v0.2:
- Evaluates raw ExternalObservation items against VerificationRequest and VerificationDecision.
- Strictly enforces Lock 3 & ADR-020: Authority Precedence != Epistemic Truth.
    - Authority rank is a deterministic conflict-resolution precedence ordering, not a truth score or probability weight.
    - Authority rank may resolve eligible conflicts between admissible observations, but never independently produces SUPPORTED.
- Strictly enforces Authority Cannot Override Scope or Freshness:
    - Official source about X != official evidence about Y.
    - Unmatched scope (wrong programme, wrong jurisdiction, unmatched key) strictly evaluates to OUT_OF_SCOPE.
    - A superseded source cannot dominate a current source regardless of static authority rank.
- Strictly enforces Lock 8: Entity Binding Isolation:
    - External entity match != Aevum match.
    - Observations lacking authenticated entity_binding_anchor are rejected as homonym ambiguities.
    - Identity ambiguity must never be interpreted as factual contradiction (EVAL-004-LOCK8-IDENTITY-BINDING).
- Deterministic conflict resolution without raw majority voting (Issue 3 / ADR-020.3):
    - Higher authority rank dominates lower authority rank (subject to freshness guard).
    - More recent freshness dominates outdated/superseded records.
    - Unresolvable symmetrical conflicts strictly evaluate to AMBIGUOUS_CONFLICT.
- Zero float confidence scores; all states and scopes are discrete categorical enums.
- Outputs immutable VerificationFinding; zero mutation authority, zero in-process Evidence creation.

Zero network calls, zero database writes, zero LLM dependencies, zero mutation authority.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Sequence
from uuid import uuid4

from app.reality.verification_models import (
    ClaimDomain,
    SourceAuthority,
    ClaimEpistemicStatus,
    VerificationScope,
    EvidenceFreshness,
    ExternalObservation,
    VerificationRequest,
    VerificationEvaluationProvenance,
    VerificationFinding,
)
from app.reality.verification_policy_engine import VerificationDecision


class IdentityBindingEvaluation(str, Enum):
    """Categorical evaluation of identity alignment for personal claims (Lock 8)."""
    AUTHENTICATED_MATCH = "AUTHENTICATED_MATCH"    # Explicit anchor match verified
    UNANCHORED_HOMONYM = "UNANCHORED_HOMONYM"      # Surface name match without verified identity anchor
    EXPLICIT_MISMATCH = "EXPLICIT_MISMATCH"        # Entity is demonstrably someone else
    NOT_APPLICABLE = "NOT_APPLICABLE"              # World reality claims


# Discrete categorical ranking for deterministic conflict resolution
_AUTHORITY_RANK: dict[SourceAuthority, int] = {
    SourceAuthority.PRIMARY_INSTITUTIONAL: 4,
    SourceAuthority.OFFICIAL_PUBLIC_RECORD: 4,
    SourceAuthority.FIRST_PARTY_PERSONAL: 4,
    SourceAuthority.CORROBORATED_SECONDARY: 2,
    SourceAuthority.UNVERIFIED_EXTERNAL: 1,
}

_FRESHNESS_RANK: dict[EvidenceFreshness, int] = {
    EvidenceFreshness.CURRENT: 3,
    EvidenceFreshness.HISTORICAL_RECORD: 2,
    EvidenceFreshness.SUPERSEDED_OUTDATED: 1,
    EvidenceFreshness.UNDETERMINED: 0,
}


class EpistemicSourceEvaluator:
    """
    Deterministic Epistemic Evaluator for External Observations.

    Transforms collections of ExternalObservation items into an immutable VerificationFinding.
    Never alters character state, never invokes set_fact().
    """

    def __init__(self, evaluator_version: str = "1.0.0") -> None:
        self._version = evaluator_version

    def evaluate_observations(
        self,
        request: VerificationRequest,
        decision: VerificationDecision,
        observations: Sequence[ExternalObservation],
        finding_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> VerificationFinding:
        """
        Evaluate external observations against the request and policy constraints.
        Pure deterministic computation.
        """
        eval_time = now or datetime.now(timezone.utc)
        effective_finding_id = finding_id or f"find-{uuid4().hex[:12]}"

        # ----------------------------------------------------------------------
        # Step 1: Pre-condition Gating
        # ----------------------------------------------------------------------
        if not decision.should_verify:
            provenance = VerificationEvaluationProvenance(
                evaluator_name="EpistemicSourceEvaluator",
                evaluator_version=self._version,
                evaluated_at=eval_time,
                rule_ids_applied=("EVAL-001-POLICY-SUPPRESSED",),
                rationale=f"Verification not authorized by policy: {decision.suppression_reason or 'Suppressed'}.",
            )
            return VerificationFinding(
                finding_id=effective_finding_id,
                request_id=request.request_id,
                claim_domain=request.claim_domain,
                claim_key=request.claim_key,
                epistemic_status=ClaimEpistemicStatus.INSUFFICIENT_EVIDENCE,
                scope=VerificationScope.UNMATCHED,
                freshness=EvidenceFreshness.UNDETERMINED,
                contributing_observation_ids=(),
                provenance=provenance,
                contradiction_details=None,
            )

        if not observations:
            provenance = VerificationEvaluationProvenance(
                evaluator_name="EpistemicSourceEvaluator",
                evaluator_version=self._version,
                evaluated_at=eval_time,
                rule_ids_applied=("EVAL-002-NO-OBSERVATIONS",),
                rationale="No external observations available for claim.",
            )
            return VerificationFinding(
                finding_id=effective_finding_id,
                request_id=request.request_id,
                claim_domain=request.claim_domain,
                claim_key=request.claim_key,
                epistemic_status=ClaimEpistemicStatus.INSUFFICIENT_EVIDENCE,
                scope=VerificationScope.UNMATCHED,
                freshness=EvidenceFreshness.UNDETERMINED,
                contributing_observation_ids=(),
                provenance=provenance,
                contradiction_details=None,
            )

        # ----------------------------------------------------------------------
        # Step 2: Policy Compliance Filtering
        # Observations not conforming to policy constraints are discarded.
        # ----------------------------------------------------------------------
        valid_observations: list[ExternalObservation] = []
        for obs in observations:
            auth = obs.source_provenance.source_authority
            kind = obs.source_provenance.source_kind
            if auth in decision.allowed_authorities and kind in decision.allowed_source_kinds:
                valid_observations.append(obs)

        if not valid_observations:
            provenance = VerificationEvaluationProvenance(
                evaluator_name="EpistemicSourceEvaluator",
                evaluator_version=self._version,
                evaluated_at=eval_time,
                rule_ids_applied=("EVAL-003-AUTHORITY-FILTERED",),
                rationale="All observations were discarded due to policy authority or source kind restrictions.",
            )
            return VerificationFinding(
                finding_id=effective_finding_id,
                request_id=request.request_id,
                claim_domain=request.claim_domain,
                claim_key=request.claim_key,
                epistemic_status=ClaimEpistemicStatus.INSUFFICIENT_EVIDENCE,
                scope=VerificationScope.UNMATCHED,
                freshness=EvidenceFreshness.UNDETERMINED,
                contributing_observation_ids=(),
                provenance=provenance,
                contradiction_details=None,
            )

        # ----------------------------------------------------------------------
        # Step 3: Identity Binding Gate (Lock 8 & Issue 6)
        # External entity match != Aevum match.
        # ----------------------------------------------------------------------
        if request.claim_domain == ClaimDomain.PERSONAL_REALITY:
            authenticated_observations: list[ExternalObservation] = []
            has_unanchored_homonym = False

            for obs in valid_observations:
                binding = self._evaluate_identity_binding(request, obs)
                if binding == IdentityBindingEvaluation.AUTHENTICATED_MATCH:
                    authenticated_observations.append(obs)
                elif binding == IdentityBindingEvaluation.UNANCHORED_HOMONYM:
                    has_unanchored_homonym = True

            if not authenticated_observations:
                rationale = (
                    "Lock 8 Rejection: Unanchored external entity homonym detected. "
                    "External name matching alone does not establish personal identity binding. "
                    "Identity ambiguity must never be interpreted as factual contradiction."
                    if has_unanchored_homonym
                    else "No observations matched the authenticated personal identity anchor."
                )
                provenance = VerificationEvaluationProvenance(
                    evaluator_name="EpistemicSourceEvaluator",
                    evaluator_version=self._version,
                    evaluated_at=eval_time,
                    rule_ids_applied=("EVAL-004-LOCK8-IDENTITY-BINDING",),
                    rationale=rationale,
                )
                status = (
                    ClaimEpistemicStatus.AMBIGUOUS_CONFLICT
                    if has_unanchored_homonym
                    else ClaimEpistemicStatus.INSUFFICIENT_EVIDENCE
                )
                return VerificationFinding(
                    finding_id=effective_finding_id,
                    request_id=request.request_id,
                    claim_domain=request.claim_domain,
                    claim_key=request.claim_key,
                    epistemic_status=status,
                    scope=VerificationScope.UNMATCHED,
                    freshness=EvidenceFreshness.UNDETERMINED,
                    contributing_observation_ids=tuple(obs.observation_id for obs in valid_observations),
                    provenance=provenance,
                    contradiction_details=(
                        "Identity binding unresolved: external entity matches name but lacks authenticated anchor "
                        "(Identity ambiguity != factual contradiction)."
                        if has_unanchored_homonym
                        else None
                    ),
                )

            valid_observations = authenticated_observations

        # ----------------------------------------------------------------------
        # Step 4: Multi-Factor Alignment & Categorical Separation
        # Classify observations into supporting vs. contradicting.
        # ----------------------------------------------------------------------
        supporting: list[ExternalObservation] = []
        contradicting: list[ExternalObservation] = []
        applicable_ids: list[str] = []

        for obs in valid_observations:
            applicable_ids.append(obs.observation_id)
            alignment = self._evaluate_claim_alignment(request, obs)
            if alignment is True:
                supporting.append(obs)
            elif alignment is False:
                contradicting.append(obs)

        if not supporting and not contradicting:
            provenance = VerificationEvaluationProvenance(
                evaluator_name="EpistemicSourceEvaluator",
                evaluator_version=self._version,
                evaluated_at=eval_time,
                rule_ids_applied=("EVAL-005-OUT-OF-SCOPE",),
                rationale="Observations did not contain relevant factual claims regarding the asserted key.",
            )
            return VerificationFinding(
                finding_id=effective_finding_id,
                request_id=request.request_id,
                claim_domain=request.claim_domain,
                claim_key=request.claim_key,
                epistemic_status=ClaimEpistemicStatus.OUT_OF_SCOPE,
                scope=VerificationScope.UNMATCHED,
                freshness=EvidenceFreshness.UNDETERMINED,
                contributing_observation_ids=tuple(applicable_ids),
                provenance=provenance,
                contradiction_details=None,
            )

        # ----------------------------------------------------------------------
        # Step 5: Deterministic Conflict Resolution (Issue 3 / ADR-020.3)
        # ----------------------------------------------------------------------
        # Case A: Pure Supporting Evidence
        if supporting and not contradicting:
            scope = self._resolve_scope(supporting)
            freshness = self._resolve_freshness(supporting)
            provenance = VerificationEvaluationProvenance(
                evaluator_name="EpistemicSourceEvaluator",
                evaluator_version=self._version,
                evaluated_at=eval_time,
                rule_ids_applied=("EVAL-006-SUPPORTED-CONSISTENT",),
                rationale=f"Claim is supported by {len(supporting)} consistent observation(s) under {decision.target_scope.value} scope requirements.",
            )
            return VerificationFinding(
                finding_id=effective_finding_id,
                request_id=request.request_id,
                claim_domain=request.claim_domain,
                claim_key=request.claim_key,
                epistemic_status=ClaimEpistemicStatus.SUPPORTED,
                scope=scope,
                freshness=freshness,
                contributing_observation_ids=tuple(applicable_ids),
                provenance=provenance,
                contradiction_details=None,
            )

        # Case B: Pure Contradicting Evidence
        if contradicting and not supporting:
            scope = self._resolve_scope(contradicting)
            freshness = self._resolve_freshness(contradicting)
            details = self._format_contradiction_details(request, contradicting)
            provenance = VerificationEvaluationProvenance(
                evaluator_name="EpistemicSourceEvaluator",
                evaluator_version=self._version,
                evaluated_at=eval_time,
                rule_ids_applied=("EVAL-007-CONTRADICTED-CONSISTENT",),
                rationale=f"Claim is contradicted by {len(contradicting)} consistent external observation(s).",
            )
            return VerificationFinding(
                finding_id=effective_finding_id,
                request_id=request.request_id,
                claim_domain=request.claim_domain,
                claim_key=request.claim_key,
                epistemic_status=ClaimEpistemicStatus.CONTRADICTED,
                scope=scope,
                freshness=freshness,
                contributing_observation_ids=tuple(applicable_ids),
                provenance=provenance,
                contradiction_details=details,
            )

        # Case C: Conflicting Evidence (Deterministic Hierarchical Arbitration)
        max_supp_auth = max(_AUTHORITY_RANK.get(o.source_provenance.source_authority, 0) for o in supporting)
        max_cont_auth = max(_AUTHORITY_RANK.get(o.source_provenance.source_authority, 0) for o in contradicting)

        # Freshness determination across sides
        max_supp_fresh = max(_FRESHNESS_RANK.get(self._get_obs_freshness(o), 0) for o in supporting)
        max_cont_fresh = max(_FRESHNESS_RANK.get(self._get_obs_freshness(o), 0) for o in contradicting)
        supp_is_all_superseded = all(self._get_obs_freshness(o) == EvidenceFreshness.SUPERSEDED_OUTDATED for o in supporting)
        cont_is_all_superseded = all(self._get_obs_freshness(o) == EvidenceFreshness.SUPERSEDED_OUTDATED for o in contradicting)
        supp_has_current = any(self._get_obs_freshness(o) == EvidenceFreshness.CURRENT for o in supporting)
        cont_has_current = any(self._get_obs_freshness(o) == EvidenceFreshness.CURRENT for o in contradicting)

        # Rule C.1: Authority Dominance (Subject to Freshness Guard)
        # Authority precedence resolves conflict ONLY when the higher authority source is not superseded by a current source
        if max_supp_auth > max_cont_auth and not (supp_is_all_superseded and cont_has_current):
            scope = self._resolve_scope(supporting)
            freshness = self._resolve_freshness(supporting)
            provenance = VerificationEvaluationProvenance(
                evaluator_name="EpistemicSourceEvaluator",
                evaluator_version=self._version,
                evaluated_at=eval_time,
                rule_ids_applied=("EVAL-008-AUTHORITY-DOMINANCE-SUPPORT",),
                rationale="Conflict resolved: higher source authority supporting claim dominates lower authority contradiction.",
            )
            return VerificationFinding(
                finding_id=effective_finding_id,
                request_id=request.request_id,
                claim_domain=request.claim_domain,
                claim_key=request.claim_key,
                epistemic_status=ClaimEpistemicStatus.SUPPORTED,
                scope=scope,
                freshness=freshness,
                contributing_observation_ids=tuple(applicable_ids),
                provenance=provenance,
                contradiction_details=None,
            )

        if max_cont_auth > max_supp_auth and not (cont_is_all_superseded and supp_has_current):
            scope = self._resolve_scope(contradicting)
            freshness = self._resolve_freshness(contradicting)
            details = self._format_contradiction_details(request, contradicting)
            provenance = VerificationEvaluationProvenance(
                evaluator_name="EpistemicSourceEvaluator",
                evaluator_version=self._version,
                evaluated_at=eval_time,
                rule_ids_applied=("EVAL-008-AUTHORITY-DOMINANCE-CONTRADICT",),
                rationale="Conflict resolved: higher source authority contradiction dominates lower authority claim.",
            )
            return VerificationFinding(
                finding_id=effective_finding_id,
                request_id=request.request_id,
                claim_domain=request.claim_domain,
                claim_key=request.claim_key,
                epistemic_status=ClaimEpistemicStatus.CONTRADICTED,
                scope=scope,
                freshness=freshness,
                contributing_observation_ids=tuple(applicable_ids),
                provenance=provenance,
                contradiction_details=details,
            )

        # Rule C.2: Freshness Dominance (Authorities are Equal, or Higher Authority is Superseded by Current)
        if max_supp_fresh > max_cont_fresh:
            scope = self._resolve_scope(supporting)
            freshness = self._resolve_freshness(supporting)
            provenance = VerificationEvaluationProvenance(
                evaluator_name="EpistemicSourceEvaluator",
                evaluator_version=self._version,
                evaluated_at=eval_time,
                rule_ids_applied=("EVAL-009-FRESHNESS-DOMINANCE-SUPPORT",),
                rationale="Conflict resolved: more recent active evidence supporting claim dominates outdated record.",
            )
            return VerificationFinding(
                finding_id=effective_finding_id,
                request_id=request.request_id,
                claim_domain=request.claim_domain,
                claim_key=request.claim_key,
                epistemic_status=ClaimEpistemicStatus.SUPPORTED,
                scope=scope,
                freshness=freshness,
                contributing_observation_ids=tuple(applicable_ids),
                provenance=provenance,
                contradiction_details=None,
            )

        if max_cont_fresh > max_supp_fresh:
            scope = self._resolve_scope(contradicting)
            freshness = self._resolve_freshness(contradicting)
            details = self._format_contradiction_details(request, contradicting)
            provenance = VerificationEvaluationProvenance(
                evaluator_name="EpistemicSourceEvaluator",
                evaluator_version=self._version,
                evaluated_at=eval_time,
                rule_ids_applied=("EVAL-009-FRESHNESS-DOMINANCE-CONTRADICT",),
                rationale="Conflict resolved: more recent active evidence contradicting claim dominates outdated record.",
            )
            return VerificationFinding(
                finding_id=effective_finding_id,
                request_id=request.request_id,
                claim_domain=request.claim_domain,
                claim_key=request.claim_key,
                epistemic_status=ClaimEpistemicStatus.CONTRADICTED,
                scope=scope,
                freshness=freshness,
                contributing_observation_ids=tuple(applicable_ids),
                provenance=provenance,
                contradiction_details=details,
            )

        # Rule C.3: Irresolvable Conflict (Equal Authority & Equal Freshness)
        # Lock 3 / Issue 3: Zero majority voting. Strictly evaluates to AMBIGUOUS_CONFLICT.
        scope = VerificationScope.PARTIAL_OVERLAP
        freshness = self._resolve_freshness(valid_observations)
        details = (
            f"Unresolved conflict: {len(supporting)} supporting and {len(contradicting)} contradicting "
            "observation(s) share identical authority tier and freshness. Zero majority voting applied."
        )
        provenance = VerificationEvaluationProvenance(
            evaluator_name="EpistemicSourceEvaluator",
            evaluator_version=self._version,
            evaluated_at=eval_time,
            rule_ids_applied=("EVAL-010-IRRESOLVABLE-CONFLICT-AMBIGUOUS",),
            rationale="Deterministic conflict resolution: equal-standing contradictory sources cannot be arbitrated without further evidence.",
        )
        return VerificationFinding(
            finding_id=effective_finding_id,
            request_id=request.request_id,
            claim_domain=request.claim_domain,
            claim_key=request.claim_key,
            epistemic_status=ClaimEpistemicStatus.AMBIGUOUS_CONFLICT,
            scope=scope,
            freshness=freshness,
            contributing_observation_ids=tuple(applicable_ids),
            provenance=provenance,
            contradiction_details=details,
        )

    # --------------------------------------------------------------------------
    # Helper Methods
    # --------------------------------------------------------------------------

    def _evaluate_identity_binding(
        self,
        request: VerificationRequest,
        obs: ExternalObservation,
    ) -> IdentityBindingEvaluation:
        """
        Enforce Lock 8:
        Verify whether the observation contains authenticated binding to the entity anchor.
        """
        if not request.entity_binding_anchor:
            return IdentityBindingEvaluation.EXPLICIT_MISMATCH

        anchor = request.entity_binding_anchor

        # Check structured payload for explicit binding anchor
        payload_anchor = obs.structured_payload.get("entity_binding_anchor")
        if payload_anchor == anchor:
            return IdentityBindingEvaluation.AUTHENTICATED_MATCH

        # Check snippet for explicit anchor reference
        if f"anchor:{anchor}" in obs.observed_content_snippet or anchor in obs.observed_content_snippet:
            return IdentityBindingEvaluation.AUTHENTICATED_MATCH

        # If entity name exists but lacks anchor -> homonym ambiguity!
        if obs.observed_entity_name:
            return IdentityBindingEvaluation.UNANCHORED_HOMONYM

        return IdentityBindingEvaluation.EXPLICIT_MISMATCH

    def _evaluate_claim_alignment(
        self,
        request: VerificationRequest,
        obs: ExternalObservation,
    ) -> Optional[bool]:
        """
        Determines if observation supports (True), contradicts (False),
        or is irrelevant (None) to the claim.
        """
        # If the observation explicitly targets a different claim key, it is out-of-scope / irrelevant
        payload_key = obs.structured_payload.get("key") or obs.structured_payload.get("claim_key")
        if payload_key is not None and payload_key != request.claim_key:
            return None

        # Check explicit scope marker in payload
        obs_scope = obs.structured_payload.get("scope")
        if obs_scope in (VerificationScope.UNMATCHED.value, VerificationScope.UNMATCHED, "OUT_OF_SCOPE"):
            return None

        # Scope qualifier: jurisdiction alignment
        obs_jurisdiction = obs.structured_payload.get("jurisdiction")
        target_jurisdiction = obs.structured_payload.get("target_jurisdiction")
        if obs_jurisdiction is not None:
            if target_jurisdiction is not None and str(obs_jurisdiction).strip().lower() != str(target_jurisdiction).strip().lower():
                return None
            key_lower = request.claim_key.lower()
            if any(k in key_lower for k in ("usm", "malaysia", "penang")):
                if str(obs_jurisdiction).strip().lower() not in ("my", "malaysia", "penang"):
                    return None

        # Scope qualifier: programme / academic pathway alignment
        obs_programme = obs.structured_payload.get("programme")
        target_programme = obs.structured_payload.get("target_programme")
        if obs_programme is not None:
            if target_programme is not None and str(obs_programme).strip().lower() != str(target_programme).strip().lower():
                return None
            key_parts = request.claim_key.lower().split(".")
            obs_prog_lower = str(obs_programme).strip().lower()
            for prog_keyword in ("cs", "computer_science", "engineering", "medicine", "law", "arts", "business"):
                if prog_keyword in key_parts and prog_keyword not in obs_prog_lower:
                    return None

        obs_val = obs.structured_payload.get("value")
        if obs_val is not None:
            return obs_val == request.claim_value

        # Check explicit negation/alternative in structured payload
        alt_val = obs.structured_payload.get("alternative_value")
        if alt_val is not None and alt_val != request.claim_value:
            return False

        # Check snippet alignment
        asserted_str = str(request.claim_value).lower()
        snippet_lower = obs.observed_content_snippet.lower()

        if asserted_str in snippet_lower:
            return True

        return None

    def _resolve_scope(self, observations: Sequence[ExternalObservation]) -> VerificationScope:
        for obs in observations:
            obs_scope = obs.structured_payload.get("scope")
            if obs_scope:
                try:
                    return VerificationScope(obs_scope)
                except ValueError:
                    pass
        return VerificationScope.EXACT_MATCH if observations else VerificationScope.UNMATCHED

    def _get_obs_freshness(self, obs: ExternalObservation) -> EvidenceFreshness:
        freshness_val = obs.structured_payload.get("freshness")
        if freshness_val:
            try:
                return EvidenceFreshness(freshness_val)
            except ValueError:
                pass
        return EvidenceFreshness.CURRENT

    def _resolve_freshness(self, observations: Sequence[ExternalObservation]) -> EvidenceFreshness:
        if not observations:
            return EvidenceFreshness.UNDETERMINED
        # Return best freshness
        return max(
            (self._get_obs_freshness(o) for o in observations),
            key=lambda f: _FRESHNESS_RANK.get(f, 0)
        )

    def _format_contradiction_details(
        self,
        request: VerificationRequest,
        contradicting_obs: Sequence[ExternalObservation],
    ) -> str:
        alt_values = [
            str(o.structured_payload.get("value") or o.structured_payload.get("alternative_value") or o.observed_content_snippet)
            for o in contradicting_obs
        ]
        return (
            f"Observed external value(s) [{', '.join(alt_values[:2])}] "
            f"contradict asserted claim value '{request.claim_value}'."
        )
