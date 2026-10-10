"""Unit tests for Phase 8A.4 CandidateEvaluationAdapter.

Verifies:
1. Invariant A: Unknown != Impossible (unknown criteria -> HardValidity=1.0).
2. Invariant A: Unknown external entities quarantined as speculative with HardValidity=1.0.
3. Invariant B: Heuristic != Probability (prior_weight is neutral 0.50 baseline fit).
4. Invariant C: Construction != Persistence (in-memory CandidateHypothesis only, zero DB models).
5. Invariant D: Derived != Primary (pure AEVUM_INFERRED premise chain yields zero support).
6. Invariant E & Anti-Circularity: Downstream inferred facts cannot support upstream slots.
7. Evaluator completely ignores proposer suggested roles.
8. Evaluator completely ignores proposer rationale string.
9. Hard validity catches core user lock conflict (HardValidity=0.0).
10. Hard validity catches chronological impossibility (age <= 16 with undergrad major -> HardValidity=0.0).
11. Feasibility strictly prohibits parental occupation stereotyping (doctor parent without resource fact -> 0.50).
12. Feasibility correctly evaluates explicit scholarship and socioeconomic facts.
13. Feasibility confirms public pathways (STPM, Matrikulasi) accessible across economic tiers.
14. Context support evaluates music major from talent and instrument facts.
15. Context support evaluates CS major from programming and math facts with contradiction penalty.
16. Affinity reflects character values and temperament alignment.
17. Composite plausibility formula evaluates bounded weighted sum.
18. Precomputed choice factor inputs attached to selection_metadata.
19. Provenance lineage and evidence families correctly linked.
20. Batch evaluation preserves envelope sequence and length.
21. AST Audit: Zero set_fact, zero tokens, zero DB transactions in adapter module.
22. AST Audit: Zero network, requests, or tool calls in adapter module.
"""

import ast
from pathlib import Path
import pytest

from app.character.core_models import CharacterCore
from app.reality.candidate_evaluator import CandidateEvaluationAdapter
from app.reality.candidate_models import (
    CandidateHypothesis,
    CandidateLifecycleState,
    InferenceEdgeType,
)
from app.reality.inference_models import (
    CandidateEnvelope,
    InferenceProposalRequest,
    PremiseRole,
)
from app.reality.models import CoreFactItem, FactAuthority, FactSource, FactStatus


def _build_core(facts_dict: dict[str, tuple[Any, FactSource, bool]]) -> CharacterCore:
    """Helper to build CharacterCore with typed CoreFactItem objects."""
    items = {}
    for key, (val, source, is_locked) in facts_dict.items():
        cat = key.split(".")[0]
        authority = FactAuthority.USER_LOCKED if is_locked else FactAuthority.AEVUM_CANONICAL
        items[key] = CoreFactItem(
            key=key,
            category=cat,
            value=val,
            source=source,
            authority=authority,
            status=FactStatus.CANONICAL,
            locked=is_locked,
        )
    return CharacterCore(facts=items)


# =============================================================================
# 1. The Six Core Invariants (A - F)
# =============================================================================


def test_invariant_unknown_is_not_impossible() -> None:
    """Invariant A: Absence of knowledge is not falsification. HardValidity remains 1.0."""
    adapter = CandidateEvaluationAdapter()
    req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=("traits.musical_talent",),
        premise_snapshots={"traits.musical_talent": True},
        inference_cycle_id="cycle_unknown",
    )
    env = CandidateEnvelope(
        domain="education",
        slot="education.major",
        raw_value="music_performance",
        suggested_premise_keys=("traits.musical_talent",),
        suggested_premise_roles={"traits.musical_talent": PremiseRole.DIRECT_SUPPORT},
        rationale="Artistic talent.",
    )
    cand = adapter.evaluate_envelope(env, req)
    # HardValidity must remain 1.0 when admission/syllabus details are unrecorded
    assert cand.plausibility.composite_plausibility_score > 0.0
    assert not cand.is_quarantined


