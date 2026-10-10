"""Phase 14.5 — Context Assembly & Belief Transparency Layer Tests.

Tests cover:
  1. DTO immutability (frozen=True, extra="forbid") on BeliefTransparencyItem & BeliefTransparencyState
  2. BeliefMaturity enum taxonomy (CONSTRUCTING, EMERGING, ESTABLISHED)
  3. Three Orthogonal Axes independence:
     CanonicalStatus (Truth) × RecallLevel (Clarity) × BeliefMaturity (Maturity)
  4. BeliefMaturityClassifier evaluation & Lock 10 enforcement:
     - Provisional single-cycle candidate -> CONSTRUCTING
     - Provisional with decisive margin or multi-cycle -> EMERGING
     - Newly promoted canonical fact (1 cycle) -> EMERGING
     - Established canonical fact (>=2 cycles, >=2 evidence, stable) -> ESTABLISHED
     - Lock 10 Invariant: 100 cycles alone without multi-evidence -> NOT ESTABLISHED
     - Evidence unstable / Disputed -> CONSTRUCTING
  5. Helper conversion methods (item_from_candidate, item_from_canonical_fact)
  6. Decision D3: CONSTRUCTING is epistemic state, zero prescribed utterance templates
  7. Decision D4: Bounded context retrieval (max 5 recent revisions)
  8. XML Context Assembly & Replay Determinism (<autonomous_belief_state>)
  9. Pure Read Projection & AST Boundary Audit (0 set_fact, 0 token minting)

Golden Suite 14 Cluster 5: GC-372 ~ GC-376 (5 constitutional acceptance benchmarks)
"""

import ast
from pathlib import Path
from typing import Any
import pytest
from pydantic import ValidationError

