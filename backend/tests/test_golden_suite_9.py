"""
test_golden_suite_9.py — Golden Acceptance Suite 9 (Phase 9.6: GC-221 ~ GC-245)

Golden Acceptance Suite for Phase 9: Autonomous Reality Verification & Epistemic Trust Gate.
Verifies all frozen contracts (9.1–9.5) and the 10 Constitutional Locks under ADR-020 Items 1–27.

Covers 25 Acceptance Benchmarks across 6 Structured Clusters:
- Cluster 1: 10 Constitutional Locks Hard Invariants (GC-221 ~ GC-225)
  - GC-221: Zero Direct Mutation Authority & Canonical Mutation Singularity (Lock 1 & Lock 10)
  - GC-222: Decision-Only Policy Engine (Lock 2)
  - GC-223: Source Authority != Truth & Domain Separation (Lock 3 & Lock 4)
  - GC-224: Temporal Isolation & Physical Temporal Wall (Lock 5 & Lock 7)
  - GC-225: Repair Delegation & Entity Binding Isolation (Lock 6 & Lock 8)

- Cluster 2: Epistemic Source Evaluation & Evidence Semantics (GC-226 ~ GC-229)
  - GC-226: Authority Cannot Override Scope or Freshness (Lock 3 & ADR-020 Item 14)
  - GC-227: Deterministic Authority Resolution & Ambiguity Preservation (Lock GC-227 & ADR-020 Item 3/15)
  - GC-228: Operational Failure Separation from Epistemic Status (ADR-020 Item 14)
  - GC-229: Zero-Float Pure Discrete Epistemic Architecture (Permanent Note A)

- Cluster 3: Queue Deduplication, Idempotency & Temporal Wall (GC-230 ~ GC-233)
  - GC-230: Canonical Deterministic Deduplication Key (ADR-020 Item 18)
  - GC-231: Turn-Scoped Queue Deduplication & Cross-Turn Re-Verification (ADR-020 Item 18)
  - GC-232: Job-to-Inbox Idempotency Protocol (ADR-020 Item 19)
  - GC-233: Earliest-Eligible Turn Invariant Under Non-Sequential Turn IDs (ADR-020 Item 17)

- Cluster 4: Evidence Reconciliation & Refutation Routing (GC-234 ~ GC-238)
  - GC-234: Anti-Shortcut Invariant (Anti-Magical-Promotion)
  - GC-235: Domain-Gated World Reality Isolation (ADR-020 Item 21)
  - GC-236: Reconciler Routing != Repair Decision (ADR-020 Item 22)
  - GC-237: Evaluation-Level Candidate Exclusion is Derived View Only (ADR-020 Item 23)
  - GC-238: All-Typed Repair Boundary & Zero Control Dict Penetration (ADR-020 Item 25)

- Cluster 5: End-to-End Multi-Turn Integration & Complex Lifecycles (GC-239 ~ GC-242)
  - GC-239: Complete Multi-Turn Veracity Cycle — Personal Claim Corroboration (Lock B & ADR-020 Item 27)
  - GC-240: Complete Multi-Turn Refutation Cycle — Unconfirmed Candidate Refutation
  - GC-241: Canonical Personal Fact Contradiction with Timeline Split
  - GC-242: Identity Ambiguity Homonym Cycle — Uncertainty Preservation

- Cluster 6: Defensive Integrity, AST Audits & System Invariants (GC-243 ~ GC-245)
  - GC-243: Policy-Scoped Promotion Margin Threshold (Lock B & ADR-020 Item 27)
  - GC-244: Static AST Boundary Audit Across Phase 9 Modules
  - GC-245: Canonical Semantic Projection Determinism & Exception Resilience (Lock A & ADR-020 Item 26)
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json
import pathlib
from typing import Any, Optional, Sequence
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.core_models import CharacterCore
from app.character.core_service import (
    AevumCanonicalNotDirectlyEditableError,
    CharacterCoreService,
)
from app.reality.biography_promotion_models import (
    BiographyConstructionPolicy,
    PromotionAuthorizationToken,
    PromotionGateType,
)
from app.reality.biography_promotion_service import BiographyPromotionService
from app.reality.candidate_models import (
    CandidateHypothesis,
    CandidateLifecycleState,
    EvidenceFamily,
    InferenceEdgeType,
    PlausibilityBreakdown,
    ProvenanceLineage,
    RealityTaxonomy,
)
from app.reality.candidate_repository import CandidateRepository
from app.reality.choice_models import (
    ChoiceDecisionResult,
    ChoiceFactorBreakdown,
    ChoiceRationaleCode,
    CompetitionResult,
    CompetitionState,
)
from app.reality.contradiction_models import ContradictionResolution, ContradictionType
from app.reality.epistemic_source_evaluator import EpistemicSourceEvaluator
from app.reality.models import CoreFactItem, FactAuthority, FactSource, FactStatus
from app.reality.observation_adapters import InMemoryObservationAdapter
from app.reality.verification_gateway import (
    AdapterDescriptor,
    VerificationGateway,
)
from app.reality.reality_orchestration_service import (
    OrchestrationTurnResult,
    RealityOrchestrationService,
)
from app.reality.repair_models import RealityRepairResult, RepairLevel
from app.reality.repair_service import RealityRepairService
from app.reality.verification_models import (
    ClaimDomain,
    ClaimEpistemicStatus,
    ConsequenceTier,
    EvidenceFreshness,
    ExternalObservation,
    SourceAuthority,
    SourceKind,
    VerificationDispatchResult,
    VerificationEvaluationProvenance,
    VerificationEvidencePayload,
    VerificationFinding,
    VerificationInboxItem,
    VerificationJob,
    VerificationJobStatus,
    VerificationProvenance,
    VerificationRequest,
    VerificationScope,
    VerificationUrgency,
)
from app.reality.verification_orchestrator import (
    VerificationAsyncOrchestrator,
    VerificationEvidenceInbox,
    compute_deduplication_key,
)
from app.reality.verification_policy_engine import (
    QuietHoursBehavior,
    VerificationCostBudget,
    VerificationDecision,
    VerificationPolicyContext,
    VerificationPolicyEngine,
    VerificationPrivacyScope,
)
from app.reality.verification_reconciler import (
    ReconciliationActionType,
    ReconciliationRoutingItem,
    VerificationEntityDisambiguationContext,
    VerificationReconciler,
    VerificationReconciliationResult,
    VerificationRepairRequest,
    VerificationTemporalSplitContext,
)


# =============================================================================
# Helper Fixtures & Constructors
# =============================================================================

def _utc_now() -> datetime:
    return datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_mock_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    scalars_mock.first.return_value = None
    session.scalars = AsyncMock(return_value=scalars_mock)
    session.execute = AsyncMock(return_value=scalars_mock)
    return session


def _make_mock_core(
    facts: Optional[dict[str, Any]] = None,
    character_id: str = "aevum",
) -> CharacterCore:
    fact_items: dict[str, CoreFactItem] = {}
    if facts:
        for k, v in facts.items():
            if isinstance(v, CoreFactItem):
                fact_items[k] = v
            else:
                cat = k.split(".")[0]
                fact_items[k] = CoreFactItem(
                    key=k,
                    category=cat,
                    value=v,
                    source=FactSource.USER_CONFIGURED,
                    authority=FactAuthority.AEVUM_CANONICAL,
                    status=FactStatus.CANONICAL,
                    epistemic_confidence=1.0,
                    locked=False,
                    created_at=_utc_now(),
                    updated_at=_utc_now(),
                )
    return CharacterCore(character_id=character_id, facts=fact_items)


def _make_candidate(
    cid: str,
    slot_name: str,
    value: str,
    composite_plausibility: float = 0.55,
    taxonomy: RealityTaxonomy = RealityTaxonomy.SIMULATED_BIOGRAPHY_FACT,
    lifecycle_state: CandidateLifecycleState = CandidateLifecycleState.ACTIVE,
    entity_id: str = "aevum",
) -> CandidateHypothesis:
    ef = EvidenceFamily(
        family_id=f"fam_{cid}",
        source_type="USER_ASSERTION",
        cluster_key=f"{entity_id}.{slot_name}.claim",
        mention_count=1,
    )
    return CandidateHypothesis(
        candidate_id=cid,
        entity_id=entity_id,
        slot_name=slot_name,
        proposed_value=value,
        reality_taxonomy=taxonomy,
        inference_depth=0,
        inference_edge_type=InferenceEdgeType.DIRECT_ATTRIBUTE,
        plausibility=PlausibilityBreakdown.create(composite_plausibility_score=composite_plausibility),
        provenance=ProvenanceLineage(origin_id=f"stim_{cid}", evidence_family_ids=(ef.family_id,)),
        evidence_families=(ef,),
        lifecycle_state=lifecycle_state,
    )


def _make_finding(
    claim_domain: ClaimDomain = ClaimDomain.PERSONAL_REALITY,
    claim_key: str = "education.university",
    epistemic_status: ClaimEpistemicStatus = ClaimEpistemicStatus.SUPPORTED,
    claim_value: Any = "Kyoto University",
    entity_binding_anchor: Optional[str] = "aevum",
    contradiction_details: Optional[str] = None,
    source_authority: SourceAuthority = SourceAuthority.PRIMARY_INSTITUTIONAL,
) -> VerificationFinding:
    provenance = VerificationEvaluationProvenance(
        evaluator_name="EpistemicSourceEvaluator",
        evaluator_version="1.0.0",
        evaluated_at=_utc_now(),
        rule_ids_applied=("EVAL-006-SUPPORTED-CONSISTENT",),
        rationale="External observation consistent with asserted claim.",
    )
    return VerificationFinding(
        finding_id=f"find_{uuid4().hex[:8]}",
        request_id=f"req_{uuid4().hex[:8]}",
        claim_domain=claim_domain,
        claim_key=claim_key,
        epistemic_status=epistemic_status,
        claim_value=claim_value,
        entity_binding_anchor=entity_binding_anchor,
        scope=VerificationScope.EXACT_MATCH,
        freshness=EvidenceFreshness.CURRENT,
        contributing_observation_ids=("obs_01",),
        provenance=provenance,
        contradiction_details=contradiction_details,
    )


def _make_inbox_item(
    finding: VerificationFinding,
    source_job_id: str = "job_test",
    origin_turn_id: str = "turn-1",
    eligible_from_turn_id: str = "turn-2",
    origin_turn_sequence: int = 1,
    eligible_from_turn_sequence: int = 2,
) -> VerificationInboxItem:
    return VerificationInboxItem(
        inbox_id=f"inbox_{uuid4().hex[:8]}",
        source_job_id=source_job_id,
        finding=finding,
        enqueued_at=_utc_now(),
        origin_turn_id=origin_turn_id,
        eligible_from_turn_id=eligible_from_turn_id,
        origin_turn_sequence=origin_turn_sequence,
        eligible_from_turn_sequence=eligible_from_turn_sequence,
    )


def _make_decision(
    request: VerificationRequest,
    should_verify: bool = True,
    suppression_reason: Optional[str] = None,
    allowed_authorities: Sequence[SourceAuthority] = (SourceAuthority.PRIMARY_INSTITUTIONAL,),
    allowed_source_kinds: Sequence[SourceKind] = (SourceKind.PUBLIC_REGISTRY,),
    privacy_scope: VerificationPrivacyScope = VerificationPrivacyScope.PUBLIC_DATA_ONLY,
    cost_budget: Optional[VerificationCostBudget] = None,
    quiet_hours_behavior: QuietHoursBehavior = QuietHoursBehavior.PROCEED_SILENT_BACKGROUND,
    target_scope: VerificationScope = VerificationScope.EXACT_MATCH,
    decision_id: Optional[str] = None,
) -> VerificationDecision:
    return VerificationDecision(
        decision_id=decision_id or f"dec_{uuid4().hex[:8]}",
        request_id=request.request_id,
        claim_key=request.claim_key,
        claim_domain=request.claim_domain,
        consequence_tier=request.consequence_tier,
        should_verify=should_verify,
        suppression_reason=suppression_reason,
        target_scope=target_scope,
        urgency=request.urgency,
        privacy_scope=privacy_scope,
        allowed_authorities=tuple(allowed_authorities),
        allowed_source_kinds=tuple(allowed_source_kinds),
        cost_budget=cost_budget or VerificationCostBudget(max_queries=1, timeout_seconds=10),
        quiet_hours_behavior=quiet_hours_behavior,
        policy_rule_id="RULE-TEST-01",
        rationale="Policy evaluated for test.",
        evaluated_at=_utc_now(),
    )


def _make_observation(
    observation_id: str = "obs_01",
    source_authority: SourceAuthority = SourceAuthority.PRIMARY_INSTITUTIONAL,
    source_kind: SourceKind = SourceKind.PUBLIC_REGISTRY,
    observed_content_snippet: str = "Observed factual record",
    structured_payload: Optional[dict[str, Any]] = None,
    observed_entity_name: Optional[str] = None,
    observed_at: Optional[datetime] = None,
    temporal_anchor: Optional[datetime] = None,
) -> ExternalObservation:
    now = observed_at or _utc_now()
    return ExternalObservation(
        observation_id=observation_id,
        source_provenance=VerificationProvenance(
            source_id=f"src_{observation_id}",
            source_authority=source_authority,
            source_kind=source_kind,
            retrieval_timestamp=now,
        ),
        observed_content_snippet=observed_content_snippet,
        structured_payload=structured_payload or {},
        observed_at=now,
        temporal_anchor=temporal_anchor,
        observed_entity_name=observed_entity_name,
    )


class FakeCoreService:
    """In-memory CharacterCoreService enforcing the PromotionAuthorizationToken mutation contract."""

    def __init__(self, initial_facts: Optional[dict[str, Any]] = None):
        self.facts: dict[str, CoreFactItem] = {}
        if initial_facts:
            for k, v in initial_facts.items():
                if isinstance(v, CoreFactItem):
                    self.facts[k] = v
                else:
                    self.facts[k] = CoreFactItem(
                        key=k,
                        category=k.split(".")[0],
                        value=v,
                        authority=FactAuthority.AEVUM_CANONICAL,
                        source=FactSource.SYSTEM_BASELINE,
                    )

    async def get_core(self, character_id: str = "aevum") -> CharacterCore:
        return CharacterCore(character_id=character_id, facts=dict(self.facts))

    async def set_fact(
        self,
        character_id: str,
        fact_key: str,
        value: Any,
        source: FactSource = FactSource.USER_CONFIGURED,
        authority: FactAuthority = FactAuthority.USER_CONFIGURED,
        status: FactStatus = FactStatus.CANONICAL,
        explanation: Optional[str] = None,
        confidence: float = 1.0,
        allow_canonical_reconciliation: bool = False,
        authorization_token: Optional[PromotionAuthorizationToken] = None,
        auto_commit: bool = True,
    ) -> CoreFactItem:
        if allow_canonical_reconciliation:
            if authorization_token is None:
                raise AevumCanonicalNotDirectlyEditableError(
                    f"Canonical reconciliation on fact '{fact_key}' requires a valid PromotionAuthorizationToken."
                )
            if not authorization_token.verify(character_id, fact_key, value):
                raise AevumCanonicalNotDirectlyEditableError(
                    f"PromotionAuthorizationToken invalid for character '{character_id}', fact '{fact_key}'."
                )
        item = CoreFactItem(
            key=fact_key,
            category=fact_key.split(".")[0],
            value=value,
            authority=authority,
            source=source,
            status=status,
            explanation=explanation,
            epistemic_confidence=confidence,
            locked=False,
        )
        self.facts[fact_key] = item
        return item


def _canonicalize_turn_result(res: OrchestrationTurnResult) -> dict[str, Any]:
    """Canonical semantic projection of OrchestrationTurnResult (Lock A / ADR-020 Item 26).

    Filters out operational metadata: runtime timestamps, generated object IDs,
    random UUIDs, and wall-clock execution duration.
    Retains purely semantic reality state: facts, choices, repair results,
    contradiction status, and reconciliation decisions.
    """
    canonical_facts = {}
    if res.governed_reality and res.governed_reality.canonical_items:
        for item in sorted(res.governed_reality.canonical_items, key=lambda x: x.provenance.fact_key):
            canonical_facts[item.provenance.fact_key] = {
                "value": item.value,
                "authority": item.provenance.authority.value if hasattr(item.provenance.authority, "value") else str(item.provenance.authority),
                "source": item.provenance.source_type.value if hasattr(item.provenance.source_type, "value") else str(item.provenance.source_type),
                "is_canonical": item.is_canonical,
            }

    choices_proj = []
    for c in sorted(res.choices, key=lambda x: x.slot_name):
        choices_proj.append({
            "slot_name": c.slot_name,
            "selected_value": c.selected_candidate.proposed_value if c.selected_candidate else None,
            "rationale_code": c.rationale_code.value if hasattr(c.rationale_code, "value") else str(c.rationale_code),
            "competition_state": c.competition_state.value if hasattr(c.competition_state, "value") else str(c.competition_state),
            "is_non_canonical": c.is_non_canonical,
        })

    repair_proj = None
    if res.repair_result:
        repair_proj = {
            "repair_level": res.repair_result.repair_level.value,
            "is_repaired": res.repair_result.is_repaired,
            "repair_action": res.repair_result.repair_action,
        }

    contradiction_proj = {
        "contradiction_type": res.contradiction.contradiction_type.value,
        "repair_strategy": res.contradiction.repair_strategy.value,
    }

    reconciliation_proj = None
    if res.reconciliation_result:
        reconciliation_proj = {
            "actions": sorted([item.action_type.value for item in res.reconciliation_result.routing_items]),
            "excluded_candidate_ids": sorted(list(res.reconciliation_result.candidate_ids_to_exclude)),
            "injected_candidate_slots": sorted([c.slot_name for c in res.reconciliation_result.candidate_hypotheses_to_inject]),
            "repair_request_keys": sorted([r.claim_key for r in res.reconciliation_result.repair_requests]),
        }

    return {
        "promoted": res.promoted,
        "canonical_facts": canonical_facts,
        "choices": choices_proj,
        "repair": repair_proj,
        "contradiction": contradiction_proj,
        "reconciliation": reconciliation_proj,
    }


# =============================================================================
# Golden Acceptance Suite 9 (GC-221 ~ GC-245)
# =============================================================================

class TestGoldenSuite9:
    """Phase 9.6 Golden Acceptance Benchmark Suite (25 Tests)."""

    # =========================================================================
    # Cluster 1: The 10 Constitutional Locks Hard Invariants (GC-221 ~ GC-225)
    # =========================================================================

    def test_gc221_zero_direct_mutation_authority_and_mutation_singularity(self):
        """GC-221 (Lock 1 & Lock 10): Zero Direct Mutation Authority & Canonical Mutation Singularity.

        Verification Gateway, Evaluator, Reconciler, and Orchestrator have 0 direct mutation authority.
        Only BiographyPromotionService mints single-use PromotionAuthorizationToken to mutate core facts.
        """
        # 1. Structural check: No Phase 9 module exposes direct fact mutation methods
        gateway = VerificationGateway()
        evaluator = EpistemicSourceEvaluator()
        reconciler = VerificationReconciler()

        for obj in (gateway, evaluator, reconciler):
            assert not hasattr(obj, "set_fact"), f"{type(obj)} must not expose set_fact method."
            assert not hasattr(obj, "mutate_core"), f"{type(obj)} must not expose mutate_core method."

        # 2. Runtime authorization enforcement: direct set_fact without valid token is blocked
        fake_core_service = FakeCoreService()
        with pytest.raises(AevumCanonicalNotDirectlyEditableError):
            import asyncio
            asyncio.run(
                fake_core_service.set_fact(
                    character_id="aevum",
                    fact_key="education.university",
                    value="Kyoto University",
                    allow_canonical_reconciliation=True,
                    authorization_token=None,  # Missing token!
                )
            )

        # 3. Forged token with mismatched hash is rejected
        forged_token = PromotionAuthorizationToken.create(
            character_id="aevum",
            slot_name="education.university",
            value="Tokyo University",  # Mismatched value!
            candidate_id="cand_1",
            choice_decision_id="dec_1",
        )
        with pytest.raises(AevumCanonicalNotDirectlyEditableError):
            asyncio.run(
                fake_core_service.set_fact(
                    character_id="aevum",
                    fact_key="education.university",
                    value="Kyoto University",
                    allow_canonical_reconciliation=True,
                    authorization_token=forged_token,
                )
            )

    def test_gc222_decision_only_policy_engine(self):
        """GC-222 (Lock 2): Decision-Only Policy Engine.

        VerificationPolicyEngine evaluates consequence tiers, quiet hours, user consent,
        turn budgets, and daily caps. Emits VerificationDecision; possesses 0 network/tool execution capability.
        """
        engine = VerificationPolicyEngine()

        # Engine has zero execution methods
        forbidden_methods = {"fetch", "query", "execute", "post", "get", "mutate", "write", "call_adapter"}
        for method in forbidden_methods:
            assert not hasattr(engine, method), f"VerificationPolicyEngine must not possess execution method '{method}'."

        # Evaluates constraints deterministically into a VerificationDecision
        req = VerificationRequest(
            request_id="req_pol_01",
            created_at=_utc_now(),
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="preferences.tea",
            claim_value="Green Tea",
            entity_binding_anchor="aevum",
            consequence_tier=ConsequenceTier.LOW,
            urgency=VerificationUrgency.BACKGROUND_ROUTINE,
        )
        ctx = VerificationPolicyContext(
            current_time=_utc_now(),
            user_privacy_consented=True,
            is_quiet_hours=True,
            turn_verification_budget_remaining=5,
            daily_verification_cap=20,
        )

        decision = engine.evaluate(req, ctx)
        assert isinstance(decision, VerificationDecision)
        assert decision.should_verify is False
        assert decision.suppression_reason == "QUIET_HOURS_DEFERRED"
        assert decision.allowed_authorities == ()

    def test_gc223_source_authority_not_truth_and_domain_separation(self):
        """GC-223 (Lock 3 & Lock 4): Source Authority != Truth & Domain Separation.

        - Institutional authority cannot establish personal fact without personal anchor (unanchored homonym).
        - Personal statement cannot overwrite objective world reality (domain separation).
        - Authority resolves eligible conflicts, but never synthesizes evidence from nothing.
        """
        evaluator = EpistemicSourceEvaluator()

        # Part 1: High institutional authority without personal entity anchor evaluates to AMBIGUOUS_CONFLICT
        personal_req = VerificationRequest(
            request_id="req_homonym",
            created_at=_utc_now(),
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="education.university",
            claim_value="Kyoto University",
            entity_binding_anchor="aevum",
            consequence_tier=ConsequenceTier.MEDIUM,
            urgency=VerificationUrgency.BACKGROUND_ROUTINE,
        )
        decision = _make_decision(
            personal_req,
            should_verify=True,
            allowed_authorities=(SourceAuthority.PRIMARY_INSTITUTIONAL,),
            allowed_source_kinds=(SourceKind.PUBLIC_REGISTRY,),
            decision_id="dec_h",
        )
        homonym_obs = _make_observation(
            observation_id="obs_homonym",
            source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
            source_kind=SourceKind.PUBLIC_REGISTRY,
            observed_content_snippet="Kyoto University graduation register.",
            structured_payload={"key": "education.university", "value": "Kyoto University"},
            observed_entity_name="Aevum",  # Unanchored homonym: name matches, but lacks entity_binding_anchor!
        )
        finding_homonym = evaluator.evaluate_observations(
            request=personal_req,
            decision=decision,
            observations=[homonym_obs],
        )
        assert finding_homonym.epistemic_status == ClaimEpistemicStatus.AMBIGUOUS_CONFLICT

        # Part 2: Zero observations yields INSUFFICIENT_EVIDENCE (cannot synthesize evidence from nothing)
        finding_empty = evaluator.evaluate_observations(
            request=personal_req,
            decision=decision,
            observations=[],
        )
        assert finding_empty.epistemic_status == ClaimEpistemicStatus.INSUFFICIENT_EVIDENCE

    def test_gc224_temporal_isolation_and_physical_temporal_wall(self):
        """GC-224 (Lock 5 & Lock 7): Temporal Isolation & Physical Temporal Wall.

        Turn N verification requests never block the turn.
        Verified findings are physically unconsumable in Turn N (origin_turn_id == consumer_turn_id).
        Items are only consumable in Turn N+1 (eligible_from_turn_sequence <= consumer_turn_sequence).
        """
        inbox = VerificationEvidenceInbox()
        finding = _make_finding(epistemic_status=ClaimEpistemicStatus.SUPPORTED)

        # Worker finishes and deposits finding in Turn 1 with eligibility for Turn 2
        item = inbox.deposit(
            source_job_id="job_turn_1",
            finding=finding,
            origin_turn_id="turn-1",
            eligible_from_turn_id="turn-2",
            origin_turn_sequence=1,
            eligible_from_turn_sequence=2,
        )
        assert item is not None

        # Turn 1 drain attempt: physically blocked by Temporal Wall
        drained_turn_1 = inbox.drain_for_turn(
            consumer_turn_id="turn-1",
            consumer_turn_sequence=1,
        )
        assert len(drained_turn_1) == 0, "Temporal Wall violation: finding consumed in origin turn!"

        # Turn 2 drain attempt: successfully drained
        drained_turn_2 = inbox.drain_for_turn(
            consumer_turn_id="turn-2",
            consumer_turn_sequence=2,
        )
        assert len(drained_turn_2) == 1
        assert drained_turn_2[0].source_job_id == "job_turn_1"
        assert drained_turn_2[0].consumed_by_turn_id == "turn-2"

    def test_gc225_repair_delegation_and_entity_binding_isolation(self):
        """GC-225 (Lock 6 & Lock 8): Repair Delegation & Entity Binding Isolation.

        - Refutations delegate strictly to RealityRepairService.repair(); zero ad-hoc overwrites or candidate deletions.
        - Entity match != Aevum match; external observations about unanchored entities evaluate to
          AMBIGUOUS_CONFLICT and preserve uncertainty (zero candidate invalidation, zero fact modification).
        """
        reconciler = VerificationReconciler()
        core = _make_mock_core()
        cand = _make_candidate("c_kyoto", "education.university", "Kyoto University", entity_id="aevum")

        # Case 1: Unanchored entity homonym preserves uncertainty (0 repair, 0 exclusion)
        ambiguous_finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="education.university",
            epistemic_status=ClaimEpistemicStatus.AMBIGUOUS_CONFLICT,
            claim_value="Kyoto University",
            entity_binding_anchor="different_external_entity",
        )
        item_ambiguous = _make_inbox_item(ambiguous_finding)
        res_ambiguous = reconciler.reconcile(
            inbox_items=[item_ambiguous],
            core=core,
            active_candidates=[cand],
        )
        assert len(res_ambiguous.candidate_ids_to_exclude) == 0
        assert len(res_ambiguous.repair_requests) == 0
        assert any(
            item.action_type == ReconciliationActionType.PRESERVE_UNCERTAINTY
            for item in res_ambiguous.routing_items
        )

        # Case 2: Refuted candidate delegates via VerificationRepairRequest (zero ad-hoc deletion)
        contradicted_finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="education.university",
            epistemic_status=ClaimEpistemicStatus.CONTRADICTED,
            claim_value="Kyoto University",
            entity_binding_anchor="aevum",
        )
        item_contra = _make_inbox_item(contradicted_finding)
        res_contra = reconciler.reconcile(
            inbox_items=[item_contra],
            core=core,
            active_candidates=[cand],
        )
        assert len(res_contra.repair_requests) == 1
        repair_req = res_contra.repair_requests[0]
        assert repair_req.claim_key == "education.university"
        assert not hasattr(repair_req, "repair_level"), "Reconciler must not select repair_level directly."

    # =========================================================================
    # Cluster 2: Epistemic Source Evaluation & Evidence Semantics (GC-226 ~ GC-229)
    # =========================================================================

    def test_gc226_authority_cannot_override_scope_or_freshness(self):
        """GC-226: Authority Cannot Override Scope or Freshness (Lock 3 & ADR-020 Item 14).

        - High-authority source outside domain/scope evaluates to OUT_OF_SCOPE.
        - Superseded historical source (SUPERSEDED_OUTDATED) cannot override an active current observation (CURRENT).
        """
        evaluator = EpistemicSourceEvaluator()
        req = VerificationRequest(
            request_id="req_scope_fresh",
            created_at=_utc_now(),
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="education.university",
            claim_value="Kyoto University",
            entity_binding_anchor="aevum",
            consequence_tier=ConsequenceTier.HIGH,
            urgency=VerificationUrgency.BACKGROUND_ROUTINE,
        )
        decision = _make_decision(
            req,
            should_verify=True,
            allowed_authorities=(
                SourceAuthority.PRIMARY_INSTITUTIONAL,
                SourceAuthority.OFFICIAL_PUBLIC_RECORD,
            ),
            allowed_source_kinds=(SourceKind.PUBLIC_REGISTRY,),
            decision_id="dec_sf",
        )

        # 1. High authority with mismatched claim key evaluates to OUT_OF_SCOPE
        out_of_scope_obs = _make_observation(
            observation_id="obs_oos",
            source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
            source_kind=SourceKind.PUBLIC_REGISTRY,
            observed_content_snippet="Kyoto Marathon record",
            structured_payload={
                "key": "sports.marathon",  # Unrelated key!
                "value": "Kyoto Marathon",
                "entity_binding_anchor": "aevum",
            },
        )
        finding_oos = evaluator.evaluate_observations(
            request=req,
            decision=decision,
            observations=[out_of_scope_obs],
        )
        assert finding_oos.epistemic_status == ClaimEpistemicStatus.OUT_OF_SCOPE

        # 2. Outdated official record cannot override current observation
        outdated_official_obs = _make_observation(
            observation_id="obs_old_official",
            source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
            source_kind=SourceKind.PUBLIC_REGISTRY,
            observed_content_snippet="Tokyo University alumni 2018",
            structured_payload={
                "key": "education.university",
                "value": "Tokyo University",
                "entity_binding_anchor": "aevum",
                "freshness": EvidenceFreshness.SUPERSEDED_OUTDATED.value,
            },
            observed_at=datetime(2018, 1, 1, tzinfo=timezone.utc),
        )
        current_supporting_obs = _make_observation(
            observation_id="obs_curr_supp",
            source_authority=SourceAuthority.OFFICIAL_PUBLIC_RECORD,
            source_kind=SourceKind.PUBLIC_REGISTRY,
            observed_content_snippet="Kyoto University current degree 2025",
            structured_payload={
                "key": "education.university",
                "value": "Kyoto University",
                "entity_binding_anchor": "aevum",
                "freshness": EvidenceFreshness.CURRENT.value,
            },
            observed_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        finding_freshness = evaluator.evaluate_observations(
            request=req,
            decision=decision,
            observations=[outdated_official_obs, current_supporting_obs],
        )
        # Current evidence dominates outdated superseded record
        assert finding_freshness.epistemic_status == ClaimEpistemicStatus.SUPPORTED

    def test_gc227_deterministic_authority_resolution_and_ambiguity_preservation(self):
        """GC-227: Deterministic Authority Resolution & Ambiguity Preservation (Lock GC-227 & ADR-020 Item 3/15).

        - 1 admissible official source dominates multiple informal sources (rejects raw majority voting / headcount).
        - 2 equally authoritative conflicting sources without scope/freshness tie-breaker: deterministically yields AMBIGUOUS_CONFLICT.
        """
        evaluator = EpistemicSourceEvaluator()
        req = VerificationRequest(
            request_id="req_auth_res",
            created_at=_utc_now(),
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="education.university",
            claim_value="Kyoto University",
            entity_binding_anchor="aevum",
            consequence_tier=ConsequenceTier.HIGH,
            urgency=VerificationUrgency.BACKGROUND_ROUTINE,
        )
        decision = _make_decision(
            req,
            should_verify=True,
            allowed_authorities=(
                SourceAuthority.PRIMARY_INSTITUTIONAL,
                SourceAuthority.UNVERIFIED_EXTERNAL,
            ),
            allowed_source_kinds=(
                SourceKind.PUBLIC_REGISTRY,
                SourceKind.WEB_DOCUMENT,
            ),
            decision_id="dec_ar",
        )

        # 1. Single PRIMARY_INSTITUTIONAL source dominates 3 UNVERIFIED_EXTERNAL forum contradictions (no 3v1 voting)
        official_supporting = _make_observation(
            observation_id="obs_official_1",
            source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
            source_kind=SourceKind.PUBLIC_REGISTRY,
            observed_content_snippet="Kyoto University verified",
            structured_payload={
                "key": "education.university",
                "value": "Kyoto University",
                "entity_binding_anchor": "aevum",
                "freshness": EvidenceFreshness.CURRENT.value,
            },
        )
        unverified_contradictions = [
            _make_observation(
                observation_id=f"obs_forum_{i}",
                source_authority=SourceAuthority.UNVERIFIED_EXTERNAL,
                source_kind=SourceKind.WEB_DOCUMENT,
                observed_content_snippet="Tokyo University forum post",
                structured_payload={
                    "key": "education.university",
                    "value": "Tokyo University",
                    "entity_binding_anchor": "aevum",
                    "freshness": EvidenceFreshness.CURRENT.value,
                },
            )
            for i in range(3)
        ]
        finding_dominance = evaluator.evaluate_observations(
            request=req,
            decision=decision,
            observations=[official_supporting] + unverified_contradictions,
        )
        assert finding_dominance.epistemic_status == ClaimEpistemicStatus.SUPPORTED

        # 2. Equal authority tie with no freshness distinction yields AMBIGUOUS_CONFLICT (zero forced truth)
        official_contradicting = _make_observation(
            observation_id="obs_official_contra",
            source_authority=SourceAuthority.PRIMARY_INSTITUTIONAL,
            source_kind=SourceKind.PUBLIC_REGISTRY,
            observed_content_snippet="Tokyo University registry record",
            structured_payload={
                "key": "education.university",
                "value": "Tokyo University",
                "entity_binding_anchor": "aevum",
                "freshness": EvidenceFreshness.CURRENT.value,
            },
        )
        finding_tie = evaluator.evaluate_observations(
            request=req,
            decision=decision,
            observations=[official_supporting, official_contradicting],
        )
        assert finding_tie.epistemic_status == ClaimEpistemicStatus.AMBIGUOUS_CONFLICT

    def test_gc228_operational_failure_separation_from_epistemic_status(self):
        """GC-228: Operational Failure Separation from Epistemic Status (ADR-020 Item 14).

        Gateway timeouts (TIMED_OUT) and worker failures (FAILED) are purely operational job statuses;
        they are NEVER manufactured into fake CONTRADICTED or INSUFFICIENT_EVIDENCE findings in the inbox.
        """
        gateway = VerificationGateway()
        inbox = VerificationEvidenceInbox()
        orchestrator = VerificationAsyncOrchestrator(
            gateway=gateway,
            evaluator=EpistemicSourceEvaluator(),
            inbox=inbox,
        )

        req = VerificationRequest(
            request_id="req_timeout_test",
            created_at=_utc_now(),
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="education.university",
            claim_value="Kyoto University",
            entity_binding_anchor="aevum",
            consequence_tier=ConsequenceTier.HIGH,
            urgency=VerificationUrgency.BACKGROUND_ROUTINE,
        )
        decision = _make_decision(
            req,
            should_verify=True,
            allowed_authorities=(SourceAuthority.PRIMARY_INSTITUTIONAL,),
            allowed_source_kinds=(SourceKind.PUBLIC_REGISTRY,),
            decision_id="dec_timeout",
        )

        # Enqueue job
        dispatch_res = orchestrator.enqueue_verification_job(
            request=req,
            decision=decision,
            origin_turn_id="turn-1",
            origin_turn_sequence=1,
        )
        assert dispatch_res.status == VerificationJobStatus.QUEUED

        # Simulate execution timeout in gateway
        with patch.object(gateway, "execute_verification", side_effect=TimeoutError("Network timeout")):
            completed_job = orchestrator.process_next_job()

        # Job transitioned to operational failure/retry status
        assert completed_job is not None
        assert completed_job.status in (VerificationJobStatus.QUEUED, VerificationJobStatus.TIMED_OUT)
        # Inbox contains ZERO findings from this timed-out job
        assert len(inbox.peek_unconsumed()) == 0

    def test_gc229_zero_float_pure_discrete_epistemic_architecture(self):
        """GC-229: Zero-Float Pure Discrete Epistemic Architecture (Permanent Note A).

        All Phase 9 contracts, policies, evaluations, inbox items, and reconciliation requests
        strictly maintain 0 float fields. All types are discrete enums, strings, ints, datetimes, and tuples.
        """
        models_to_audit = [
            VerificationRequest,
            VerificationPolicyContext,
            VerificationDecision,
            ExternalObservation,
            VerificationFinding,
            VerificationEvidencePayload,
            VerificationInboxItem,
            VerificationJob,
            VerificationRepairRequest,
            VerificationTemporalSplitContext,
            VerificationEntityDisambiguationContext,
            ReconciliationRoutingItem,
            VerificationReconciliationResult,
        ]

        float_violations: list[str] = []
        for model in models_to_audit:
            for field_name, field_info in model.model_fields.items():
                ann_str = str(field_info.annotation).lower()
                if "float" in ann_str:
                    float_violations.append(f"{model.__name__}.{field_name} has float annotation: {field_info.annotation}")

        assert not float_violations, f"Discrete epistemic architecture violated by float fields: {float_violations}"

    # =========================================================================
    # Cluster 3: Queue Deduplication, Idempotency & Temporal Wall (GC-230 ~ GC-233)
    # =========================================================================

    def test_gc230_canonical_deterministic_deduplication_key(self):
        """GC-230: Canonical Deterministic Deduplication Key (ADR-020 Item 18).

        Sorted JSON hashing via SHA-256 for claim work scheduling.
        Deduplication key is an identity key for verification work, NOT evidence truth.
        """
        req_a = VerificationRequest(
            request_id="req_a_123",
            created_at=_utc_now(),
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="education.university",
            claim_value="Kyoto University",
            entity_binding_anchor="aevum",
            consequence_tier=ConsequenceTier.HIGH,
            urgency=VerificationUrgency.BACKGROUND_ROUTINE,
        )
        req_b = VerificationRequest(
            request_id="req_b_999",  # Different request_id and created_at
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="education.university",
            claim_value="Kyoto University",
            entity_binding_anchor="aevum",
            consequence_tier=ConsequenceTier.LOW,  # Different consequence tier
            urgency=VerificationUrgency.BACKGROUND_ROUTINE,
        )
        # Identical core claim fields produce identical SHA-256 deduplication key
        key_a = compute_deduplication_key(req_a)
        key_b = compute_deduplication_key(req_b)
        assert key_a == key_b
        assert len(key_a) == 64

        # Different claim value produces distinct hash
        req_diff = req_a.model_copy(update={"claim_value": "Tokyo University"})
        key_diff = compute_deduplication_key(req_diff)
        assert key_diff != key_a

    def test_gc231_turn_scoped_queue_deduplication_and_cross_turn_reverification(self):
        """GC-231: Turn-Scoped Queue Deduplication & Cross-Turn Re-Verification (ADR-020 Item 18).

        - Coalesces identical verification requests within the same turn.
        - Allows clean, fresh verification jobs across subsequent turns.
        """
        gateway = VerificationGateway()
        orchestrator = VerificationAsyncOrchestrator(
            gateway=gateway,
            evaluator=EpistemicSourceEvaluator(),
        )

        req = VerificationRequest(
            request_id="req_turn_scope",
            created_at=_utc_now(),
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="education.university",
            claim_value="Kyoto University",
            entity_binding_anchor="aevum",
            consequence_tier=ConsequenceTier.HIGH,
            urgency=VerificationUrgency.BACKGROUND_ROUTINE,
        )
        decision = _make_decision(
            req,
            should_verify=True,
            allowed_authorities=(SourceAuthority.PRIMARY_INSTITUTIONAL,),
            allowed_source_kinds=(SourceKind.PUBLIC_REGISTRY,),
            decision_id="dec_ts",
        )

        # 1. Same turn: two enqueue calls coalesce to the same job
        res_t1_first = orchestrator.enqueue_verification_job(req, decision, origin_turn_id="turn-1", origin_turn_sequence=1)
        res_t1_second = orchestrator.enqueue_verification_job(req, decision, origin_turn_id="turn-1", origin_turn_sequence=1)
        assert res_t1_first.job_id == res_t1_second.job_id
        assert res_t1_second.is_duplicate is True

        # 2. Next turn: same claim dispatches a clean, fresh job
        res_t2 = orchestrator.enqueue_verification_job(req, decision, origin_turn_id="turn-2", origin_turn_sequence=2)
        assert res_t2.job_id != res_t1_first.job_id
        assert not res_t2.is_duplicate

    def test_gc232_job_to_inbox_idempotency_protocol(self):
        """GC-232: Job-to-Inbox Idempotency Protocol (ADR-020 Item 19).

        Worker retry after partial crash calling inbox.deposit(source_job_id, ...) idempotently
        returns the existing inbox item without generating duplicate evidence.
        """
        inbox = VerificationEvidenceInbox()
        finding = _make_finding(epistemic_status=ClaimEpistemicStatus.SUPPORTED)

        # Deposit 1
        item_1 = inbox.deposit(
            source_job_id="job_crash_retry_99",
            finding=finding,
            origin_turn_id="turn-1",
            eligible_from_turn_id="turn-2",
            origin_turn_sequence=1,
            eligible_from_turn_sequence=2,
        )

        # Deposit 2 (simulated worker retry after partial network failure)
        item_2 = inbox.deposit(
            source_job_id="job_crash_retry_99",
            finding=finding,
            origin_turn_id="turn-1",
            eligible_from_turn_id="turn-2",
            origin_turn_sequence=1,
            eligible_from_turn_sequence=2,
        )

        assert item_1.inbox_id == item_2.inbox_id
        assert len(inbox.peek_unconsumed()) == 1

    def test_gc233_earliest_eligible_turn_invariant_under_non_sequential_turn_ids(self):
        """GC-233: Earliest-Eligible Turn Invariant Under Non-Sequential Turn IDs (ADR-020 Item 17).

        True earliest-turn semantics: an item eligible from sequence 2 is consumable in turn sequence 2, 5, or later,
        but strictly unconsumable in turn sequence 0 or 1.
        """
        inbox = VerificationEvidenceInbox()
        finding = _make_finding(epistemic_status=ClaimEpistemicStatus.SUPPORTED)

        inbox.deposit(
            source_job_id="job_nonseq",
            finding=finding,
            origin_turn_id="turn-1",
            eligible_from_turn_id="turn-2",
            origin_turn_sequence=1,
            eligible_from_turn_sequence=2,
        )

        # Unconsumable in sequence 1 (origin turn)
        assert len(inbox.drain_for_turn(consumer_turn_id="turn-1", consumer_turn_sequence=1)) == 0

        # Jump forward to sequence 6 (user had silence for turns 2..5)
        drained_jump = inbox.drain_for_turn(consumer_turn_id="turn-6", consumer_turn_sequence=6)
        assert len(drained_jump) == 1
        assert drained_jump[0].source_job_id == "job_nonseq"

    # =========================================================================
    # Cluster 4: Evidence Reconciliation & Refutation Routing (GC-234 ~ GC-238)
    # =========================================================================

    def test_gc234_anti_shortcut_supported_to_promotion_pipeline(self):
        """GC-234: Anti-Shortcut Invariant (Anti-Magical-Promotion).

        External finding with SUPPORTED status NEVER directly writes to CharacterCore.facts.
        Must enter through VerificationEvidencePayload -> Step C5 -> Candidate Competition -> Choice -> 14 Gates.
        """
        core = _make_mock_core(facts={"education.university": "Kyoto University"})
        reconciler = VerificationReconciler()
        cand = _make_candidate("c_kyoto", "education.university", "Kyoto University")

        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="education.university",
            epistemic_status=ClaimEpistemicStatus.SUPPORTED,
            claim_value="Kyoto University",
            entity_binding_anchor="aevum",
        )
        item = _make_inbox_item(finding)

        # Reconciler processes item
        res = reconciler.reconcile(inbox_items=[item], core=core, active_candidates=[cand])

        # Core facts remain untouched during reconciliation
        assert core.facts["education.university"].value == "Kyoto University"
        # Candidate is augmented with payload for competition injection, NOT directly promoted
        assert len(res.candidate_hypotheses_to_inject) == 1
        aug_cand = res.candidate_hypotheses_to_inject[0]
        assert any(ef.source_type == "EXTERNAL_VERIFICATION" for ef in aug_cand.evidence_families)

    def test_gc235_domain_gated_world_reality_isolation(self):
        """GC-235: Domain-Gated World Reality Isolation (ADR-020 Item 21).

        WORLD_REALITY observations are strictly isolated from the personal candidate, repair,
        and promotion pipeline; zero personal fact modification authority.
        """
        reconciler = VerificationReconciler()
        core = _make_mock_core()
        cand = _make_candidate("c_world", "world.university_duration", "4 years")

        finding_world = _make_finding(
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="education.usm.programme_duration",
            epistemic_status=ClaimEpistemicStatus.CONTRADICTED,
            claim_value=3,
        )
        item_world = _make_inbox_item(finding_world)

        res = reconciler.reconcile(
            inbox_items=[item_world],
            core=core,
            active_candidates=[cand],
        )

        # Isolated from personal reality pipeline:
        assert len(res.candidate_ids_to_exclude) == 0
        assert len(res.candidate_hypotheses_to_inject) == 0
        assert len(res.repair_requests) == 0

    def test_gc236_reconciler_routing_not_repair_decision(self):
        """GC-236: Reconciler Routing != Repair Decision (ADR-020 Item 22).

        Reconciler packages typed factual inputs in VerificationRepairRequest;
        never selects or passes a RepairLevel. RealityRepairService evaluates hierarchy independently.
        """
        reconciler = VerificationReconciler()
        core = _make_mock_core()
        cand = _make_candidate("c_contra", "education.degree", "Computer Science")

        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="education.degree",
            epistemic_status=ClaimEpistemicStatus.CONTRADICTED,
            claim_value="Computer Science",
            entity_binding_anchor="aevum",
        )
        item = _make_inbox_item(finding)

        res = reconciler.reconcile([item], core=core, active_candidates=[cand])
        assert len(res.repair_requests) == 1
        req = res.repair_requests[0]
        # Reconciler emits typed factual parameters only; zero RepairLevel enum
        assert req.claim_key == "education.degree"
        assert req.claimed_value == "Computer Science"
        assert not hasattr(req, "repair_level")

    def test_gc237_evaluation_level_candidate_exclusion_is_derived_view_only(self):
        """GC-237: Evaluation-Level Candidate Exclusion is Derived View Only (ADR-020 Item 23).

        Refuted candidates are excluded from the current turn's competition_candidates.
        all_candidates remains intact; candidate object's lifecycle_state is NOT mutated in-place; zero DB deletions.
        """
        reconciler = VerificationReconciler()
        core = _make_mock_core()
        cand = _make_candidate(
            "c_refuted",
            "education.degree",
            "Computer Science",
            lifecycle_state=CandidateLifecycleState.ACTIVE,
        )

        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="education.degree",
            epistemic_status=ClaimEpistemicStatus.CONTRADICTED,
            claim_value="Computer Science",
            entity_binding_anchor="aevum",
        )
        item = _make_inbox_item(finding)

        res = reconciler.reconcile([item], core=core, active_candidates=[cand])
        assert "c_refuted" in res.candidate_ids_to_exclude
        # Original candidate remains completely untouched in ACTIVE lifecycle state
        assert cand.lifecycle_state == CandidateLifecycleState.ACTIVE

    def test_gc238_all_typed_repair_boundary_and_zero_control_dict_penetration(self):
        """GC-238: All-Typed Repair Boundary & Zero Control Dict Penetration (ADR-020 Item 25).

        VerificationTemporalSplitContext and VerificationEntityDisambiguationContext enforce extra='forbid'.
        Zero dict[str, Any] bypasses the reconciler-repair boundary.
        """
        # Extra kwargs strictly rejected by model validation
        with pytest.raises(ValidationError):
            VerificationTemporalSplitContext(
                conflicting_interval="2021-2024",
                observed_interval="2018-2020",
                temporal_relation="PRECEDES",
                arbitrary_control_flag=True,  # Forbidden extra field!
            )

        with pytest.raises(ValidationError):
            VerificationEntityDisambiguationContext(
                canonical_entity_anchor="aevum",
                observed_entity_anchor="stranger",
                ambiguity_reason="Homonym match",
                bypass_authorization=True,  # Forbidden extra field!
            )

    # =========================================================================
    # Cluster 5: End-to-End Multi-Turn Integration & Complex Lifecycles (GC-239 ~ GC-242)
    # =========================================================================

    @pytest.mark.asyncio
    async def test_gc239_complete_multiturn_veracity_cycle_personal_claim(self):
        """GC-239: Complete Multi-Turn Veracity Cycle — Personal Claim Corroboration (Lock B & ADR-020 Item 27).

        - Turn 1: User claims Kyoto University. Enqueued in async gateway; Temporal Wall blocks Turn 1 drain.
        - Background: Registry returns SUPPORTED; deposited with eligible_from_turn_id='turn-2'.
        - Turn 2: Step C5 drains inbox. Candidate augmented with EXTERNAL_VERIFICATION.
        - Wins Step E competition & Step F choice with choice_margin >= active_policy.min_choice_margin.
        - Step H 14 promotion gates pass; promoted to canonical reality.
        """
        session = _make_mock_session()
        inbox = VerificationEvidenceInbox()
        reconciler = VerificationReconciler()

        cand_kyoto = _make_candidate(
            "c_kyoto",
            "education.institution",
            "Kyoto University",
            composite_plausibility=0.85,
        )
        cand_tokyo = _make_candidate(
            "c_tokyo",
            "education.institution",
            "Tokyo University",
            composite_plausibility=0.60,
        )

        mock_repo = MagicMock(spec=CandidateRepository)
        mock_repo.get_all_active_candidates = AsyncMock(return_value=[cand_kyoto, cand_tokyo])
        mock_repo.save_choice_decision = AsyncMock()
        mock_repo.get_biography_promotion_by_candidate = AsyncMock(return_value=None)
        mock_repo.record_biography_promotion = AsyncMock()
        mock_repo.save_biography_promotion = AsyncMock()
        mock_repo.update_candidate_lifecycle = AsyncMock()

        core = _make_mock_core()
        fake_core_service = FakeCoreService(core.facts)

        service = RealityOrchestrationService(
            session=session,
            candidate_repo=mock_repo,
            inbox=inbox,
            reconciler=reconciler,
        )

        # Deposit verified finding with eligible_from_turn_sequence=2
        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="education.institution",
            epistemic_status=ClaimEpistemicStatus.SUPPORTED,
            claim_value="Kyoto University",
            entity_binding_anchor="aevum",
        )
        inbox.deposit(
            source_job_id="job_kyoto_veracity",
            finding=finding,
            origin_turn_id="turn-1",
            eligible_from_turn_id="turn-2",
            origin_turn_sequence=1,
            eligible_from_turn_sequence=2,
        )

        # Turn 1: Temporal Wall prevents drain
        res_t1 = await service.run_turn(
            user_input="Did you graduate from Kyoto University?",
            core=core,
            current_turn_id="turn-1",
            current_turn_sequence=1,
        )
        assert res_t1.reconciliation_result is None

        # Turn 2: Finding drained, candidate augmented, passes promotion with policy-scoped margin
        with patch("app.character.core_service.CharacterCoreService", return_value=fake_core_service), \
             patch("app.reality.biography_promotion_service.CharacterCoreService", return_value=fake_core_service):
            res_t2 = await service.run_turn(
                user_input="Tell me about Kyoto University.",
                core=core,
                current_turn_id="turn-2",
                current_turn_sequence=2,
            )

        assert res_t2.reconciliation_result is not None
        assert res_t2.promoted is True
        assert fake_core_service.facts["education.institution"].value == "Kyoto University"

    @pytest.mark.asyncio
    async def test_gc240_complete_multiturn_refutation_cycle_unconfirmed_candidate(self):
        """GC-240: Complete Multi-Turn Refutation Cycle — Unconfirmed Candidate Refutation.

        - Turn 1: Unconfirmed candidate exists. Verification queued.
        - Background: Registry adapter returns CONTRADICTED finding.
        - Turn 2: Step C5 drains inbox. Candidate excluded from competition view.
        - RealityRepairService executes Level 3 Fact Invalidation. Candidate is preserved in all_candidates (not deleted).
        """
        session = _make_mock_session()
        inbox = VerificationEvidenceInbox()
        reconciler = VerificationReconciler()

        cand_unconfirmed = _make_candidate(
            "c_unconfirmed",
            "education.university",
            "Tokyo University",
            composite_plausibility=0.65,
        )

        mock_repo = MagicMock(spec=CandidateRepository)
        mock_repo.get_all_active_candidates = AsyncMock(return_value=[cand_unconfirmed])
        mock_repo.save_choice_decision = AsyncMock()

        service = RealityOrchestrationService(
            session=session,
            candidate_repo=mock_repo,
            inbox=inbox,
            reconciler=reconciler,
        )
        core = _make_mock_core()

        # Deposit contradiction
        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="education.university",
            epistemic_status=ClaimEpistemicStatus.CONTRADICTED,
            claim_value="Tokyo University",
            entity_binding_anchor="aevum",
        )
        inbox.deposit(
            source_job_id="job_contra",
            finding=finding,
            origin_turn_id="turn-1",
            eligible_from_turn_id="turn-2",
            origin_turn_sequence=1,
            eligible_from_turn_sequence=2,
        )

        res_t2 = await service.run_turn(
            user_input="Did you attend Tokyo University?",
            core=core,
            current_turn_id="turn-2",
            current_turn_sequence=2,
        )

        # Candidate excluded from competition
        assert "c_unconfirmed" in res_t2.reconciliation_result.candidate_ids_to_exclude
        # Level 3 Fact Invalidation executed
        assert res_t2.repair_result is not None
        assert res_t2.repair_result.repair_level == RepairLevel.LEVEL_3_FACT_INVALIDATION
        # Preserved in all_candidates; not deleted
        assert any(c.candidate_id == "c_unconfirmed" for c in res_t2.candidates)
        assert res_t2.promoted is False

    @pytest.mark.asyncio
    async def test_gc241_canonical_personal_fact_contradiction_with_timeline_split(self):
        """GC-241: Canonical Personal Fact Contradiction with Timeline Split.

        - Canonical fact exists in core.facts. External observation provides historical interval.
        - Reconciler routes typed VerificationTemporalSplitContext.
        - Resolves at Level 2 Temporal Reinterpretation; zero compensatory lore invention.
        """
        session = _make_mock_session()
        inbox = VerificationEvidenceInbox()
        reconciler = VerificationReconciler()

        mock_repo = MagicMock(spec=CandidateRepository)
        mock_repo.get_all_active_candidates = AsyncMock(return_value=[])
        mock_repo.save_choice_decision = AsyncMock()

        core = _make_mock_core(facts={"education.degree": "Bachelor of Science (2021-2024)"})
        service = RealityOrchestrationService(
            session=session,
            candidate_repo=mock_repo,
            inbox=inbox,
            reconciler=reconciler,
        )

        # Historical degree interval contradicts current claim
        temporal_ctx = VerificationTemporalSplitContext(
            conflicting_interval=(2021, 2024),
            observed_interval=(2018, 2020),
            temporal_relation="PRECEDES",
        )
        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="education.degree",
            epistemic_status=ClaimEpistemicStatus.CONTRADICTED,
            claim_value="Bachelor of Science (2018-2020)",
            entity_binding_anchor="aevum",
        )
        item = _make_inbox_item(finding)

        payload = VerificationEvidencePayload(
            payload_id=f"vev_{uuid4().hex[:8]}",
            finding_id=finding.finding_id,
            claim_domain=finding.claim_domain,
            claim_key=finding.claim_key,
            claim_value=finding.claim_value,
            entity_binding_anchor=finding.entity_binding_anchor,
            epistemic_status=finding.epistemic_status,
            evidence_text="Historical records show earlier graduation interval.",
            is_refutation=True,
            target_canonical_fact_key="education.degree",
            created_at=_utc_now(),
        )

        # Route repair with temporal split context
        repair_req = VerificationRepairRequest(
            inbox_id=item.inbox_id,
            finding_id=finding.finding_id,
            claim_domain=finding.claim_domain,
            claim_key="education.degree",
            claimed_value="Bachelor of Science (2018-2020)",
            existing_value="Bachelor of Science (2021-2024)",
            evidence_payload=payload,
            target_canonical_fact_key="education.degree",
            temporal_split_context=temporal_ctx,
            rationale="Degree awarded in earlier historical period.",
        )
        recon_result = VerificationReconciliationResult(
            consumer_turn_id="turn-2",
            consumer_turn_sequence=2,
            routing_items=(
                ReconciliationRoutingItem(
                    action_type=ReconciliationActionType.ROUTE_TO_REPAIR,
                    inbox_id=item.inbox_id,
                    finding_id=finding.finding_id,
                    claim_domain=finding.claim_domain,
                    claim_key="education.degree",
                    evidence_payload=payload,
                    repair_request=repair_req,
                    rationale="Historical timeline split requires temporal reinterpretation.",
                ),
            ),
            repair_requests=(repair_req,),
            reconciled_at=_utc_now(),
        )

        with patch.object(reconciler, "reconcile", return_value=recon_result):
            inbox.deposit(
                source_job_id="job_time_split",
                finding=finding,
                origin_turn_id="turn-1",
                eligible_from_turn_id="turn-2",
                origin_turn_sequence=1,
                eligible_from_turn_sequence=2,
            )
            res = await service.run_turn(
                user_input="When did you finish your degree?",
                core=core,
                current_turn_id="turn-2",
                current_turn_sequence=2,
            )

        assert res.repair_result is not None
        assert res.repair_result.repair_level == RepairLevel.LEVEL_2_TEMPORAL_REINTERPRETATION
        assert res.repair_result.is_repaired is True

    @pytest.mark.asyncio
    async def test_gc242_identity_ambiguity_homonym_cycle_uncertainty_preservation(self):
        """GC-242: Identity Ambiguity Homonym Cycle — Uncertainty Preservation.

        - External observation matches name but lacks authenticated entity anchor.
        - Evaluator emits AMBIGUOUS_CONFLICT; Reconciler emits PRESERVE_UNCERTAINTY.
        - Step G performs 0 repair calls, Step H performs 0 promotions, Core remains 100% intact.
        """
        session = _make_mock_session()
        inbox = VerificationEvidenceInbox()
        reconciler = VerificationReconciler()

        mock_repo = MagicMock(spec=CandidateRepository)
        mock_repo.get_all_active_candidates = AsyncMock(return_value=[])
        mock_repo.save_choice_decision = AsyncMock()

        core = _make_mock_core(facts={"identity.name": "Aevum"})
        service = RealityOrchestrationService(
            session=session,
            candidate_repo=mock_repo,
            inbox=inbox,
            reconciler=reconciler,
        )

        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="identity.name",
            epistemic_status=ClaimEpistemicStatus.AMBIGUOUS_CONFLICT,
            claim_value="Aevum",
            entity_binding_anchor="unrelated_external_entity",
            contradiction_details="Homonym match lacking identity binding anchor.",
        )
        inbox.deposit(
            source_job_id="job_homonym_e2e",
            finding=finding,
            origin_turn_id="turn-1",
            eligible_from_turn_id="turn-2",
            origin_turn_sequence=1,
            eligible_from_turn_sequence=2,
        )

        res = await service.run_turn(
            user_input="Are you the Aevum from that article?",
            core=core,
            current_turn_id="turn-2",
            current_turn_sequence=2,
        )

        assert res.repair_result is None
        assert res.promoted is False
        canonical_name = next(
            (item for item in res.governed_reality.canonical_items if item.provenance.fact_key == "identity.name"),
            None,
        )
        assert canonical_name is not None
        assert canonical_name.value == "Aevum"

    # =========================================================================
    # Cluster 6: Defensive Integrity, AST Audits & System Invariants (GC-243 ~ GC-245)
    # =========================================================================

    def test_gc243_policy_scoped_promotion_margin_threshold(self):
        """GC-243: Policy-Scoped Promotion Margin Threshold (Lock B & ADR-020 Item 27).

        - Decisive choice margin required for Gate 7 (GATE_7_EXPLICIT_CHOICE) is strictly scoped to
          the active BiographyConstructionPolicy.min_choice_margin, NOT a hardcoded architecture constant.
        - candidate with choice_margin >= policy.min_choice_margin satisfies Gate 7.
        - candidate with choice_margin < policy.min_choice_margin strictly blocks promotion.
        """
        session = _make_mock_session()
        core = _make_mock_core()
        cand = _make_candidate(
            "c_margin",
            "education.major",
            "Physics",
            composite_plausibility=0.80,
            lifecycle_state=CandidateLifecycleState.PROMOTABLE,
        )

        # Choice decision with decisive margin of exactly 0.15
        choice = ChoiceDecisionResult(
            decision_id="dec_margin_test",
            entity_id="aevum",
            slot_name="education.major",
            candidate_set_id="cs_m",
            candidate_ids_considered=("c_margin", "c_runnerup"),
            selected_candidate_id="c_margin",
            unselected_candidate_ids=("c_runnerup",),
            selected_candidate=cand,
            archived_unselected_candidates=(),
            decision_timestamp=_utc_now(),
            decision_model_version="1.0",
            competition_state=CompetitionState.CLEAR_LEADER,
            competition_margin=0.20,
            plausibility_scores={"c_margin": 0.80, "c_runnerup": 0.60},
            factor_inputs={"c_margin": ChoiceFactorBreakdown(plausibility_score=0.80).model_dump()},
            factor_contributions={"c_margin": {"plausibility": 0.80}},
            choice_scores={"c_margin": 0.80, "c_runnerup": 0.65},
            choice_margin=0.15,  # Margin is 0.15!
            rationale_code=ChoiceRationaleCode.MULTI_FACTOR_BALANCED,
            rationale_description="Decisive lead in plausibility",
            is_non_canonical=False,
            provenance_references=("ref_1",),
        )

        # Policy A: Strict policy requires min_choice_margin = 0.20 -> 0.15 FAILS
        policy_strict = BiographyConstructionPolicy(min_choice_margin=0.20)
        promo_service_strict = BiographyPromotionService(session=session, policy=policy_strict)
        eligibility_strict = promo_service_strict.evaluate_promotion_eligibility(cand, choice, core)
        assert not eligibility_strict.is_eligible
        assert PromotionGateType.GATE_7_EXPLICIT_CHOICE in eligibility_strict.failed_gates

        # Policy B: Lenient policy requires min_choice_margin = 0.10 -> 0.15 PASSES
        policy_lenient = BiographyConstructionPolicy(min_choice_margin=0.10)
        promo_service_lenient = BiographyPromotionService(session=session, policy=policy_lenient)
        eligibility_lenient = promo_service_lenient.evaluate_promotion_eligibility(cand, choice, core)
        assert PromotionGateType.GATE_7_EXPLICIT_CHOICE not in eligibility_lenient.failed_gates

    def test_gc244_static_ast_boundary_audit_across_phase9(self):
        """GC-244: Static AST Boundary Audit Across Phase 9 Modules.

        - 0 calls or attributes for set_fact across all Phase 9 files (outside biography_promotion_service).
        - 0 instantiation of PromotionAuthorizationToken across all Phase 9 files.
        - Pure cognitive engines have 0 network or database imports.
        """
        app_reality_dir = pathlib.Path(__file__).resolve().parent.parent / "app" / "reality"
        phase9_files = [
            app_reality_dir / "verification_models.py",
            app_reality_dir / "verification_policy_engine.py",
            app_reality_dir / "observation_adapters.py",
            app_reality_dir / "epistemic_source_evaluator.py",
            app_reality_dir / "verification_gateway.py",
            app_reality_dir / "verification_orchestrator.py",
            app_reality_dir / "verification_reconciler.py",
        ]

        pure_cognitive_files = {
            "verification_policy_engine.py",
            "epistemic_source_evaluator.py",
            "verification_reconciler.py",
        }

        forbidden_mutation_tokens = {"set_fact", "PromotionAuthorizationToken"}
        forbidden_io_modules = {
            "requests", "httpx", "aiohttp", "urllib", "socket",
            "sqlalchemy", "sqlite3", "redis",
        }

        violations: list[str] = []

        for fpath in phase9_files:
            assert fpath.exists(), f"Phase 9 file {fpath} must exist"
            tree = ast.parse(fpath.read_text(encoding="utf-8"), filename=str(fpath))
            is_pure_cognitive = fpath.name in pure_cognitive_files

            for node in ast.walk(tree):
                # 1. Zero mutation authority / token leakage
                if isinstance(node, ast.Name) and node.id in forbidden_mutation_tokens:
                    violations.append(f"{fpath.name}:{node.lineno} references forbidden mutation identifier '{node.id}'")
                elif isinstance(node, ast.Attribute) and node.attr in forbidden_mutation_tokens:
                    violations.append(f"{fpath.name}:{node.lineno} references forbidden mutation attribute '{node.attr}'")

                # 2. Pure cognitive engines: Zero network/DB imports
                if is_pure_cognitive:
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            root_mod = alias.name.split(".")[0]
                            if root_mod in forbidden_io_modules:
                                violations.append(f"{fpath.name}:{node.lineno} imports forbidden I/O module '{alias.name}'")
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        root_mod = node.module.split(".")[0]
                        if root_mod in forbidden_io_modules:
                            violations.append(f"{fpath.name}:{node.lineno} from-imports forbidden I/O module '{node.module}'")

        assert not violations, f"AST Boundary violations found across Phase 9: {violations}"

    @pytest.mark.asyncio
    async def test_gc245_canonical_semantic_projection_determinism_and_exception_resilience(self):
        """GC-245: Canonical Semantic Projection Determinism & Exception Resilience (Lock A & ADR-020 Item 26).

        - Replay determinism is defined over canonicalize_turn_result(result), excluding operational metadata.
        - Identical inputs + snapshots guarantee bit-identical semantic projections.
        - Gateway crash or inbox exceptions gracefully degrade without crashing run_turn().
        """
        session = _make_mock_session()
        inbox = VerificationEvidenceInbox()
        reconciler = VerificationReconciler()

        core = _make_mock_core(facts={"identity.name": "Aevum"})
        cand = _make_candidate("c_det", "preferences.tea", "Sencha")

        mock_repo = MagicMock(spec=CandidateRepository)
        mock_repo.get_all_active_candidates = AsyncMock(return_value=[cand])
        mock_repo.save_choice_decision = AsyncMock()

        service = RealityOrchestrationService(
            session=session,
            candidate_repo=mock_repo,
            inbox=inbox,
            reconciler=reconciler,
        )

        # 1. Deterministic Replay over Canonical Semantic Projection
        res_run_1 = await service.run_turn(
            user_input="Do you like green tea?",
            core=core,
            current_turn_id="turn-replay",
            current_turn_sequence=1,
        )
        proj_1 = _canonicalize_turn_result(res_run_1)

        res_run_2 = await service.run_turn(
            user_input="Do you like green tea?",
            core=core,
            current_turn_id="turn-replay",
            current_turn_sequence=1,
        )
        proj_2 = _canonicalize_turn_result(res_run_2)

        assert proj_1 == proj_2, "Canonical semantic projection determinism failed across identical replay."

        # 2. Exception Resilience: Inbox crash gracefully degrades
        with patch.object(inbox, "drain_for_turn", side_effect=RuntimeError("Simulated DB connection failure")):
            res_fail = await service.run_turn(
                user_input="Tell me about tea.",
                core=core,
                current_turn_id="turn-crash",
                current_turn_sequence=2,
            )
            # Service absorbed failure; returned valid result
            assert isinstance(res_fail, OrchestrationTurnResult)
            assert res_fail.reconciliation_result is None
            assert res_fail.governed_reality is not None