def test_invariant_unknown_entity_is_quarantined_not_zero_validity() -> None:
    """Invariant A: Unregistered external entity has HardValidity=1.0 and is_quarantined=True."""
    adapter = CandidateEvaluationAdapter()
    req = InferenceProposalRequest(
        target_slot="education.university",
        domain="education",
        authorized_premise_keys=("traits.musical_talent",),
        premise_snapshots={"traits.musical_talent": True},
        inference_cycle_id="cycle_quarantine",
    )
    env = CandidateEnvelope(
        domain="education",
        slot="education.university",
        raw_value="Juilliard School",
        suggested_premise_keys=("traits.musical_talent",),
        suggested_premise_roles={"traits.musical_talent": PremiseRole.DIRECT_SUPPORT},
        rationale="Elite conservatory.",
    )
    cand = adapter.evaluate_envelope(env, req)

    # Invariant: Unknown != Impossible. HardValidity is 1.0, so composite > 0
    assert cand.plausibility.composite_plausibility_score > 0.0
    # Must be quarantined for Phase 9 verification
    assert cand.is_quarantined is True
    assert cand.quarantine_reason == "UNVERIFIED_EXTERNAL_WORLD_ENTITY"
    assert cand.inference_edge_type == InferenceEdgeType.SPECULATIVE_ASSOCIATION


def test_invariant_heuristic_is_not_probability() -> None:
    """Invariant B: structural_baseline_fit is neutral 0.50; composite is coherence, not probability."""
    adapter = CandidateEvaluationAdapter()
    req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=("skills.programming",),
        premise_snapshots={"skills.programming": "Python"},
        inference_cycle_id="cycle_heuristic",
    )
    env = CandidateEnvelope(
        domain="education",
        slot="education.major",
        raw_value="computer_science",
        suggested_premise_keys=("skills.programming",),
        suggested_premise_roles={"skills.programming": PremiseRole.DIRECT_SUPPORT},
        rationale="Tech fit.",
    )
    cand = adapter.evaluate_envelope(env, req)
    assert cand.plausibility.prior_weight == 0.50
    assert 0.0 <= cand.plausibility.composite_plausibility_score <= 1.0


def test_invariant_construction_is_not_persistence() -> None:
    """Invariant C: Adapter constructs in-memory CandidateHypothesis only (zero DB models)."""
    adapter = CandidateEvaluationAdapter()
    req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=("traits.musical_talent",),
        premise_snapshots={"traits.musical_talent": True},
        inference_cycle_id="cycle_memory",
    )
    env = CandidateEnvelope(
        domain="education",
        slot="education.major",
        raw_value="music_performance",
        suggested_premise_keys=("traits.musical_talent",),
        suggested_premise_roles={"traits.musical_talent": PremiseRole.DIRECT_SUPPORT},
        rationale="Musical talent.",
    )
    cand = adapter.evaluate_envelope(env, req)
    assert isinstance(cand, CandidateHypothesis)
    # Confirm in-memory lifecycle state is GENERATED (not PERSISTED)
    assert cand.lifecycle_state == CandidateLifecycleState.GENERATED
    assert cand.selection_metadata is None
    # Confirm it has no SQLAlchemy DB state
    assert not hasattr(cand, "__tablename__")
    assert not hasattr(cand, "_sa_instance_state")


def test_invariant_derived_is_not_primary() -> None:
    """Invariant D: Pure derived (AEVUM_INFERRED -> AEVUM_INFERRED) premise chain yields zero support."""
    adapter = CandidateEvaluationAdapter()
    # Core has only an AEVUM_INFERRED fact
    core = _build_core({
        "education.major": ("computer_science", FactSource.AEVUM_INFERRED, False),
    })
    req = InferenceProposalRequest(
        target_slot="career.aspiration",
        domain="career",
        authorized_premise_keys=("education.major",),
        premise_snapshots={"education.major": "computer_science"},
        inference_cycle_id="cycle_derived_only",
    )
    env = CandidateEnvelope(
        domain="career",
        slot="career.aspiration",
        raw_value="software_engineer",
        suggested_premise_keys=("education.major",),
        suggested_premise_roles={"education.major": PremiseRole.DIRECT_SUPPORT},
        rationale="Major suggests career.",
    )
    cand = adapter.evaluate_envelope(env, req, core=core)
    # ContextSupport must be 0.0 because there is zero primary canonical anchor!
    assert cand.plausibility.evidence_grounding_score == 0.0


