"""Phase 14.4 — Adaptive Belief Revision Engine Tests.

Tests cover:
  1. DTO immutability (frozen=True, extra="forbid")
  2. Revision taxonomy (CONFIRMATION, PARTIAL_CONFIRMATION, CONTRADICTION, SUPERSESSION, EXPIRY)
  3. BeliefRevisionRepository (Lock 4 append-only audit trail & Decision D4 bounded context retrieval)
  4. AdaptiveBeliefRevisionEngine evaluation:
     - Exact match -> CONFIRMATION
     - Substring/partial match -> PARTIAL_CONFIRMATION
     - Definitive replacement -> SUPERSESSION (Lock 4)
     - Contradiction without replacement -> CONTRADICTION
     - Lock 11: Candidate != Evidence rejection
     - Lock 8: Canonical fact demotion protection
  5. BeliefReconciliationService (atomic state transition & audit recording)
  6. Authority boundary AST audit (0 set_fact, 0 token minting)

Golden Suite 14 Cluster 4: GC-367 ~ GC-371 (5 constitutional acceptance benchmarks)
"""

import ast
from pathlib import Path
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock
import pytest
from pydantic import ValidationError

from app.character.core_models import CharacterCore
from app.reality.belief_revision import (
    AdaptiveBeliefRevisionEngine,
    BeliefReconciliationService,
    BeliefRevisionKind,
    BeliefRevisionProposal,
    BeliefRevisionRecord,
    BeliefRevisionRepository,
    EvidenceSourceType,
    IncomingEvidenceItem,
)
from app.reality.candidate_models import (
    CandidateHypothesis,
    CandidateLifecycleState,
    InferenceEdgeType,
    PlausibilityBreakdown,
    ProvenanceLineage,
    RealityTaxonomy,
)
from app.reality.models import CoreFactItem, FactAuthority, FactSource, FactStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_candidate(
    cid: str,
    slot: str = "education.major",
    val: str = "Computer Science",
    lifecycle: CandidateLifecycleState = CandidateLifecycleState.ACTIVE,
) -> CandidateHypothesis:
    plausibility = PlausibilityBreakdown.create(
        prior_weight=0.5,
        evidence_grounding_score=0.8,
        coherence_score=0.9,
        utility_score=0.7,
        composite_plausibility_score=0.75,
    )
    provenance = ProvenanceLineage(
        origin_id="test_origin",
        parent_candidate_ids=(),
        evidence_family_ids=(),
        inference_depth=1,
        derivation_path=("test",),
    )
    return CandidateHypothesis(
        candidate_id=cid,
        entity_id="aevum",
        slot_name=slot,
        proposed_value=val,
        reality_taxonomy=RealityTaxonomy.SIMULATED_BIOGRAPHY_FACT,
        inference_depth=1,
        inference_edge_type=InferenceEdgeType.BEHAVIORAL_CORRELATE,
        plausibility=plausibility,
        provenance=provenance,
        evidence_families=(),
        lifecycle_state=lifecycle,
        is_quarantined=False,
    )


def _make_core(
    facts_dict: dict[str, tuple[Any, bool]],  # key -> (value, is_locked)
) -> CharacterCore:
    facts = {}
    for k, (val, locked) in facts_dict.items():
        category = k.split(".")[0]
        authority = FactAuthority.USER_LOCKED if locked else FactAuthority.AEVUM_CANONICAL
        facts[k] = CoreFactItem(
            key=k,
            value=val,
            category=category,
            source=FactSource.SYSTEM_BASELINE,
            authority=authority,
            status=FactStatus.CANONICAL,
            locked=locked,
        )
    return CharacterCore(character_id="aevum", facts=facts)


# ---------------------------------------------------------------------------
# 1. DTO Immutability
# ---------------------------------------------------------------------------