from app.biography.biography_models import CanonicalStatus, RecallLevel
from app.reality.belief_revision import BeliefRevisionKind, BeliefRevisionRecord
from app.reality.belief_transparency import (
    BeliefMaturity,
    BeliefMaturityClassifier,
    BeliefTransparencyAdapter,
    BeliefTransparencyItem,
    BeliefTransparencyState,
)
from app.reality.candidate_models import (
    CandidateHypothesis,
    CandidateLifecycleState,
    InferenceEdgeType,
    PlausibilityBreakdown,
    ProvenanceLineage,
    RealityTaxonomy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_candidate(
    cid: str,
    slot: str = "education.major",
    val: str = "Computer Science",
    evidence_count: int = 1,
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
        lifecycle_state=CandidateLifecycleState.ACTIVE,
        is_quarantined=False,
    )


def _make_revision_record(rid: str, slot: str = "education.major") -> BeliefRevisionRecord:
    return BeliefRevisionRecord(
        revision_id=rid,
        slot_name=slot,
        revision_kind=BeliefRevisionKind.CONFIRMATION,
        prior_value="Old Major",
        revised_value="New Major",
        trigger_cycle_id="cycle-1",
        rationale="Unit test revision",
    )


# ---------------------------------------------------------------------------
# 1. DTO Immutability & Validation Tests
# ---------------------------------------------------------------------------

class TestBeliefTransparencyDTOs:
    """Verifies DTO immutability and schema constraints."""

    def test_belief_transparency_item_immutability(self):
        """Item is frozen and rejects mutation."""
        item = BeliefTransparencyItem(
            slot_name="education.major",
            asserted_value="Literature",
            canonical_status=CanonicalStatus.PROVISIONAL,
            recall_level=RecallLevel.VIVID,
            belief_maturity=BeliefMaturity.CONSTRUCTING,
            cycles_observed=1,
            evidence_count=1,
        )
        with pytest.raises(ValidationError):
            item.belief_maturity = BeliefMaturity.ESTABLISHED  # type: ignore

    def test_belief_transparency_item_extra_forbid(self):
        """Item rejects extra attributes."""
        with pytest.raises(ValidationError):
            BeliefTransparencyItem(
                slot_name="education.major",
                asserted_value="Literature",
                canonical_status=CanonicalStatus.PROVISIONAL,
                belief_maturity=BeliefMaturity.CONSTRUCTING,
                unauthorized_extra_field="malicious",  # type: ignore
            )

    def test_belief_transparency_state_immutability(self):
        """State is frozen and rejects extra attributes."""
        state = BeliefTransparencyState(
            character_id="aevum",
            active_beliefs=(),
            recent_revisions=(),
        )
        with pytest.raises(ValidationError):
            state.character_id = "other"  # type: ignore
        with pytest.raises(ValidationError):
            BeliefTransparencyState(unknown_field="extra")  # type: ignore

    def test_belief_transparency_item_bounds_validation(self):
        """Cycles observed must be >= 1, evidence count >= 0."""
        with pytest.raises(ValidationError):
            BeliefTransparencyItem(
                slot_name="s",
                asserted_value="v",
                canonical_status=CanonicalStatus.CANONICAL,
                belief_maturity=BeliefMaturity.ESTABLISHED,
                cycles_observed=0,  # Invalid: ge=1
            )
        with pytest.raises(ValidationError):
            BeliefTransparencyItem(
                slot_name="s",
                asserted_value="v",
                canonical_status=CanonicalStatus.CANONICAL,
                belief_maturity=BeliefMaturity.ESTABLISHED,
                evidence_count=-1,  # Invalid: ge=0
            )


# ---------------------------------------------------------------------------
# 2. Three Orthogonal Axes Independence
# ---------------------------------------------------------------------------

class TestThreeOrthogonalAxes:
    """Verifies that CanonicalStatus, RecallLevel, and BeliefMaturity are orthogonal."""

    def test_canonical_hazy_established(self):
        """A ground-truth canonical fact can be subjectively hazy and established."""
        item = BeliefTransparencyItem(
            slot_name="childhood.friend",
            asserted_value="Kaito",
            canonical_status=CanonicalStatus.CANONICAL,
            recall_level=RecallLevel.HAZY,
            belief_maturity=BeliefMaturity.ESTABLISHED,
            cycles_observed=10,
            evidence_count=5,
        )
        assert item.canonical_status == CanonicalStatus.CANONICAL
        assert item.recall_level == RecallLevel.HAZY
        assert item.belief_maturity == BeliefMaturity.ESTABLISHED

    def test_canonical_vivid_emerging(self):
        """A newly promoted canonical fact can be vivid but still emerging in maturity."""
        item = BeliefTransparencyItem(
            slot_name="lifestyle.beverage",
            asserted_value="Matcha Latte",
            canonical_status=CanonicalStatus.CANONICAL,
            recall_level=RecallLevel.VIVID,
            belief_maturity=BeliefMaturity.EMERGING,
            cycles_observed=1,
            evidence_count=1,
        )
        assert item.canonical_status == CanonicalStatus.CANONICAL
        assert item.recall_level == RecallLevel.VIVID
        assert item.belief_maturity == BeliefMaturity.EMERGING

    def test_provisional_vivid_emerging(self):
        """A provisional hypothesis can be vivid and emerging across cycles."""
        item = BeliefTransparencyItem(
            slot_name="education.minor",
            asserted_value="Philosophy",
            canonical_status=CanonicalStatus.PROVISIONAL,
            recall_level=RecallLevel.VIVID,
            belief_maturity=BeliefMaturity.EMERGING,
            cycles_observed=3,
            evidence_count=2,
        )
        assert item.canonical_status == CanonicalStatus.PROVISIONAL
        assert item.recall_level == RecallLevel.VIVID
        assert item.belief_maturity == BeliefMaturity.EMERGING

    def test_provisional_fragmentary_constructing(self):
        """An early hypothesis can be fragmentary in recall and constructing in maturity."""
        item = BeliefTransparencyItem(
            slot_name="early_memory.pet",
            asserted_value="Calico Cat",
            canonical_status=CanonicalStatus.PROVISIONAL,
            recall_level=RecallLevel.FRAGMENTARY,
            belief_maturity=BeliefMaturity.CONSTRUCTING,
            cycles_observed=1,
            evidence_count=1,
        )
        assert item.canonical_status == CanonicalStatus.PROVISIONAL
        assert item.recall_level == RecallLevel.FRAGMENTARY
        assert item.belief_maturity == BeliefMaturity.CONSTRUCTING

    def test_disputed_vivid_constructing(self):
        """A disputed claim under repair can have vivid recollection but constructing maturity."""
        item = BeliefTransparencyItem(
            slot_name="timeline.year",
            asserted_value="Year 2",
            canonical_status=CanonicalStatus.DISPUTED,
            recall_level=RecallLevel.VIVID,
            belief_maturity=BeliefMaturity.CONSTRUCTING,
            cycles_observed=2,
            evidence_count=1,
            evidence_stable=False,
        )
        assert item.canonical_status == CanonicalStatus.DISPUTED
        assert item.recall_level == RecallLevel.VIVID
        assert item.belief_maturity == BeliefMaturity.CONSTRUCTING


# ---------------------------------------------------------------------------
# 3. Belief Maturity Classifier & Lock 10 Tests
# ---------------------------------------------------------------------------

class TestBeliefMaturityClassifier:
    """Verifies classification rules enforcing Lock 10."""

    def test_established_classification(self):
        """ESTABLISHED requires CANONICAL + cycles>=2 + evidence>=2 + evidence_stable=True."""
        maturity = BeliefMaturityClassifier.classify(
            canonical_status=CanonicalStatus.CANONICAL,
            cycles_observed=3,
            evidence_count=2,
            evidence_stable=True,
        )
        assert maturity == BeliefMaturity.ESTABLISHED

    def test_lock_10_cycle_count_alone_cannot_establish(self):
        """Lock 10: 100 cycles alone without multi-evidence cannot become ESTABLISHED."""
        # Case A: 100 cycles but evidence_count = 1 -> remains EMERGING
        mat_a = BeliefMaturityClassifier.classify(
            canonical_status=CanonicalStatus.CANONICAL,
            cycles_observed=100,
            evidence_count=1,
            evidence_stable=True,
        )
        assert mat_a == BeliefMaturity.EMERGING
        assert mat_a != BeliefMaturity.ESTABLISHED

        # Case B: 100 cycles but non-canonical provisional -> remains EMERGING
        mat_b = BeliefMaturityClassifier.classify(
            canonical_status=CanonicalStatus.PROVISIONAL,
            cycles_observed=100,
            evidence_count=10,
            evidence_stable=True,
        )
        assert mat_b == BeliefMaturity.EMERGING
        assert mat_b != BeliefMaturity.ESTABLISHED

    def test_lock_10_unstable_evidence_blocks_established(self):
        """Lock 10: Unaddressed contradiction (evidence_stable=False) demotes to CONSTRUCTING."""
        maturity = BeliefMaturityClassifier.classify(
            canonical_status=CanonicalStatus.CANONICAL,
            cycles_observed=10,
            evidence_count=5,
            evidence_stable=False,
        )
        assert maturity == BeliefMaturity.CONSTRUCTING

    def test_newly_promoted_canonical_is_emerging(self):
        """A canonical fact in cycle 1 with 1 evidence starts as EMERGING."""
        maturity = BeliefMaturityClassifier.classify(
            canonical_status=CanonicalStatus.CANONICAL,
            cycles_observed=1,
            evidence_count=1,
            evidence_stable=True,
        )
        assert maturity == BeliefMaturity.EMERGING

    def test_provisional_with_decisive_margin_is_emerging(self):
        """A provisional hypothesis with decisive competitive margin is EMERGING."""
        maturity = BeliefMaturityClassifier.classify(
            canonical_status=CanonicalStatus.PROVISIONAL,
            cycles_observed=1,
            evidence_count=1,
            evidence_stable=True,
            has_decisive_margin=True,
        )
        assert maturity == BeliefMaturity.EMERGING

    def test_initial_provisional_without_decisive_margin_is_constructing(self):
        """An initial provisional candidate without decisive margin is CONSTRUCTING."""
        maturity = BeliefMaturityClassifier.classify(
            canonical_status=CanonicalStatus.PROVISIONAL,
            cycles_observed=1,
            evidence_count=1,
            evidence_stable=True,
            has_decisive_margin=False,
        )
        assert maturity == BeliefMaturity.CONSTRUCTING

    def test_disputed_status_is_constructing(self):
        """Any disputed fact is CONSTRUCTING."""
        maturity = BeliefMaturityClassifier.classify(
            canonical_status=CanonicalStatus.DISPUTED,
            cycles_observed=5,
            evidence_count=3,
        )
        assert maturity == BeliefMaturity.CONSTRUCTING


# ---------------------------------------------------------------------------
# 4. Adapter & Prompt Context Assembly Tests
# ---------------------------------------------------------------------------

class TestBeliefTransparencyAdapter:
    """Verifies XML serialization, bounded revisions, and helpers."""

    def test_bounded_revision_retention_decision_d4(self):
        """Decision D4: At most 5 recent revisions are included in prompt context."""
        revisions = [_make_revision_record(f"rev-{i}") for i in range(12)]
        state = BeliefTransparencyAdapter.build_transparency_state(
            character_id="aevum",
            active_beliefs=(),
            recent_revisions=revisions,
        )
        assert len(state.recent_revisions) == 5
        assert [r.revision_id for r in state.recent_revisions] == [
            "rev-7", "rev-8", "rev-9", "rev-10", "rev-11"
        ]

    def test_format_autonomous_belief_state_xml(self):
        """Adapter formats valid <autonomous_belief_state> XML block."""
        item1 = BeliefTransparencyItem(
            slot_name="education.major",
            asserted_value="Computer Science",
            canonical_status=CanonicalStatus.CANONICAL,
            recall_level=RecallLevel.VIVID,
            belief_maturity=BeliefMaturity.ESTABLISHED,
            cycles_observed=5,
            evidence_count=3,
        )
        item2 = BeliefTransparencyItem(
            slot_name="hobbies.music",
            asserted_value="Piano",
            canonical_status=CanonicalStatus.PROVISIONAL,
            recall_level=RecallLevel.HAZY,
            belief_maturity=BeliefMaturity.CONSTRUCTING,
            cycles_observed=1,
            evidence_count=1,
            candidate_id="cand-piano",
        )
        rev = _make_revision_record("rev-1", slot="lifestyle.sleep_time")

        state = BeliefTransparencyAdapter.build_transparency_state(
            character_id="aevum",
            active_beliefs=(item1, item2),
            recent_revisions=(rev,),
        )
        xml = BeliefTransparencyAdapter.format_autonomous_belief_state(state)

        assert "<autonomous_belief_state>" in xml
        assert "</autonomous_belief_state>" in xml
        assert '<constitutional_guidance>' in xml
        assert '<active_beliefs count="2">' in xml
        assert 'slot="education.major" status="CANONICAL" recall="VIVID" maturity="ESTABLISHED"' in xml
        assert 'slot="hobbies.music" status="PROVISIONAL" recall="HAZY" maturity="CONSTRUCTING"' in xml
        assert "<candidate_id>cand-piano</candidate_id>" in xml
        assert '<recent_belief_revisions count="1">' in xml
        assert 'id="rev-1" kind="CONFIRMATION" slot="lifestyle.sleep_time"' in xml

    def test_empty_state_xml_serialization(self):
        """Empty state formats cleanly without errors."""
        state = BeliefTransparencyAdapter.build_transparency_state(character_id="aevum")
        xml = BeliefTransparencyAdapter.format_autonomous_belief_state(state)
        assert '<active_beliefs count="0" />' in xml
        assert '<recent_belief_revisions count="0" />' in xml

    def test_replay_determinism_hash(self):
        """Identical inputs produce identical SHA-256 hash."""
        item = BeliefTransparencyItem(
            slot_name="education.major",
            asserted_value="Computer Science",
            canonical_status=CanonicalStatus.CANONICAL,
            belief_maturity=BeliefMaturity.ESTABLISHED,
        )
        state1 = BeliefTransparencyAdapter.build_transparency_state(
            character_id="aevum", active_beliefs=(item,)
        )
        state2 = BeliefTransparencyAdapter.build_transparency_state(
            character_id="aevum", active_beliefs=(item,)
        )
        assert state1.context_hash_sha256 == state2.context_hash_sha256
        assert len(state1.context_hash_sha256) == 64

    def test_item_from_candidate_helper(self):
        """Helper correctly creates item from CandidateHypothesis."""
        cand = _make_candidate("cand-1", slot="education.major", val="Linguistics", evidence_count=2)
        item = BeliefTransparencyAdapter.item_from_candidate(
            candidate=cand,
            recall_level=RecallLevel.VIVID,
            cycles_observed=2,
            has_decisive_margin=True,
        )
        assert item.slot_name == "education.major"
        assert item.asserted_value == "Linguistics"
        assert item.canonical_status == CanonicalStatus.PROVISIONAL
        assert item.belief_maturity == BeliefMaturity.EMERGING
        assert item.candidate_id == "cand-1"

    def test_item_from_canonical_fact_helper(self):
        """Helper correctly creates item for canonical fact."""
        item = BeliefTransparencyAdapter.item_from_canonical_fact(
            slot_name="identity.name",
            value="Aevum",
            recall_level=RecallLevel.VIVID,
            cycles_observed=5,
            evidence_count=4,
        )
        assert item.slot_name == "identity.name"
        assert item.asserted_value == "Aevum"
        assert item.canonical_status == CanonicalStatus.CANONICAL
        assert item.belief_maturity == BeliefMaturity.ESTABLISHED


# ---------------------------------------------------------------------------
# 5. Golden Suite 14 Acceptance Benchmarks (GC-372 ~ GC-376)
# ---------------------------------------------------------------------------

class TestGoldenSuite14Cluster5:
    """GC-372 ~ GC-376 — Constitutional acceptance benchmarks for Phase 14.5."""

    def test_gc372_three_orthogonal_axes_independence(self):
        """GC-372: CanonicalStatus, RecallLevel, and BeliefMaturity are 3 independent axes.

        Proves that maturity is completely decoupled from canonical truth status and recall clarity:
        - A canonical fact can have any recall quality (VIVID, HAZY, FRAGMENTARY).
        - A provisional candidate can have any recall quality.
        - High maturity does not convert a candidate to canonical truth.
        """
        # Canonical + Hazy + Established
        f1 = BeliefTransparencyItem(
            slot_name="origin.place",
            asserted_value="Coastal Town",
            canonical_status=CanonicalStatus.CANONICAL,
            recall_level=RecallLevel.HAZY,
            belief_maturity=BeliefMaturity.ESTABLISHED,
            cycles_observed=4,
            evidence_count=3,
        )
        # Provisional + Vivid + Emerging (Not Canonical despite high clarity and multi-cycle emergence)
        f2 = BeliefTransparencyItem(
            slot_name="future.goal",
            asserted_value="Music School",
            canonical_status=CanonicalStatus.PROVISIONAL,
            recall_level=RecallLevel.VIVID,
            belief_maturity=BeliefMaturity.EMERGING,
            cycles_observed=3,
            evidence_count=2,
        )
        # Canonical + Vivid + Emerging (Newly promoted, vivid, but not yet established maturity)
        f3 = BeliefTransparencyItem(
            slot_name="lifestyle.routine",
            asserted_value="Morning Walk",
            canonical_status=CanonicalStatus.CANONICAL,
            recall_level=RecallLevel.VIVID,
            belief_maturity=BeliefMaturity.EMERGING,
            cycles_observed=1,
            evidence_count=1,
        )
        # Disputed + Fragmentary + Constructing
        f4 = BeliefTransparencyItem(
            slot_name="timeline.event",
            asserted_value="Old Festival",
            canonical_status=CanonicalStatus.DISPUTED,
            recall_level=RecallLevel.FRAGMENTARY,
            belief_maturity=BeliefMaturity.CONSTRUCTING,
            cycles_observed=2,
            evidence_count=1,
        )

        assert f1.canonical_status != f2.canonical_status
        assert f1.belief_maturity == BeliefMaturity.ESTABLISHED
        assert f2.canonical_status == CanonicalStatus.PROVISIONAL
        assert f3.canonical_status == CanonicalStatus.CANONICAL
        assert f3.belief_maturity == BeliefMaturity.EMERGING

    def test_gc373_lock10_maturity_not_truth_and_cycle_alone_insufficient(self):
        """GC-373: Lock 10 — Belief maturity is not truth; cycle count alone cannot establish.

        A hypothesis or fact that has existed for 100 cycles without corroborating
        evidence stability MUST NOT be classified as ESTABLISHED.
        """
        # Case 1: 100 cycles, but only 1 evidence -> NOT ESTABLISHED (EMERGING)
        maturity_isolated_cycle = BeliefMaturityClassifier.classify(
            canonical_status=CanonicalStatus.CANONICAL,
            cycles_observed=100,
            evidence_count=1,
            evidence_stable=True,
        )
        assert maturity_isolated_cycle != BeliefMaturity.ESTABLISHED
        assert maturity_isolated_cycle == BeliefMaturity.EMERGING

        # Case 2: 100 cycles on provisional candidate -> NOT ESTABLISHED (EMERGING)
        maturity_provisional = BeliefMaturityClassifier.classify(
            canonical_status=CanonicalStatus.PROVISIONAL,
            cycles_observed=100,
            evidence_count=5,
            evidence_stable=True,
        )
        assert maturity_provisional != BeliefMaturity.ESTABLISHED

        # Case 3: Proper ESTABLISHED requires CANONICAL + duration (cycles>=2) + stability (count>=2, stable=True)
        maturity_valid = BeliefMaturityClassifier.classify(
            canonical_status=CanonicalStatus.CANONICAL,
            cycles_observed=2,
            evidence_count=2,
            evidence_stable=True,
        )
        assert maturity_valid == BeliefMaturity.ESTABLISHED

    def test_gc374_decision_d3_constructing_no_prescribed_utterance_templates(self):
        """GC-374: Decision D3 — CONSTRUCTING is an epistemic state, NOT a prescribed utterance template.

        Verifies that XML guidance instructs natural humble uncertainty without
        canned linguistic formulas (no mandatory prefixes like 'I think...', 'Maybe...').
        """
        state = BeliefTransparencyAdapter.build_transparency_state(
            character_id="aevum",
            active_beliefs=(
                BeliefTransparencyItem(
                    slot_name="test.slot",
                    asserted_value="Unknown",
                    canonical_status=CanonicalStatus.PROVISIONAL,
                    belief_maturity=BeliefMaturity.CONSTRUCTING,
                ),
            ),
        )
        xml = BeliefTransparencyAdapter.format_autonomous_belief_state(state)

        # Guidance specifies epistemic posture
        assert "CONSTRUCTING: Active exploration/hypothesis; genuine epistemic ambiguity; express natural humble uncertainty, do not invent answers." in xml
        # Architecture does NOT specify mandatory sentence patterns
        assert "You must say 'I am not sure'" not in xml
        assert "Prefix your response with" not in xml
        assert "Template:" not in xml

    def test_gc375_context_assembly_and_xml_bounded_serialization(self):
        """GC-375: Context assembly generates well-formed XML with bounded revisions (Decision D4)."""
        revisions = [_make_revision_record(f"gc375-rev-{i}") for i in range(10)]
        item = BeliefTransparencyItem(
            slot_name="identity.motto",
            asserted_value="Per Aspera Ad Astra",
            canonical_status=CanonicalStatus.CANONICAL,
            belief_maturity=BeliefMaturity.ESTABLISHED,
            cycles_observed=3,
            evidence_count=2,
        )
        state = BeliefTransparencyAdapter.build_transparency_state(
            character_id="aevum",
            active_beliefs=(item,),
            recent_revisions=revisions,
        )
        assert len(state.recent_revisions) == 5

        xml = BeliefTransparencyAdapter.format_autonomous_belief_state(state)
        assert '<autonomous_belief_state>' in xml
        assert '<active_beliefs count="1">' in xml
        assert '<recent_belief_revisions count="5">' in xml
        assert 'Per Aspera Ad Astra' in xml
        assert state.context_hash_sha256 != ""

    def test_gc376_constitutional_authority_boundary_ast_audit(self):
        """GC-376: belief_transparency.py contains zero forbidden mutation symbols (0 set_fact, 0 token minting)."""
        path = Path(__file__).parent.parent / "app" / "reality" / "belief_transparency.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden = {"set_fact", "PromotionAuthorizationToken"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden:
                pytest.fail(f"Forbidden symbol '{node.id}' in belief_transparency.py AST")