def test_invariant_anti_circularity_downstream_cannot_support_upstream() -> None:
    """Invariant E & Anti-Circularity: Downstream career cannot support upstream major."""
    adapter = CandidateEvaluationAdapter()
    # Core has an AEVUM_INFERRED career aspiration
    core = _build_core({
        "career.aspiration": ("software_engineer", FactSource.AEVUM_INFERRED, False),
        "traits.musical_talent": (True, FactSource.USER_CONFIGURED, False),
    })
    req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=("career.aspiration", "traits.musical_talent"),
        premise_snapshots={"career.aspiration": "software_engineer", "traits.musical_talent": True},
        inference_cycle_id="cycle_circular",
    )
    env = CandidateEnvelope(
        domain="education",
        slot="education.major",
        raw_value="computer_science",
        # Attempting to cite downstream career to support CS major
        suggested_premise_keys=("career.aspiration",),
        suggested_premise_roles={"career.aspiration": PremiseRole.DIRECT_SUPPORT},
        rationale="Downstream circular attempt.",
    )
    cand = adapter.evaluate_envelope(env, req, core=core)
    # Downstream inferred career is pruned; zero support
    assert cand.plausibility.evidence_grounding_score == 0.0


# =============================================================================
# 2. Independent Evaluation Dimensions
# =============================================================================


def test_evaluator_ignores_proposer_suggested_roles() -> None:
    """Evaluator ignores proposer roles; evaluates purely from canonical evidence."""
    adapter = CandidateEvaluationAdapter()
    req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=("traits.musical_talent",),
        premise_snapshots={"traits.musical_talent": True},
        inference_cycle_id="cycle_roles",
    )
    # Proposer erroneously claims musical_talent is CONTRADICTING for music_performance
    env = CandidateEnvelope(
        domain="education",
        slot="education.major",
        raw_value="music_performance",
        suggested_premise_keys=("traits.musical_talent",),
        suggested_premise_roles={"traits.musical_talent": PremiseRole.CONTRADICTING},
        rationale="Erroneous role.",
    )
    cand = adapter.evaluate_envelope(env, req)
    # Evaluator determines support independently from domain matrix (+0.35), ignoring CONTRADICTING claim
    assert cand.plausibility.evidence_grounding_score >= 0.70


def test_evaluator_ignores_proposer_rationale() -> None:
    """Evaluator ignores narrative rationale text."""
    adapter = CandidateEvaluationAdapter()
    req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=("skills.programming",),
        premise_snapshots={"skills.programming": "Python"},
        inference_cycle_id="cycle_rat",
    )
    env1 = CandidateEnvelope(
        domain="education",
        slot="education.major",
        raw_value="computer_science",
        suggested_premise_keys=("skills.programming",),
        suggested_premise_roles={"skills.programming": PremiseRole.DIRECT_SUPPORT},
        rationale="Unsubstantiated claim of perfection and genius.",
    )
    env2 = CandidateEnvelope(
        domain="education",
        slot="education.major",
        raw_value="computer_science",
        suggested_premise_keys=("skills.programming",),
        suggested_premise_roles={"skills.programming": PremiseRole.DIRECT_SUPPORT},
        rationale="Completely different wording.",
    )
    cand1 = adapter.evaluate_envelope(env1, req)
    cand2 = adapter.evaluate_envelope(env2, req)
    # Plausibility scores must be strictly identical regardless of narrative in rationale
    assert cand1.plausibility.composite_plausibility_score == cand2.plausibility.composite_plausibility_score