class TestRevisionDTOImmutability:
    """Gate 1: All revision DTOs are frozen and reject extra fields."""

    def test_belief_revision_record_is_frozen(self):
        rec = BeliefRevisionRecord(
            revision_id="rev-1",
            slot_name="education.major",
            revision_kind=BeliefRevisionKind.CONFIRMATION,
            prior_value="Computer Science",
            revised_value="Computer Science",
            trigger_cycle_id="cycle-1",
            rationale="Confirmed by user statement",
        )
        with pytest.raises(Exception):
            rec.prior_value = "Mutated"  # type: ignore[misc]

    def test_belief_revision_record_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            BeliefRevisionRecord(
                revision_id="rev-1",
                slot_name="education.major",
                revision_kind=BeliefRevisionKind.CONFIRMATION,
                trigger_cycle_id="cycle-1",
                rationale="Confirmed",
                extra_forbidden_field="injection",  # type: ignore[call-arg]
            )

    def test_incoming_evidence_item_is_frozen(self):
        ev = IncomingEvidenceItem(
            evidence_id="ev-1",
            source_type=EvidenceSourceType.USER_STATEMENT,
            slot_name="education.major",
            asserted_value="Computer Science",
        )
        with pytest.raises(Exception):
            ev.confidence = 0.5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 2. Revision Taxonomy
# ---------------------------------------------------------------------------

class TestRevisionTaxonomy:
    """Gate 2: All 5 BeliefRevisionKind enum values exist and are distinct."""

    def test_all_five_revision_kinds_exist(self):
        kinds = {k.value for k in BeliefRevisionKind}
        assert kinds == {
            "CONFIRMATION",
            "PARTIAL_CONFIRMATION",
            "CONTRADICTION",
            "SUPERSESSION",
            "EXPIRY",
        }


# ---------------------------------------------------------------------------
# 3. BeliefRevisionRepository (Lock 4, Decision D4)
# ---------------------------------------------------------------------------

class TestBeliefRevisionRepository:
    """Gate 3: Append-only audit trail and bounded context retrieval."""

    def test_append_and_query_history(self):
        repo = BeliefRevisionRepository()
        assert repo.count() == 0

        rec1 = BeliefRevisionRecord(
            revision_id="r1",
            slot_name="education.major",
            revision_kind=BeliefRevisionKind.CONFIRMATION,
            trigger_cycle_id="c1",
            rationale="r1",
        )
        rec2 = BeliefRevisionRecord(
            revision_id="r2",
            slot_name="lifestyle.transit",
            revision_kind=BeliefRevisionKind.SUPERSESSION,
            trigger_cycle_id="c2",
            rationale="r2",
        )

        repo.append(rec1)
        repo.append(rec2)
        assert repo.count() == 2

        major_history = repo.get_history(slot_name="education.major")
        assert len(major_history) == 1
        assert major_history[0].revision_id == "r1"

    def test_bounded_context_retrieval(self):
        """Decision D4: Prompt retrieval is strictly bounded (get_recent, default limit=5)."""
        repo = BeliefRevisionRepository()
        # Add 10 records
        for i in range(10):
            repo.append(
                BeliefRevisionRecord(
                    revision_id=f"r{i}",
                    slot_name="education.major",
                    revision_kind=BeliefRevisionKind.CONFIRMATION,
                    trigger_cycle_id=f"c{i}",
                    rationale=f"test {i}",
                )
            )

        # Context retrieval bounded to 5 by default
        recent = repo.get_recent(limit=5)
        assert len(recent) == 5
        # Must return the 5 most recent records
        assert [r.revision_id for r in recent] == ["r5", "r6", "r7", "r8", "r9"]


# ---------------------------------------------------------------------------
# 4. AdaptiveBeliefRevisionEngine Evaluation Tests
# ---------------------------------------------------------------------------

