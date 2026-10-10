"""
test_phase95_evidence_reconciliation.py — Phase 9.5 Evidence Reconciliation & Refutation Routing Tests

Gate Checkpoints (GC-95.1 to GC-95.25):
- GC-95.1: WORLD_REALITY findings strictly barred from personal candidate, repair, or promotion pipeline (Lock 21).
- GC-95.2: Reconciler never selects RepairLevel; RealityRepairService evaluates 5-level hierarchy (Lock 22).
- GC-95.3: Candidate exclusion is derived view only; zero candidate lifecycle mutation (Lock 23).
- GC-95.4: Entity binding anchor divergence prevents candidate matching and augmentation (Lock 8 & Lock 24).
- GC-95.5: Strictly typed repair contracts with 0 dict[str, Any] penetration (Lock 25).
- GC-95.6: AMBIGUOUS_CONFLICT preserves uncertainty (zero repair, zero exclusion, zero mutation).
- GC-95.7: Deterministic replay idempotency under identical inputs.
- GC-95.8: Anti-shortcut: supported finding injected into candidate competition view, never canonical reality.
- GC-95.9: Unanchored personal claim cannot propose new candidate hypothesis.
- GC-95.10: VerificationTemporalSplitContext routes to Level 2 Temporal Reinterpretation.
- GC-95.11: VerificationEntityDisambiguationContext routes to Level 4 Re-Anchoring.
- GC-95.12: Unconfirmed candidate refutation routes to Level 3 Fact Invalidation.
- GC-95.13: Unsupported canonical contradiction routes to Level 5 Graceful Uncertainty.
- GC-95.14: Compensatory biography requests are strictly rejected.
- GC-95.15: INSUFFICIENT_EVIDENCE and OUT_OF_SCOPE maintain status quo (NO_ACTION).
- GC-95.16: Physical Temporal Wall compliance in orchestration turn.
- GC-95.17: all_candidates immutability during candidate exclusion.
- GC-95.18: Multi-factor matching requires reality taxonomy alignment.
- GC-95.19: Multi-factor matching requires proposed value alignment.
- GC-95.20: Empty inbox executes clean no-op without affecting turn pipeline.
- GC-95.21: Margin failure in biography promotion blocks canonical mutation.
- GC-95.22: End-to-end multi-turn asynchronous verification to promotion lifecycle.
- GC-95.23: Static AST boundary audit (0 set_fact, 0 token, 0 network, 0 DB in reconciler).
- GC-95.24: Zero floats in reconciliation contract models.
- GC-95.25: Backward compatibility of RealityOrchestrationService with inbox=None.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import pathlib
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.core_models import CharacterCore
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
from app.reality.choice_service import ChoiceSelectionService
from app.reality.competition_service import CandidateCompetitionService
from app.reality.biography_promotion_models import BiographyConstructionPolicy
from app.reality.biography_promotion_service import BiographyPromotionService
from app.reality.models import CoreFactItem, FactAuthority, FactSource, FactStatus
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
    VerificationEvaluationProvenance,
    VerificationEvidencePayload,
    VerificationFinding,
    VerificationInboxItem,
    VerificationScope,
)
from app.reality.verification_orchestrator import VerificationEvidenceInbox
from app.reality.verification_reconciler import (
    ReconciliationActionType,
    ReconciliationRoutingItem,
    VerificationEntityDisambiguationContext,
    VerificationReconciler,
    VerificationReconciliationResult,
    VerificationRepairRequest,
    VerificationTemporalSplitContext,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
                    locked=False,
                )
    return CharacterCore(
        character_id=character_id,
        facts=fact_items,
    )


def _make_candidate(
    candidate_id: str,
    slot_name: str,
    proposed_value: Any,
    entity_id: str = "aevum",
    taxonomy: RealityTaxonomy = RealityTaxonomy.SIMULATED_BIOGRAPHY_FACT,
    composite_plausibility: float = 0.85,
    lifecycle_state: CandidateLifecycleState = CandidateLifecycleState.PERSISTED,
) -> CandidateHypothesis:
    fam = EvidenceFamily(
        family_id=f"fam_{candidate_id}",
        source_type="PREMISE",
        cluster_key=f"{entity_id}.{slot_name}.test",
        mention_count=1,
        session_ids=(),
        first_observed_at=_utc_now(),
        last_observed_at=_utc_now(),
    )
    return CandidateHypothesis(
        candidate_id=candidate_id,
        entity_id=entity_id,
        slot_name=slot_name,
        proposed_value=proposed_value,
        reality_taxonomy=taxonomy,
        inference_depth=0,
        inference_edge_type=InferenceEdgeType.DIRECT_ATTRIBUTE,
        lifecycle_state=lifecycle_state,
        is_quarantined=False,
        quarantine_reason=None,
        plausibility=PlausibilityBreakdown.create(
            prior_weight=composite_plausibility,
            evidence_grounding_score=composite_plausibility,
            coherence_score=composite_plausibility,
            utility_score=composite_plausibility,
            composite_plausibility_score=composite_plausibility,
        ),
        provenance=ProvenanceLineage(
            origin_id=f"stimulus_{candidate_id}",
            evidence_family_ids=(fam.family_id,),
            inference_depth=0,
        ),
        evidence_families=(fam,),
    )


def _make_mock_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalars.return_value.first.return_value = None
    session.execute = AsyncMock(return_value=mock_result)
    session.scalars = AsyncMock(return_value=mock_result.scalars.return_value)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    nested_mock = AsyncMock()
    nested_mock.__aenter__.return_value = nested_mock
    nested_mock.__aexit__.return_value = None
    session.begin_nested = MagicMock(return_value=nested_mock)
    return session


def _make_finding(
    claim_domain: ClaimDomain,
    claim_key: str,
    epistemic_status: ClaimEpistemicStatus,
    claim_value: Optional[Any] = None,
    entity_binding_anchor: Optional[str] = None,
) -> VerificationFinding:
    provenance = VerificationEvaluationProvenance(
        evaluator_name="EpistemicSourceEvaluator",
        evaluator_version="9.3.0",
        evaluated_at=_utc_now(),
        rule_ids_applied=("rule_test",),
        rationale="Test finding",
    )
    return VerificationFinding(
        finding_id=f"find_{uuid4().hex[:8]}",
        request_id=f"req_{uuid4().hex[:8]}",
        claim_domain=claim_domain,
        claim_key=claim_key,
        claim_value=claim_value,
        entity_binding_anchor=entity_binding_anchor,
        epistemic_status=epistemic_status,
        scope=VerificationScope.EXACT_MATCH,
        freshness=EvidenceFreshness.CURRENT,
        contributing_observation_ids=(),
        provenance=provenance,
        contradiction_details=None,
    )


def _make_inbox_item(
    finding: VerificationFinding,
    inbox_id: Optional[str] = None,
    origin_turn_id: str = "turn-1",
    eligible_from_turn_id: str = "turn-2",
    origin_turn_sequence: int = 1,
    eligible_from_turn_sequence: int = 2,
) -> VerificationInboxItem:
    return VerificationInboxItem(
        inbox_id=inbox_id or f"inbox_{uuid4().hex[:8]}",
        source_job_id=f"job_{uuid4().hex[:8]}",
        finding=finding,
        enqueued_at=_utc_now(),
        origin_turn_id=origin_turn_id,
        eligible_from_turn_id=eligible_from_turn_id,
        origin_turn_sequence=origin_turn_sequence,
        eligible_from_turn_sequence=eligible_from_turn_sequence,
        consumed_at=None,
        consumed_by_turn_id=None,
    )


# =============================================================================
# BENCHMARK TESTS: GC-95.1 to GC-95.25
# =============================================================================


class TestPhase95EvidenceReconciliation:
    """Phase 9.5 Evidence Reconciliation & Refutation Routing Test Suite."""

    def test_gc_95_1_world_reality_never_enters_personal_repair(self):
        """GC-95.1: WORLD_REALITY findings strictly barred from personal repair/promotion (Lock 21)."""
        reconciler = VerificationReconciler()
        core = _make_mock_core(facts={"world.capital": "Paris"})
        cand = _make_candidate("c_world", "world.capital", "Paris")

        finding = _make_finding(
            claim_domain=ClaimDomain.WORLD_REALITY,
            claim_key="world.capital",
            epistemic_status=ClaimEpistemicStatus.CONTRADICTED,
            claim_value="Berlin",
            entity_binding_anchor=None,
        )
        item = _make_inbox_item(finding)

        result = reconciler.reconcile([item], core=core, active_candidates=[cand])

        assert len(result.routing_items) == 1
        assert result.routing_items[0].action_type == ReconciliationActionType.NO_ACTION
        assert result.repair_requests == ()
        assert result.candidate_hypotheses_to_inject == ()
        assert result.candidate_ids_to_exclude == ()
        assert "Lock 21" in result.routing_items[0].rationale

    def test_gc_95_2_reconciler_never_selects_repair_level(self):
        """GC-95.2: Reconciler never selects RepairLevel; RealityRepairService evaluates hierarchy (Lock 22)."""
        # 1. Structural check: VerificationRepairRequest has 0 level fields
        assert "repair_level" not in VerificationRepairRequest.model_fields
        assert "recommended_level" not in VerificationRepairRequest.model_fields
        assert "level" not in VerificationRepairRequest.model_fields

        # 2. Reconciler yields factual request without choosing level
        reconciler = VerificationReconciler()
        core = _make_mock_core(facts={"biography.birth_city": "Tokyo"})
        cand = _make_candidate("c_birth", "biography.birth_city", "Tokyo")

        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="biography.birth_city",
            epistemic_status=ClaimEpistemicStatus.CONTRADICTED,
            claim_value="Tokyo",
            entity_binding_anchor="aevum",
        )
        item = _make_inbox_item(finding)

        result = reconciler.reconcile([item], core=core, active_candidates=[cand])
        assert len(result.repair_requests) == 1
        req = result.repair_requests[0]
        assert not hasattr(req, "repair_level")

        # 3. Delegation to RealityRepairService resolves Level 3 because unconfirmed candidate matched
        repair_res = RealityRepairService.repair(
            claim_key=req.claim_key,
            claimed_value=req.claimed_value,
            existing_value=req.existing_value,
            unconfirmed_candidate_id=req.target_candidate_id,
        )
        assert repair_res.repair_level == RepairLevel.LEVEL_3_FACT_INVALIDATION

    def test_gc_95_3_candidate_exclusion_is_derived_view_zero_lifecycle_mutation(self):
        """GC-95.3: Candidate exclusion is derived view only; zero candidate lifecycle mutation (Lock 23)."""
        reconciler = VerificationReconciler()
        core = _make_mock_core()
        cand = _make_candidate(
            "c_excl",
            "education.major",
            "History",
            lifecycle_state=CandidateLifecycleState.PERSISTED,
        )

        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="education.major",
            epistemic_status=ClaimEpistemicStatus.CONTRADICTED,
            claim_value="History",
            entity_binding_anchor="aevum",
        )
        item = _make_inbox_item(finding)

        result = reconciler.reconcile([item], core=core, active_candidates=[cand])

        assert result.candidate_ids_to_exclude == ("c_excl",)
        # Invariant: cand was NOT mutated in-place
        assert cand.lifecycle_state == CandidateLifecycleState.PERSISTED
        assert not cand.is_quarantined

    def test_gc_95_4_different_entity_anchor_strictly_prevents_augmentation(self):
        """GC-95.4: Entity binding anchor divergence prevents candidate matching and augmentation (Lock 8 & 24)."""
        reconciler = VerificationReconciler()
        core = _make_mock_core()
        cand = _make_candidate("c_aevum", "education.major", "Physics", entity_id="aevum")

        # Finding is for another entity anchor
        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="education.major",
            epistemic_status=ClaimEpistemicStatus.SUPPORTED,
            claim_value="Physics",
            entity_binding_anchor="external_subject_bob",
        )
        item = _make_inbox_item(finding)

        result = reconciler.reconcile([item], core=core, active_candidates=[cand])

        # Candidate "c_aevum" must NOT be augmented
        assert "c_aevum" not in result.candidate_ids_to_exclude
        injected_entities = [c.entity_id for c in result.candidate_hypotheses_to_inject]
        assert "aevum" not in injected_entities
        assert "external_subject_bob" in injected_entities

    def test_gc_95_5_strictly_typed_repair_contract_zero_dict_penetration(self):
        """GC-95.5: Strictly typed repair contracts with 0 dict[str, Any] penetration (Lock 25)."""
        assert VerificationTemporalSplitContext.model_config.get("extra") == "forbid"
        assert VerificationEntityDisambiguationContext.model_config.get("extra") == "forbid"
        assert VerificationRepairRequest.model_config.get("extra") == "forbid"

        # Reject arbitrary extra fields on TemporalSplitContext
        with pytest.raises(ValidationError):
            VerificationTemporalSplitContext(
                temporal_relation="SUPERSEDED",
                arbitrary_control_dict={"hack": 123},  # type: ignore[call-arg]
            )

        # Reject arbitrary extra fields on RepairRequest
        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="identity.name",
            epistemic_status=ClaimEpistemicStatus.CONTRADICTED,
        )
        payload = VerificationEvidencePayload(
            payload_id="p_1",
            finding_id=finding.finding_id,
            claim_domain=finding.claim_domain,
            claim_key=finding.claim_key,
            epistemic_status=finding.epistemic_status,
            evidence_text="text",
            created_at=_utc_now(),
        )

        with pytest.raises(ValidationError):
            VerificationRepairRequest(
                inbox_id="inbox_1",
                finding_id=finding.finding_id,
                claim_domain=finding.claim_domain,
                claim_key=finding.claim_key,
                claimed_value="val",
                existing_value="exist",
                evidence_payload=payload,
                rationale="rationale",
                unauthorized_bypass_flag=True,  # type: ignore[call-arg]
            )

    def test_gc_95_6_ambiguous_conflict_preserves_uncertainty(self):
        """GC-95.6: AMBIGUOUS_CONFLICT preserves uncertainty (zero repair, zero exclusion, zero mutation)."""
        reconciler = VerificationReconciler()
        core = _make_mock_core(facts={"identity.alias": "Shadow"})
        cand = _make_candidate("c_alias", "identity.alias", "Shadow")

        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="identity.alias",
            epistemic_status=ClaimEpistemicStatus.AMBIGUOUS_CONFLICT,
            claim_value="Ghost",
            entity_binding_anchor="aevum",
        )
        item = _make_inbox_item(finding)

        result = reconciler.reconcile([item], core=core, active_candidates=[cand])

        assert len(result.routing_items) == 1
        assert result.routing_items[0].action_type == ReconciliationActionType.PRESERVE_UNCERTAINTY
        assert result.repair_requests == ()
        assert result.candidate_ids_to_exclude == ()
        assert result.candidate_hypotheses_to_inject == ()

    def test_gc_95_7_deterministic_replay_idempotency(self):
        """GC-95.7: Deterministic replay idempotency under identical inputs."""
        reconciler = VerificationReconciler()
        core = _make_mock_core(facts={"hobbies.reading": "SciFi"})
        cand = _make_candidate("c_hobby", "hobbies.reading", "SciFi")

        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="hobbies.reading",
            epistemic_status=ClaimEpistemicStatus.SUPPORTED,
            claim_value="SciFi",
            entity_binding_anchor="aevum",
        )
        item = _make_inbox_item(finding)
        fixed_now = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)

        res1 = reconciler.reconcile([item], core=core, active_candidates=[cand], now=fixed_now)
        res2 = reconciler.reconcile([item], core=core, active_candidates=[cand], now=fixed_now)

        assert len(res1.routing_items) == len(res2.routing_items)
        assert res1.routing_items[0].action_type == res2.routing_items[0].action_type
        assert res1.candidate_ids_to_exclude == res2.candidate_ids_to_exclude
        assert len(res1.candidate_hypotheses_to_inject) == len(res2.candidate_hypotheses_to_inject)

    def test_gc_95_8_anti_shortcut_supported_finding_injected_to_competition_not_canonical(self):
        """GC-95.8: Anti-shortcut: supported finding injected into candidate competition view, never canonical reality."""
        reconciler = VerificationReconciler()
        core = _make_mock_core()
        cand = _make_candidate("c_sci", "education.degree", "Bachelor", entity_id="aevum")

        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="education.degree",
            epistemic_status=ClaimEpistemicStatus.SUPPORTED,
            claim_value="Bachelor",
            entity_binding_anchor="aevum",
        )
        item = _make_inbox_item(finding)

        result = reconciler.reconcile([item], core=core, active_candidates=[cand])

        # Augmented candidate is prepared for competition
        assert len(result.candidate_hypotheses_to_inject) == 1
        aug_cand = result.candidate_hypotheses_to_inject[0]
        assert any(f.source_type == "EXTERNAL_VERIFICATION" for f in aug_cand.evidence_families)

        # Canonical reality is untouched
        assert "education.degree" not in core.facts

    def test_gc_95_9_anti_shortcut_unanchored_claim_cannot_propose_candidate(self):
        """GC-95.9: Unanchored personal claim cannot propose new candidate hypothesis."""
        reconciler = VerificationReconciler()
        core = _make_mock_core()

        # No active candidate and anchor is None
        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="music.favorite_genre",
            epistemic_status=ClaimEpistemicStatus.SUPPORTED,
            claim_value="Classical",
            entity_binding_anchor=None,
        )
        item = _make_inbox_item(finding)

        result = reconciler.reconcile([item], core=core, active_candidates=[])

        assert result.routing_items[0].action_type == ReconciliationActionType.NO_ACTION
        assert result.candidate_hypotheses_to_inject == ()

    def test_gc_95_10_temporal_split_context_routes_to_level_2_repair(self):
        """GC-95.10: VerificationTemporalSplitContext routes to Level 2 Temporal Reinterpretation."""
        temporal_ctx = VerificationTemporalSplitContext(
            conflicting_interval=(2018, 2020),
            observed_interval=(2021, 2024),
            temporal_relation="SUPERSEDED",
        )
        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="residence.city",
            epistemic_status=ClaimEpistemicStatus.CONTRADICTED,
            claim_value="London",
            entity_binding_anchor="aevum",
        )
        payload = VerificationEvidencePayload(
            payload_id="p_t",
            finding_id=finding.finding_id,
            claim_domain=finding.claim_domain,
            claim_key=finding.claim_key,
            epistemic_status=finding.epistemic_status,
            evidence_text="text",
            created_at=_utc_now(),
        )
        repair_req = VerificationRepairRequest(
            inbox_id="i_t",
            finding_id=finding.finding_id,
            claim_domain=finding.claim_domain,
            claim_key="residence.city",
            claimed_value="London",
            existing_value="Tokyo",
            evidence_payload=payload,
            temporal_split_context=temporal_ctx,
            rationale="Temporal update observed",
        )

        session = _make_mock_session()
        service = RealityOrchestrationService(session=session)
        repair_res = service._run_verification_repair(repair_req)

        assert repair_res is not None
        assert repair_res.repair_level == RepairLevel.LEVEL_2_TEMPORAL_REINTERPRETATION
        assert repair_res.is_repaired is True

    def test_gc_95_11_entity_disambiguation_context_routes_to_level_4_repair(self):
        """GC-95.11: VerificationEntityDisambiguationContext routes to Level 4 Re-Anchoring."""
        disambig_ctx = VerificationEntityDisambiguationContext(
            canonical_entity_anchor="aevum",
            observed_entity_anchor="aevum_prime",
            ambiguity_reason="NAME_COLLISION",
        )
        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="project.name",
            epistemic_status=ClaimEpistemicStatus.CONTRADICTED,
            claim_value="Project Omega",
            entity_binding_anchor="aevum",
        )
        payload = VerificationEvidencePayload(
            payload_id="p_e",
            finding_id=finding.finding_id,
            claim_domain=finding.claim_domain,
            claim_key=finding.claim_key,
            epistemic_status=finding.epistemic_status,
            evidence_text="text",
            created_at=_utc_now(),
        )
        repair_req = VerificationRepairRequest(
            inbox_id="i_e",
            finding_id=finding.finding_id,
            claim_domain=finding.claim_domain,
            claim_key="project.name",
            claimed_value="Project Omega",
            existing_value="Project Alpha",
            evidence_payload=payload,
            entity_disambiguation_context=disambig_ctx,
            rationale="Entity disambiguation needed",
        )

        session = _make_mock_session()
        service = RealityOrchestrationService(session=session)
        repair_res = service._run_verification_repair(repair_req)

        assert repair_res is not None
        assert repair_res.repair_level == RepairLevel.LEVEL_4_RE_ANCHORING
        assert repair_res.is_repaired is True

    def test_gc_95_12_unconfirmed_candidate_refutation_routes_to_level_3_repair(self):
        """GC-95.12: Unconfirmed candidate refutation routes to Level 3 Fact Invalidation."""
        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="pet.name",
            epistemic_status=ClaimEpistemicStatus.CONTRADICTED,
            claim_value="Unknown",
            entity_binding_anchor="aevum",
        )
        payload = VerificationEvidencePayload(
            payload_id="p_c",
            finding_id=finding.finding_id,
            claim_domain=finding.claim_domain,
            claim_key=finding.claim_key,
            epistemic_status=finding.epistemic_status,
            evidence_text="text",
            created_at=_utc_now(),
        )
        repair_req = VerificationRepairRequest(
            inbox_id="i_c",
            finding_id=finding.finding_id,
            claim_domain=finding.claim_domain,
            claim_key="pet.name",
            claimed_value="Unknown",
            existing_value="Fluffy",
            evidence_payload=payload,
            target_candidate_id="cand_fluffy",
            rationale="Candidate refuted",
        )

        session = _make_mock_session()
        service = RealityOrchestrationService(session=session)
        repair_res = service._run_verification_repair(repair_req)

        assert repair_res is not None
        assert repair_res.repair_level == RepairLevel.LEVEL_3_FACT_INVALIDATION
        assert "cand_fluffy" in repair_res.invalidated_claim_ids

    def test_gc_95_13_canonical_fact_unsupported_refutation_routes_to_level_5_repair(self):
        """GC-95.13: Unsupported canonical contradiction routes to Level 5 Graceful Uncertainty."""
        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="identity.birthplace",
            epistemic_status=ClaimEpistemicStatus.CONTRADICTED,
            claim_value="Berlin",
            entity_binding_anchor="aevum",
        )
        payload = VerificationEvidencePayload(
            payload_id="p_u",
            finding_id=finding.finding_id,
            claim_domain=finding.claim_domain,
            claim_key=finding.claim_key,
            epistemic_status=finding.epistemic_status,
            evidence_text="text",
            created_at=_utc_now(),
        )
        repair_req = VerificationRepairRequest(
            inbox_id="i_u",
            finding_id=finding.finding_id,
            claim_domain=finding.claim_domain,
            claim_key="identity.birthplace",
            claimed_value="Berlin",
            existing_value="Tokyo",
            evidence_payload=payload,
            target_canonical_fact_key="identity.birthplace",
            rationale="Unsupported factual contradiction",
        )

        session = _make_mock_session()
        service = RealityOrchestrationService(session=session)
        repair_res = service._run_verification_repair(repair_req)

        assert repair_res is not None
        assert repair_res.repair_level == RepairLevel.LEVEL_5_GRACEFUL_UNCERTAINTY
        assert repair_res.is_repaired is False

    def test_gc_95_14_compensatory_biography_strictly_rejected(self):
        """GC-95.14: Compensatory biography requests are strictly rejected."""
        repair_res = RealityRepairService.repair(
            claim_key="unknown.lore",
            claimed_value="Secret",
            existing_value="Mystery",
            compensatory_biography_requested=True,
        )
        assert repair_res.repair_level == RepairLevel.LEVEL_5_GRACEFUL_UNCERTAINTY
        assert repair_res.compensatory_biography_created is False

    def test_gc_95_15_insufficient_evidence_and_out_of_scope_maintain_status_quo(self):
        """GC-95.15: INSUFFICIENT_EVIDENCE and OUT_OF_SCOPE maintain status quo (NO_ACTION)."""
        reconciler = VerificationReconciler()
        core = _make_mock_core()

        f1 = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="skill.coding",
            epistemic_status=ClaimEpistemicStatus.INSUFFICIENT_EVIDENCE,
        )
        f2 = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="skill.coding",
            epistemic_status=ClaimEpistemicStatus.OUT_OF_SCOPE,
        )
        items = [_make_inbox_item(f1), _make_inbox_item(f2)]

        result = reconciler.reconcile(items, core=core, active_candidates=[])

        assert len(result.routing_items) == 2
        assert all(r.action_type == ReconciliationActionType.NO_ACTION for r in result.routing_items)
        assert result.candidate_hypotheses_to_inject == ()
        assert result.candidate_ids_to_exclude == ()
        assert result.repair_requests == ()

    @pytest.mark.asyncio
    async def test_gc_95_16_temporal_wall_compliance_in_orchestration_turn(self):
        """GC-95.16: Physical Temporal Wall compliance in orchestration turn."""
        session = _make_mock_session()
        inbox = VerificationEvidenceInbox()
        reconciler = VerificationReconciler()
        service = RealityOrchestrationService(session=session, inbox=inbox, reconciler=reconciler)
        core = _make_mock_core()

        # Finding deposited with origin_turn_id="turn-1", eligible_from_turn_id="turn-2"
        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="academics.degree",
            epistemic_status=ClaimEpistemicStatus.SUPPORTED,
            claim_value="Computer Science",
            entity_binding_anchor="aevum",
        )
        inbox.deposit(
            source_job_id="job_1",
            finding=finding,
            origin_turn_id="turn-1",
            eligible_from_turn_id="turn-2",
            origin_turn_sequence=1,
            eligible_from_turn_sequence=2,
        )

        # Turn 1: Temporal Wall blocks consumption
        res_t1 = await service.run_turn(
            user_input="Hello",
            core=core,
            current_turn_id="turn-1",
            current_turn_sequence=1,
        )
        assert res_t1.reconciliation_result is None

        # Turn 2: Item is consumed and reconciled
        res_t2 = await service.run_turn(
            user_input="Tell me more",
            core=core,
            current_turn_id="turn-2",
            current_turn_sequence=2,
        )
        assert res_t2.reconciliation_result is not None
        assert len(res_t2.reconciliation_result.routing_items) == 1

    @pytest.mark.asyncio
    async def test_gc_95_17_all_candidates_immutability_during_exclusion(self):
        """GC-95.17: all_candidates immutability during candidate exclusion."""
        session = _make_mock_session()
        inbox = VerificationEvidenceInbox()
        reconciler = VerificationReconciler()

        c1 = _make_candidate("c_1", "education.major", "Physics")
        c2 = _make_candidate("c_2", "education.major", "Literature")
        c3 = _make_candidate("c_3", "hobbies.sport", "Tennis")

        # Mock CandidateRepository to return all 3 candidates
        mock_repo = MagicMock(spec=CandidateRepository)
        mock_repo.get_all_active_candidates = AsyncMock(return_value=[c1, c2, c3])
        mock_repo.save_choice_decision = AsyncMock()
        mock_repo.get_biography_promotion_by_candidate = AsyncMock(return_value=None)
        mock_repo.record_biography_promotion = AsyncMock()

        service = RealityOrchestrationService(
            session=session,
            candidate_repo=mock_repo,
            inbox=inbox,
            reconciler=reconciler,
        )
        core = _make_mock_core()

        # Deposit refutation of c2
        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="education.major",
            epistemic_status=ClaimEpistemicStatus.CONTRADICTED,
            claim_value="Literature",
            entity_binding_anchor="aevum",
        )
        inbox.deposit(
            source_job_id="job_c2",
            finding=finding,
            origin_turn_id="turn-0",
            eligible_from_turn_id="turn-1",
            origin_turn_sequence=0,
            eligible_from_turn_sequence=1,
        )

        turn_result = await service.run_turn(
            user_input="Hi",
            core=core,
            current_turn_id="turn-1",
            current_turn_sequence=1,
        )

        # Invariant: all_candidates in turn_result.candidates contains all 3 candidates intact!
        assert len(turn_result.candidates) == 3
        assert {c.candidate_id for c in turn_result.candidates} == {"c_1", "c_2", "c_3"}
        # But reconciliation excluded c2 from turn competition view
        assert turn_result.reconciliation_result is not None
        assert "c_2" in turn_result.reconciliation_result.candidate_ids_to_exclude

    def test_gc_95_18_multi_factor_matching_requires_taxonomy_alignment(self):
        """GC-95.18: Multi-factor matching requires reality taxonomy alignment."""
        reconciler = VerificationReconciler()
        core = _make_mock_core()
        cand = _make_candidate(
            "c_tax",
            "fact.test",
            "Value",
            taxonomy=RealityTaxonomy.OBJECTIVE_WORLD_FACT,
        )

        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="fact.test",
            epistemic_status=ClaimEpistemicStatus.SUPPORTED,
            claim_value="Value",
            entity_binding_anchor="aevum",
        )
        item = _make_inbox_item(finding)

        result = reconciler.reconcile([item], core=core, active_candidates=[cand])

        # Candidate was NOT matched because taxonomy != SIMULATED_BIOGRAPHY_FACT
        assert "c_tax" not in result.candidate_ids_to_exclude

    def test_gc_95_19_multi_factor_matching_requires_value_alignment(self):
        """GC-95.19: Multi-factor matching requires proposed value alignment."""
        reconciler = VerificationReconciler()
        core = _make_mock_core()
        cand = _make_candidate("c_val", "residence.city", "Kyoto")

        # Finding is for Tokyo, candidate is for Kyoto
        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="residence.city",
            epistemic_status=ClaimEpistemicStatus.SUPPORTED,
            claim_value="Tokyo",
            entity_binding_anchor="aevum",
        )
        item = _make_inbox_item(finding)

        result = reconciler.reconcile([item], core=core, active_candidates=[cand])

        # Candidate was NOT matched
        assert "c_val" not in result.candidate_ids_to_exclude

    @pytest.mark.asyncio
    async def test_gc_95_20_empty_inbox_clean_noop(self):
        """GC-95.20: Empty inbox executes clean no-op without affecting turn pipeline."""
        session = _make_mock_session()
        inbox = VerificationEvidenceInbox()
        reconciler = VerificationReconciler()
        service = RealityOrchestrationService(session=session, inbox=inbox, reconciler=reconciler)
        core = _make_mock_core()

        result = await service.run_turn(
            user_input="Normal conversation",
            core=core,
            current_turn_id="turn-5",
            current_turn_sequence=5,
        )
        assert result.reconciliation_result is None
        assert result.governed_reality is not None

    @pytest.mark.asyncio
    async def test_gc_95_21_margin_failure_in_biography_promotion_blocks_canonical_mutation(self):
        """GC-95.21: Margin failure in biography promotion blocks canonical mutation (Gate 4)."""
        session = _make_mock_session()
        core = _make_mock_core()
        promo_service = BiographyPromotionService(session=session)

        cand = _make_candidate(
            "c_close",
            "education.major",
            "Physics",
            composite_plausibility=0.80,
            lifecycle_state=CandidateLifecycleState.PROMOTABLE,
        )

        # Choice decision with choice_margin < 0.02 (violates Gate 7)
        choice = ChoiceDecisionResult(
            decision_id="dec_margin_fail",
            entity_id="aevum",
            slot_name="education.major",
            candidate_set_id="cs_1",
            candidate_ids_considered=("c_close", "c_runnerup"),
            selected_candidate_id="c_close",
            unselected_candidate_ids=("c_runnerup",),
            selected_candidate=cand,
            archived_unselected_candidates=(),
            decision_timestamp=_utc_now(),
            decision_model_version="1.0",
            competition_state=CompetitionState.CLEAR_LEADER,
            competition_margin=0.08,
            plausibility_scores={"c_close": 0.80, "c_runnerup": 0.72},
            factor_inputs={"c_close": ChoiceFactorBreakdown(plausibility_score=0.80).model_dump()},
            factor_contributions={"c_close": {"plausibility": 0.80}},
            choice_scores={"c_close": 0.80, "c_runnerup": 0.795},
            choice_margin=0.005,  # < min_choice_margin (0.02) !
            rationale_code=ChoiceRationaleCode.MULTI_FACTOR_BALANCED,
            rationale_description="Close choice margin",
            is_non_canonical=False,
            provenance_references=("ref_1",),
        )

        eligibility = promo_service.evaluate_promotion_eligibility(cand, choice, core)
        assert not eligibility.is_eligible
        from app.reality.biography_promotion_models import PromotionGateType
        assert PromotionGateType.GATE_7_EXPLICIT_CHOICE in eligibility.failed_gates

    @pytest.mark.asyncio
    async def test_gc_95_22_end_to_end_multi_turn_lifecycle(self):
        """GC-95.22: End-to-end multi-turn asynchronous verification to promotion lifecycle."""
        session = _make_mock_session()
        inbox = VerificationEvidenceInbox()
        reconciler = VerificationReconciler()

        cand = _make_candidate(
            "c_deg",
            "education.degree",
            "Computer Science",
            composite_plausibility=0.90,
        )

        mock_repo = MagicMock(spec=CandidateRepository)
        mock_repo.get_all_active_candidates = AsyncMock(return_value=[cand])
        mock_repo.save_choice_decision = AsyncMock()
        mock_repo.get_biography_promotion_by_candidate = AsyncMock(return_value=None)
        mock_repo.record_biography_promotion = AsyncMock()

        service = RealityOrchestrationService(
            session=session,
            candidate_repo=mock_repo,
            inbox=inbox,
            reconciler=reconciler,
        )
        core = _make_mock_core()

        # Turn 1: External observation completes and is deposited for Turn 2
        finding = _make_finding(
            claim_domain=ClaimDomain.PERSONAL_REALITY,
            claim_key="education.degree",
            epistemic_status=ClaimEpistemicStatus.SUPPORTED,
            claim_value="Computer Science",
            entity_binding_anchor="aevum",
        )
        inbox.deposit(
            source_job_id="job_e2e",
            finding=finding,
            origin_turn_id="turn-1",
            eligible_from_turn_id="turn-2",
            origin_turn_sequence=1,
            eligible_from_turn_sequence=2,
        )

        # Turn 1: Temporal wall stops consumption
        t1_res = await service.run_turn(
            user_input="Did you study CS?",
            core=core,
            current_turn_id="turn-1",
            current_turn_sequence=1,
        )
        assert t1_res.reconciliation_result is None

        # Turn 2: Finding is drained and reconciles
        t2_res = await service.run_turn(
            user_input="Tell me about your studies.",
            core=core,
            current_turn_id="turn-2",
            current_turn_sequence=2,
        )
        assert t2_res.reconciliation_result is not None
        assert len(t2_res.reconciliation_result.candidate_hypotheses_to_inject) == 1
        aug_cand = t2_res.reconciliation_result.candidate_hypotheses_to_inject[0]
        assert any(f.source_type == "EXTERNAL_VERIFICATION" for f in aug_cand.evidence_families)

    def test_gc_95_23_reconciler_static_ast_boundary_audit(self):
        """GC-95.23: Static AST boundary audit (0 set_fact, 0 token, 0 network, 0 DB in reconciler)."""
        reconciler_path = pathlib.Path("app/reality/verification_reconciler.py")
        assert reconciler_path.exists(), "verification_reconciler.py must exist"

        tree = ast.parse(reconciler_path.read_text(encoding="utf-8"))

        forbidden_names = {
            "set_fact",
            "PromotionAuthorizationToken",
            "requests",
            "httpx",
            "aiohttp",
            "urllib",
            "sqlite3",
            "sqlalchemy",
        }

        found_violations: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden_names:
                found_violations.append(f"Forbidden name '{node.id}' at line {node.lineno}")
            elif isinstance(node, ast.Attribute) and node.attr in forbidden_names:
                found_violations.append(f"Forbidden attribute '{node.attr}' at line {node.lineno}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden_names:
                        found_violations.append(f"Forbidden import '{alias.name}' at line {node.lineno}")
            elif isinstance(node, ast.ImportFrom):
                if node.module in forbidden_names:
                    found_violations.append(f"Forbidden from-import '{node.module}' at line {node.lineno}")

        assert not found_violations, f"AST Boundary violations found in verification_reconciler.py: {found_violations}"

    def test_gc_95_24_zero_floats_in_reconciliation_contracts(self):
        """GC-95.24: Zero floats in reconciliation contract models."""
        models_to_check = [
            VerificationTemporalSplitContext,
            VerificationEntityDisambiguationContext,
            VerificationRepairRequest,
            ReconciliationRoutingItem,
            VerificationReconciliationResult,
        ]

        for model in models_to_check:
            for field_name, field_info in model.model_fields.items():
                annotation_str = str(field_info.annotation)
                assert "float" not in annotation_str.lower(), (
                    f"Model {model.__name__} field '{field_name}' contains float: {annotation_str}"
                )

    @pytest.mark.asyncio
    async def test_gc_95_25_orchestration_turn_result_backward_compatibility(self):
        """GC-95.25: Backward compatibility of RealityOrchestrationService with inbox=None."""
        session = _make_mock_session()
        # Default initialization: inbox=None, reconciler=None
        service = RealityOrchestrationService(session=session)
        core = _make_mock_core()

        result = await service.run_turn(
            user_input="Hello world",
            core=core,
        )

        assert isinstance(result, OrchestrationTurnResult)
        assert result.reconciliation_result is None
        assert result.governed_reality is not None