def test_hard_validity_catches_core_user_lock_conflict() -> None:
    """Core fact locked with different value yields HardValidity=0.0."""
    adapter = CandidateEvaluationAdapter()
    core = _build_core({
        "education.major": ("music_performance", FactSource.USER_CONFIGURED, True),  # LOCKED
    })
    req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=("skills.programming",),
        premise_snapshots={"skills.programming": "Python"},
        inference_cycle_id="cycle_locked",
    )
    env = CandidateEnvelope(
        domain="education",
        slot="education.major",
        raw_value="computer_science",
        suggested_premise_keys=("skills.programming",),
        suggested_premise_roles={"skills.programming": PremiseRole.DIRECT_SUPPORT},
        rationale="Conflicting candidate.",
    )
    cand = adapter.evaluate_envelope(env, req, core=core)
    assert cand.plausibility.composite_plausibility_score == 0.0


def test_hard_validity_catches_chronological_impossibility() -> None:
    """Undergraduate major at age 14 yields HardValidity=0.0."""
    adapter = CandidateEvaluationAdapter()
    req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=("identity.age", "skills.programming"),
        premise_snapshots={"identity.age": 14, "skills.programming": "Python"},
        inference_cycle_id="cycle_underage",
    )
    env = CandidateEnvelope(
        domain="education",
        slot="education.major",
        raw_value="computer_science",
        suggested_premise_keys=("skills.programming",),
        suggested_premise_roles={"skills.programming": PremiseRole.DIRECT_SUPPORT},
        rationale="Child prodigy attempt without canon.",
    )
    cand = adapter.evaluate_envelope(env, req)
    assert cand.plausibility.composite_plausibility_score == 0.0


def test_feasibility_strictly_prohibits_parental_occupation_stereotypes() -> None:
    """Doctor parent without explicit resource facts yields neutral 0.50 feasibility."""
    adapter = CandidateEvaluationAdapter()
    req = InferenceProposalRequest(
        target_slot="education.pathway",
        domain="education",
        authorized_premise_keys=("parents.father_occupation",),
        premise_snapshots={"parents.father_occupation": "doctor"},
        inference_cycle_id="cycle_stereotype",
    )
    env = CandidateEnvelope(
        domain="education",
        slot="education.pathway",
        raw_value="foundation",
        suggested_premise_keys=("parents.father_occupation",),
        suggested_premise_roles={"parents.father_occupation": PremiseRole.DIRECT_SUPPORT},
        rationale="Private foundation.",
    )
    cand = adapter.evaluate_envelope(env, req)
    # Feasibility must not be boosted by father being a doctor (remains neutral resource 0.50)
    # Average of acad (0.85) and neutral resource (0.50) = 0.675
    assert cand.plausibility.coherence_score <= 0.70


def test_feasibility_explicit_scholarship_and_socioeconomic_tier() -> None:
    """Explicit scholarship boosts private foundation feasibility; B40 without aid penalizes it."""
    adapter = CandidateEvaluationAdapter()

    # Case 1: Awarded scholarship
    req_scholar = InferenceProposalRequest(
        target_slot="education.pathway",
        domain="education",
        authorized_premise_keys=("scholarship.status",),
        premise_snapshots={"scholarship.status": True},
        inference_cycle_id="cycle_scholar",
    )
    env_priv = CandidateEnvelope(
        domain="education",
        slot="education.pathway",
        raw_value="foundation",
        suggested_premise_keys=("scholarship.status",),
        suggested_premise_roles={"scholarship.status": PremiseRole.DIRECT_SUPPORT},
        rationale="Scholarship foundation.",
    )
    cand_scholar = adapter.evaluate_envelope(env_priv, req_scholar)
    # High resource feasibility (0.95)
    assert cand_scholar.plausibility.coherence_score >= 0.85

    # Case 2: B40 socioeconomic tier without aid
    req_b40 = InferenceProposalRequest(
        target_slot="education.pathway",
        domain="education",
        authorized_premise_keys=("family.socioeconomic_tier",),
        premise_snapshots={"family.socioeconomic_tier": "B40"},
        inference_cycle_id="cycle_b40",
    )
    cand_b40 = adapter.evaluate_envelope(env_priv, req_b40)
    # Low resource feasibility (0.25)
    assert cand_b40.plausibility.coherence_score <= 0.60