class TestAdaptiveBeliefRevisionEngine:
    """Gate 4: Pure evaluation of belief revisions under constitutional locks."""

    def test_exact_match_produces_confirmation(self):
        engine = AdaptiveBeliefRevisionEngine()
        cand = _make_candidate("cand-1", val="Computer Science")
        ev = IncomingEvidenceItem(
            evidence_id="ev-1",
            source_type=EvidenceSourceType.USER_STATEMENT,
            slot_name="education.major",
            asserted_value="Computer Science",
        )

        proposal = engine.evaluate_revision(cand, ev)
        assert proposal.is_valid_revision is True
        assert proposal.revision_kind == BeliefRevisionKind.CONFIRMATION
        assert proposal.target_lifecycle_state == CandidateLifecycleState.ACTIVE
        assert proposal.record is not None
        assert proposal.record.revised_value == "Computer Science"

    def test_partial_match_produces_partial_confirmation(self):
        engine = AdaptiveBeliefRevisionEngine()
        cand = _make_candidate("cand-1", val="Computer Science")
        ev = IncomingEvidenceItem(
            evidence_id="ev-1",
            source_type=EvidenceSourceType.USER_STATEMENT,
            slot_name="education.major",
            asserted_value="Computer Science and Engineering",
        )

        proposal = engine.evaluate_revision(cand, ev)
        assert proposal.is_valid_revision is True
        assert proposal.revision_kind == BeliefRevisionKind.PARTIAL_CONFIRMATION
        assert proposal.target_lifecycle_state == CandidateLifecycleState.ACTIVE

    def test_definitive_contradiction_produces_supersession(self):
        """Lock 4: Definitive replacement transitions prior candidate to SUPERSEDED."""
        engine = AdaptiveBeliefRevisionEngine()
        cand = _make_candidate("cand-1", val="Software Engineering")
        ev = IncomingEvidenceItem(
            evidence_id="ev-1",
            source_type=EvidenceSourceType.USER_STATEMENT,
            slot_name="education.major",
            asserted_value="Artificial Intelligence",
            is_definitive_replacement=True,
        )

        proposal = engine.evaluate_revision(cand, ev)
        assert proposal.is_valid_revision is True
        assert proposal.revision_kind == BeliefRevisionKind.SUPERSESSION
        assert proposal.target_lifecycle_state == CandidateLifecycleState.SUPERSEDED
        assert proposal.record is not None
        assert proposal.record.prior_value == "Software Engineering"
        assert proposal.record.revised_value == "Artificial Intelligence"

    def test_contradiction_without_replacement_produces_rejection(self):
        engine = AdaptiveBeliefRevisionEngine()
        cand = _make_candidate("cand-1", val="Software Engineering")
        ev = IncomingEvidenceItem(
            evidence_id="ev-1",
            source_type=EvidenceSourceType.USER_STATEMENT,
            slot_name="education.major",
            asserted_value="Definitely not engineering",
            is_definitive_replacement=False,
        )

        proposal = engine.evaluate_revision(cand, ev)
        assert proposal.is_valid_revision is True
        assert proposal.revision_kind == BeliefRevisionKind.CONTRADICTION
        assert proposal.target_lifecycle_state == CandidateLifecycleState.REJECTED

    def test_lock_11_candidate_hypothesis_rejected_as_evidence(self):
        """Lock 11: CandidateHypothesis cannot serve as evidence for belief revision."""
        engine = AdaptiveBeliefRevisionEngine()
        cand = _make_candidate("cand-1", val="Computer Science")
        ev = IncomingEvidenceItem(
            evidence_id="ev-hypo",
            source_type=EvidenceSourceType.CANDIDATE_HYPOTHESIS,
            slot_name="education.major",
            asserted_value="Data Science",
        )

        proposal = engine.evaluate_revision(cand, ev)
        assert proposal.is_valid_revision is False
        assert "LOCK_11_CANDIDATE_NOT_EVIDENCE" in (proposal.rejection_reason or "")

    def test_lock_8_canonical_demotion_rejected(self):
        """Lock 8: An existing CANONICAL fact cannot be demoted by autonomous revision."""
        engine = AdaptiveBeliefRevisionEngine()
        # Canonical fact is currently "Universiti Malaya"
        core = _make_core({"education.university": ("Universiti Malaya", False)})

        cand = _make_candidate("cand-uni", slot="education.university", val="Universiti Malaya")
        ev = IncomingEvidenceItem(
            evidence_id="ev-uni",
            source_type=EvidenceSourceType.USER_STATEMENT,
            slot_name="education.university",
            asserted_value="Harvard University",
            is_definitive_replacement=True,
        )

        proposal = engine.evaluate_revision(cand, ev, core=core)
        assert proposal.is_valid_revision is False
        assert "LOCK_8_CANONICAL_DEMOTION_BLOCKED" in (proposal.rejection_reason or "")

    def test_slot_mismatch_rejected(self):
        engine = AdaptiveBeliefRevisionEngine()
        cand = _make_candidate("cand-1", slot="education.major")
        ev = IncomingEvidenceItem(
            evidence_id="ev-1",
            source_type=EvidenceSourceType.USER_STATEMENT,
            slot_name="education.year",  # Different slot
            asserted_value=2,
        )

        proposal = engine.evaluate_revision(cand, ev)
        assert proposal.is_valid_revision is False
        assert "Slot mismatch" in (proposal.rejection_reason or "")