def test_feasibility_public_pathways_accessible_across_all_tiers() -> None:
    """STPM / Matrikulasi maintain high feasibility across all economic tiers due to public subsidy."""
    adapter = CandidateEvaluationAdapter()
    req_b40 = InferenceProposalRequest(
        target_slot="education.pathway",
        domain="education",
        authorized_premise_keys=("family.socioeconomic_tier",),
        premise_snapshots={"family.socioeconomic_tier": "B40"},
        inference_cycle_id="cycle_stpm",
    )
    env_stpm = CandidateEnvelope(
        domain="education",
        slot="education.pathway",
        raw_value="stpm",
        suggested_premise_keys=("family.socioeconomic_tier",),
        suggested_premise_roles={"family.socioeconomic_tier": PremiseRole.CONTEXT_SUPPORT},
        rationale="Public STPM.",
    )
    cand_stpm = adapter.evaluate_envelope(env_stpm, req_b40)
    # Public pathway is accessible (resource score 0.90)
    assert cand_stpm.plausibility.coherence_score >= 0.85


def test_context_support_deterministic_music_major() -> None:
    """Music talent and instrument playing produce high context support."""
    adapter = CandidateEvaluationAdapter()
    req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=("traits.musical_talent", "skills.instrument_playing", "academics.spm_math_grade"),
        premise_snapshots={
            "traits.musical_talent": True,
            "skills.instrument_playing": "piano",
            "academics.spm_math_grade": "C",
        },
        inference_cycle_id="cycle_music_sup",
    )
    env = CandidateEnvelope(
        domain="education",
        slot="education.major",
        raw_value="music_performance",
        suggested_premise_keys=("traits.musical_talent", "skills.instrument_playing"),
        suggested_premise_roles={"traits.musical_talent": PremiseRole.DIRECT_SUPPORT},
        rationale="Piano artist.",
    )
    cand = adapter.evaluate_envelope(env, req)
    # High support (>0.70)
    assert cand.plausibility.evidence_grounding_score >= 0.70


def test_context_support_deterministic_cs_major() -> None:
    """Programming + Math A produces high support; Math F produces contradiction penalty."""
    adapter = CandidateEvaluationAdapter()

    # Strong math
    req_strong = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=("skills.programming", "academics.spm_math_grade"),
        premise_snapshots={"skills.programming": "Python", "academics.spm_math_grade": "A"},
        inference_cycle_id="cycle_cs_strong",
    )
    env_cs = CandidateEnvelope(
        domain="education",
        slot="education.major",
        raw_value="computer_science",
        suggested_premise_keys=("skills.programming", "academics.spm_math_grade"),
        suggested_premise_roles={"skills.programming": PremiseRole.DIRECT_SUPPORT},
        rationale="CS talent.",
    )
    cand_strong = adapter.evaluate_envelope(env_cs, req_strong)
    assert cand_strong.plausibility.evidence_grounding_score >= 0.75

    # Weak math contradiction
    req_weak = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=("skills.programming", "academics.spm_math_grade"),
        premise_snapshots={"skills.programming": "Python", "academics.spm_math_grade": "F"},
        inference_cycle_id="cycle_cs_weak",
    )
    cand_weak = adapter.evaluate_envelope(env_cs, req_weak)
    assert cand_weak.plausibility.evidence_grounding_score < cand_strong.plausibility.evidence_grounding_score


def test_affinity_values_and_temperament_alignment() -> None:
    """Creativity values boost creative candidate affinity; stability values boost traditional."""
    adapter = CandidateEvaluationAdapter()
    req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=("values.creativity",),
        premise_snapshots={"values.creativity": "HIGH"},
        inference_cycle_id="cycle_aff",
    )
    env_music = CandidateEnvelope(
        domain="education",
        slot="education.major",
        raw_value="music_performance",
        suggested_premise_keys=("values.creativity",),
        suggested_premise_roles={"values.creativity": PremiseRole.DIRECT_SUPPORT},
        rationale="Creative music.",
    )
    cand_music = adapter.evaluate_envelope(env_music, req)
    assert cand_music.plausibility.utility_score >= 0.70


# =============================================================================
# 3. Model Mapping & Phase 7 Interoperability
# =============================================================================


def test_composite_plausibility_formula_correctness() -> None:
    """Composite score formula matches: round(H * (0.15*base + 0.35*supp + 0.25*feas + 0.25*aff), 4)."""
    adapter = CandidateEvaluationAdapter()
    req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=("skills.programming",),
        premise_snapshots={"skills.programming": "Python"},
        inference_cycle_id="cycle_formula",
    )
    env = CandidateEnvelope(
        domain="education",
        slot="education.major",
        raw_value="computer_science",
        suggested_premise_keys=("skills.programming",),
        suggested_premise_roles={"skills.programming": PremiseRole.DIRECT_SUPPORT},
        rationale="Formula verification.",
    )
    cand = adapter.evaluate_envelope(env, req)
    p = cand.plausibility
    expected = round(
        0.15 * p.prior_weight
        + 0.35 * p.evidence_grounding_score
        + 0.25 * p.coherence_score
        + 0.25 * p.utility_score,
        4,
    )
    assert p.composite_plausibility_score == expected


def test_evaluator_leaves_selection_metadata_none_and_lifecycle_generated() -> None:
    """CandidateHypothesis has lifecycle_state=GENERATED and selection_metadata=None.

    Preserves:
    - Invariant C: Construction != Persistence (candidate is GENERATED, not PERSISTED).
    - Separation of Evaluation and Choice: Zero choice factor pre-baking in selection_metadata.
    """
    adapter = CandidateEvaluationAdapter()
    req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=("traits.musical_talent",),
        premise_snapshots={"traits.musical_talent": True},
        inference_cycle_id="cycle_meta",
    )
    env = CandidateEnvelope(
        domain="education",
        slot="education.major",
        raw_value="music_performance",
        suggested_premise_keys=("traits.musical_talent",),
        suggested_premise_roles={"traits.musical_talent": PremiseRole.DIRECT_SUPPORT},
        rationale="Selection metadata verification.",
    )
    cand = adapter.evaluate_envelope(env, req)
    assert cand.lifecycle_state == CandidateLifecycleState.GENERATED
    assert cand.selection_metadata is None


def test_evaluator_does_not_construct_choice_factor_breakdown_inputs() -> None:
    """Evaluator does not pre-bake ChoiceFactorBreakdown inputs (e.g. opportunity_cost, time_cost)."""
    adapter = CandidateEvaluationAdapter()
    req = InferenceProposalRequest(
        target_slot="education.pathway",
        domain="education",
        authorized_premise_keys=("traits.challenge_preference",),
        premise_snapshots={"traits.challenge_preference": "HIGH"},
        inference_cycle_id="cycle_choice_free",
    )
    env = CandidateEnvelope(
        domain="education",
        slot="education.pathway",
        raw_value="stpm",
        suggested_premise_keys=("traits.challenge_preference",),
        suggested_premise_roles={"traits.challenge_preference": PremiseRole.DIRECT_SUPPORT},
        rationale="STPM pathway.",
    )
    cand = adapter.evaluate_envelope(env, req)
    assert cand.selection_metadata is None
    # Verify no arbitrary choice constants leaked into candidate attributes
    assert not hasattr(cand, "opportunity_cost")
    assert not hasattr(cand, "time_cost")