# ---------------------------------------------------------------------------
# 5. BeliefReconciliationService Tests
# ---------------------------------------------------------------------------

class TestBeliefReconciliationService:
    """Gate 5: Non-destructive state transition and permanent audit logging."""

    @pytest.mark.asyncio
    async def test_apply_supersession_persists_record_and_updates_lifecycle(self):
        """Lock 4: Prior candidate transitioned to SUPERSEDED, preserved in audit trail."""
        rev_repo = BeliefRevisionRepository()
        cand_repo = AsyncMock()

        service = BeliefReconciliationService(
            revision_repo=rev_repo,
            candidate_repo=cand_repo,
        )

        cand = _make_candidate("cand-old", val="Mechanical Engineering")
        rec = BeliefRevisionRecord(
            revision_id="rev-super",
            slot_name="education.major",
            revision_kind=BeliefRevisionKind.SUPERSESSION,
            prior_value="Mechanical Engineering",
            revised_value="Computer Engineering",
            prior_candidate_id="cand-old",
            trigger_cycle_id="cycle-42",
            rationale="Definitive user confirmation",
        )
        proposal = BeliefRevisionProposal(
            is_valid_revision=True,
            revision_kind=BeliefRevisionKind.SUPERSESSION,
            record=rec,
            target_lifecycle_state=CandidateLifecycleState.SUPERSEDED,
        )

        res = await service.apply_revision(cand, proposal)
        assert res is not None
        assert res.revision_id == "rev-super"

        # 1. Audit record permanently stored
        assert rev_repo.count() == 1
        stored = rev_repo.get_history()[0]
        assert stored.revision_kind == BeliefRevisionKind.SUPERSESSION
        assert stored.prior_value == "Mechanical Engineering"
        assert stored.revised_value == "Computer Engineering"

        # 2. Prior candidate transitioned to SUPERSEDED (never deleted!)
        cand_repo.update_lifecycle_state.assert_called_once_with(
            candidate_id="cand-old",
            new_state=CandidateLifecycleState.SUPERSEDED,
        )

    @pytest.mark.asyncio
    async def test_refuses_invalid_proposal(self):
        rev_repo = BeliefRevisionRepository()
        cand_repo = AsyncMock()
        service = BeliefReconciliationService(revision_repo=rev_repo, candidate_repo=cand_repo)

        cand = _make_candidate("cand-1")
        proposal = BeliefRevisionProposal(
            is_valid_revision=False,
            revision_kind=BeliefRevisionKind.CONTRADICTION,
            rejection_reason="Invalid",
        )

        res = await service.apply_revision(cand, proposal)
        assert res is None
        assert rev_repo.count() == 0
        cand_repo.update_lifecycle_state.assert_not_called()


# ---------------------------------------------------------------------------
# 6. Authority Boundary AST Audit
# ---------------------------------------------------------------------------

class TestBeliefRevisionAuthorityBoundary:
    """Gate 6: belief_revision.py must not reference forbidden mutation calls."""

    _FORBIDDEN_NAMES = {
        "set_fact",
        "PromotionAuthorizationToken",
    }

    def _load_ast(self) -> ast.Module:
        path = Path(__file__).parent.parent / "app" / "reality" / "belief_revision.py"
        return ast.parse(path.read_text(encoding="utf-8"))

    def test_no_forbidden_mutation_calls(self):
        tree = self._load_ast()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in self._FORBIDDEN_NAMES:
                pytest.fail(f"Forbidden name '{node.id}' in belief_revision.py AST")
            elif isinstance(node, ast.Attribute) and node.attr in self._FORBIDDEN_NAMES:
                pytest.fail(f"Forbidden attribute '{node.attr}' in belief_revision.py AST")


# ---------------------------------------------------------------------------
# 7. Golden Suite 14 — Cluster 4: GC-367 ~ GC-371
# ---------------------------------------------------------------------------

class TestGoldenSuite14Cluster4:
    """GC-367 ~ GC-371 — Constitutional acceptance benchmarks for Phase 14.4."""

    @pytest.mark.asyncio
    async def test_gc367_non_destructive_belief_revision(self):
        """GC-367: Non-destructive revision transitions prior candidate to SUPERSEDED."""
        rev_repo = BeliefRevisionRepository()
        cand_repo = AsyncMock()
        service = BeliefReconciliationService(revision_repo=rev_repo, candidate_repo=cand_repo)

        cand = _make_candidate("gc367-cand", val="History")
        rec = BeliefRevisionRecord(
            revision_id="rev-gc367",
            slot_name="education.major",
            revision_kind=BeliefRevisionKind.SUPERSESSION,
            prior_value="History",
            revised_value="Linguistics",
            prior_candidate_id="gc367-cand",
            trigger_cycle_id="cycle-gc",
            rationale="Revision test",
        )
        prop = BeliefRevisionProposal(
            is_valid_revision=True,
            revision_kind=BeliefRevisionKind.SUPERSESSION,
            record=rec,
            target_lifecycle_state=CandidateLifecycleState.SUPERSEDED,
        )

        await service.apply_revision(cand, prop)
        # Verify candidate transitioned to SUPERSEDED, not deleted
        cand_repo.update_lifecycle_state.assert_called_once_with(
            candidate_id="gc367-cand",
            new_state=CandidateLifecycleState.SUPERSEDED,
        )
        assert rev_repo.count() == 1

    def test_gc368_candidate_not_evidence_lock_11(self):
        """GC-368: CandidateHypothesis cannot serve as evidence for belief revision."""
        engine = AdaptiveBeliefRevisionEngine()
        cand = _make_candidate("gc368-cand", val="Law")
        ev = IncomingEvidenceItem(
            evidence_id="ev-gc368",
            source_type=EvidenceSourceType.CANDIDATE_HYPOTHESIS,
            slot_name="education.major",
            asserted_value="Medicine",
        )
        prop = engine.evaluate_revision(cand, ev)
        assert prop.is_valid_revision is False
        assert "LOCK_11_CANDIDATE_NOT_EVIDENCE" in (prop.rejection_reason or "")

    def test_gc369_canonical_fact_demotion_protection_lock_8(self):
        """GC-369: Canonical fact cannot be demoted by autonomous belief revision."""
        engine = AdaptiveBeliefRevisionEngine()
        core = _make_core({"education.level": ("Undergraduate", False)})
        cand = _make_candidate("gc369-cand", slot="education.level", val="Undergraduate")
        ev = IncomingEvidenceItem(
            evidence_id="ev-gc369",
            source_type=EvidenceSourceType.USER_STATEMENT,
            slot_name="education.level",
            asserted_value="High School",
            is_definitive_replacement=True,
        )
        prop = engine.evaluate_revision(cand, ev, core=core)
        assert prop.is_valid_revision is False
        assert "LOCK_8_CANONICAL_DEMOTION_BLOCKED" in (prop.rejection_reason or "")

    def test_gc370_permanent_repository_with_bounded_context(self):
        """GC-370: Append-only storage is permanent; prompt context retrieval is bounded."""
        repo = BeliefRevisionRepository()
        for i in range(8):
            repo.append(
                BeliefRevisionRecord(
                    revision_id=f"r{i}",
                    slot_name="education.major",
                    revision_kind=BeliefRevisionKind.CONFIRMATION,
                    trigger_cycle_id="c",
                    rationale=f"test {i}",
                )
            )
        assert repo.count() == 8
        recent = repo.get_recent(limit=5)
        assert len(recent) == 5

    def test_gc371_authority_boundary_zero_forbidden_symbols(self):
        """GC-371: belief_revision.py has 0 references to set_fact or token minting."""
        path = Path(__file__).parent.parent / "app" / "reality" / "belief_revision.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden = {"set_fact", "PromotionAuthorizationToken"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden:
                pytest.fail(f"Forbidden name '{node.id}' in belief_revision.py AST")
            elif isinstance(node, ast.Attribute) and node.attr in forbidden:
                pytest.fail(f"Forbidden attribute '{node.attr}' in belief_revision.py AST")