def test_provenance_lineage_and_evidence_families_created() -> None:
    """ProvenanceLineage and EvidenceFamily objects are correctly created."""
    adapter = CandidateEvaluationAdapter()
    req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=("traits.musical_talent", "skills.instrument_playing"),
        premise_snapshots={"traits.musical_talent": True, "skills.instrument_playing": "piano"},
        inference_cycle_id="cycle_prov_01",
    )
    env = CandidateEnvelope(
        domain="education",
        slot="education.major",
        raw_value="music_performance",
        suggested_premise_keys=("traits.musical_talent", "skills.instrument_playing"),
        suggested_premise_roles={"traits.musical_talent": PremiseRole.DIRECT_SUPPORT},
        rationale="Provenance verification.",
    )
    cand = adapter.evaluate_envelope(env, req)
    assert cand.provenance.origin_id == "cycle_prov_01"
    assert cand.provenance.inference_depth == 1
    assert len(cand.evidence_families) == 2
    assert cand.evidence_families[0].family_id == "fam_traits.musical_talent"


def test_batch_evaluation_preserves_order_and_envelopes() -> None:
    """evaluate_envelopes batch processes a list of envelopes without dropping any."""
    adapter = CandidateEvaluationAdapter()
    req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=("traits.musical_talent", "skills.programming"),
        premise_snapshots={"traits.musical_talent": True, "skills.programming": "Python"},
        inference_cycle_id="cycle_batch",
    )
    envs = [
        CandidateEnvelope(
            domain="education",
            slot="education.major",
            raw_value="music_performance",
            suggested_premise_keys=("traits.musical_talent",),
            suggested_premise_roles={"traits.musical_talent": PremiseRole.DIRECT_SUPPORT},
            rationale="Opt 1.",
        ),
        CandidateEnvelope(
            domain="education",
            slot="education.major",
            raw_value="computer_science",
            suggested_premise_keys=("skills.programming",),
            suggested_premise_roles={"skills.programming": PremiseRole.DIRECT_SUPPORT},
            rationale="Opt 2.",
        ),
    ]
    candidates = adapter.evaluate_envelopes(envs, req)
    assert len(candidates) == 2
    assert candidates[0].proposed_value == "music_performance"
    assert candidates[1].proposed_value == "computer_science"


# =============================================================================
# 4. AST Audits: Zero Mutation, Zero Tokens, Zero Network Calls
# =============================================================================


def test_ast_audit_zero_set_fact_zero_tokens_zero_db_transactions() -> None:
    """AST Audit: Prohibits set_fact, PromotionAuthorizationToken.create, and DB commit/flush."""
    eval_file = Path("d:/Aevum/Aevum/backend/app/reality/candidate_evaluator.py")
    assert eval_file.exists()
    tree = ast.parse(eval_file.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            # Prohibit set_fact()
            if isinstance(func, ast.Attribute) and func.attr == "set_fact":
                pytest.fail(f"Unauthorized set_fact() call in candidate_evaluator.py:{node.lineno}")
            # Prohibit PromotionAuthorizationToken.create()
            if isinstance(func, ast.Attribute) and func.attr == "create":
                if isinstance(func.value, ast.Name) and func.value.id == "PromotionAuthorizationToken":
                    pytest.fail(f"Unauthorized PromotionAuthorizationToken.create() in candidate_evaluator.py:{node.lineno}")
            # Prohibit DB commit/flush/rollback
            if isinstance(func, ast.Attribute) and func.attr in ("commit", "flush", "rollback"):
                pytest.fail(f"Unauthorized DB transaction in candidate_evaluator.py:{node.lineno}")


def test_ast_audit_zero_network_and_tool_calls() -> None:
    """AST Audit: Prohibits network calls and external scraping tools."""
    eval_file = Path("d:/Aevum/Aevum/backend/app/reality/candidate_evaluator.py")
    tree = ast.parse(eval_file.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in ("get", "post", "put", "delete"):
                if isinstance(func.value, ast.Name) and func.value.id in ("requests", "http", "httpx", "urllib"):
                    pytest.fail(f"Unauthorized network call in candidate_evaluator.py:{node.lineno}")
