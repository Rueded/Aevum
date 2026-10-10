"""Unit tests for Phase 8A.3 LifeHypothesisProposer & DeterministicLifeHypothesisProposer.

Verifies:
1. Sufficient request produces 2–4 distinct candidates.
2. Cardinality invariant: never produces a single autonomous candidate (min 2).
3. Cardinality invariant: maximum 4 candidates.
4. Candidates are meaningfully distinct (unique normalized values).
5. All premise keys in candidates are strictly authorized by the request.
6. Unauthorized premise keys are filtered out / rejected.
7. Candidate rationale is non-epistemic metadata.
8. CandidateEnvelope remains a transient DTO (not SQLAlchemy model).
9. AST Audit: zero set_fact calls.
10. AST Audit: zero PromotionAuthorizationToken creation calls.
11. AST Audit: zero DB commit/flush/rollback calls.
12. AST Audit: zero web/tool/network calls.
13. Deterministic repeated invocation produces identical candidates.
14. SlotValueNormalizer is applied (values are canonical tokens).
15. Unknown/un-normalizable candidates are pruned cleanly.
16. Insufficiently constrained request produces no candidates (returns empty ()).
17. Empty or invalid request is rejected cleanly.
18. Unsupported target slot returns empty ().
19. BoundedLLMProposer cleanly falls back to deterministic proposer.
20. Pathway choices (STPM vs Matrikulasi vs Foundation) preserve 2-3 genuine options.
"""

import ast
from pathlib import Path
import pytest

from app.reality.inference_models import CandidateEnvelope, InferenceProposalRequest, PremiseRole
from app.reality.proposer import BoundedLLMProposer, DeterministicLifeHypothesisProposer


# =============================================================================
# 1. Candidate Cardinality & Diversity (2 <= k <= 4)
# =============================================================================


@pytest.mark.asyncio
async def test_proposer_generates_between_two_and_four_candidates_for_major() -> None:
    proposer = DeterministicLifeHypothesisProposer()
    req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=(
            "traits.musical_talent",
            "skills.instrument_playing",
            "academics.spm_math_grade",
            "values.parental_expectation",
            "family.socioeconomic_tier",
        ),
        premise_snapshots={
            "traits.musical_talent": True,
            "skills.instrument_playing": "piano",
            "academics.spm_math_grade": "C",
            "values.parental_expectation": "career_stability",
            "family.socioeconomic_tier": "MIDDLE_CLASS",
        },
        known_constraints=("undergrad_requires_secondary",),
        inference_cycle_id="cycle_major_01",
    )
    candidates = await proposer.propose_hypotheses(req)
    # Cardinality invariant: strictly 2 <= k <= 4
    assert 2 <= len(candidates) <= 4

    # Confirm candidates are meaningfully distinct
    values = [c.raw_value for c in candidates]
    assert len(values) == len(set(values)), "Candidates must have unique normalized values"

    # Confirm known diverse pathways are represented
    assert "music_performance" in values
    assert "computer_science" in values or "sound_engineering" in values


@pytest.mark.asyncio
async def test_proposer_never_emits_a_single_autonomous_candidate() -> None:
    # If constraints/premises only support 1 option, proposer MUST return ()
    # to prevent single-candidate self-promotion under Gate 6
    proposer = DeterministicLifeHypothesisProposer()
    # A request with only a single non-branching premise that cannot synthesize 2 distinct options
    sparse_req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=("preferences.unknown_sparse",),
        premise_snapshots={"preferences.unknown_sparse": "value"},
        inference_cycle_id="cycle_sparse",
    )
    candidates = await proposer.propose_hypotheses(sparse_req)
    # Must NEVER emit 1 candidate! Must be either >= 2 or empty ()
    assert len(candidates) != 1
    assert candidates == ()


@pytest.mark.asyncio
async def test_proposer_caps_at_maximum_four_candidates() -> None:
    proposer = DeterministicLifeHypothesisProposer()
    rich_req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=(
            "traits.musical_talent",
            "skills.instrument_playing",
            "skills.programming",
            "academics.spm_math_grade",
            "interests",
            "values.creativity",
            "values.parental_expectation",
            "family.socioeconomic_tier",
        ),
        premise_snapshots={
            "traits.musical_talent": True,
            "skills.instrument_playing": "piano",
            "skills.programming": "Python",
            "academics.spm_math_grade": "A",
            "interests": ["music", "gaming"],
            "values.creativity": "HIGH",
            "values.parental_expectation": "career_stability",
            "family.socioeconomic_tier": "MIDDLE_CLASS",
        },
        inference_cycle_id="cycle_rich",
    )
    candidates = await proposer.propose_hypotheses(rich_req)
    assert 2 <= len(candidates) <= 4


# =============================================================================
# 2. Premise Discipline & Authorization Invariant
# =============================================================================


@pytest.mark.asyncio
async def test_candidate_premises_are_strictly_authorized_subset() -> None:
    proposer = DeterministicLifeHypothesisProposer()
    authorized = (
        "traits.musical_talent",
        "skills.instrument_playing",
        "academics.spm_math_grade",
    )
    req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=authorized,
        premise_snapshots={
            "traits.musical_talent": True,
            "skills.instrument_playing": "piano",
            "academics.spm_math_grade": "C",
        },
        inference_cycle_id="cycle_auth_01",
    )
    candidates = await proposer.propose_hypotheses(req)
    assert len(candidates) >= 2

    for c in candidates:
        for p_key in c.suggested_premise_keys:
            assert p_key in authorized, f"Premise '{p_key}' was not in authorized keys {authorized}"


@pytest.mark.asyncio
async def test_rationale_is_display_only_metadata() -> None:
    proposer = DeterministicLifeHypothesisProposer()
    req = InferenceProposalRequest(
        target_slot="education.pathway",
        domain="education",
        authorized_premise_keys=("academics.spm_overall", "traits.challenge_preference"),
        premise_snapshots={
            "academics.spm_overall": "8A",
            "traits.challenge_preference": "HIGH",
        },
        inference_cycle_id="cycle_pathway_01",
    )
    candidates = await proposer.propose_hypotheses(req)
    assert len(candidates) >= 2

    for c in candidates:
        assert isinstance(c.rationale, str)
        assert len(c.rationale) > 0
        # Rationale must not be treated as a premise key
        assert c.rationale not in c.suggested_premise_keys


# =============================================================================
# 3. Normalization Invariant
# =============================================================================


@pytest.mark.asyncio
async def test_proposer_normalizes_candidate_values() -> None:
    proposer = DeterministicLifeHypothesisProposer()
    req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=("traits.musical_talent", "skills.programming"),
        premise_snapshots={
            "traits.musical_talent": True,
            "skills.programming": "Python",
        },
        inference_cycle_id="cycle_norm_01",
    )
    candidates = await proposer.propose_hypotheses(req)
    assert len(candidates) >= 2

    # Check normalized canonical token format
    for c in candidates:
        assert c.raw_value in (
            "music_performance",
            "computer_science",
            "sound_engineering",
            "digital_media",
        )


@pytest.mark.asyncio
async def test_pathway_proposals_include_genuine_alternatives() -> None:
    proposer = DeterministicLifeHypothesisProposer()
    req = InferenceProposalRequest(
        target_slot="education.pathway",
        domain="education",
        authorized_premise_keys=(
            "academics.spm_overall",
            "traits.challenge_preference",
            "family.socioeconomic_tier",
            "preferences.study_duration",
        ),
        premise_snapshots={
            "academics.spm_overall": "Straight As",
            "traits.challenge_preference": "HIGH",
            "family.socioeconomic_tier": "MIDDLE_CLASS",
            "preferences.study_duration": "short",
        },
        inference_cycle_id="cycle_pathway_02",
    )
    candidates = await proposer.propose_hypotheses(req)
    assert len(candidates) >= 2

    values = [c.raw_value for c in candidates]
    # Check that STPM, Matrikulasi, and Foundation alternatives are available
    assert "STPM" in values
    assert "MATRIKULASI" in values or "FOUNDATION" in values


@pytest.mark.asyncio
async def test_career_aspiration_proposals_with_major_foundation() -> None:
    proposer = DeterministicLifeHypothesisProposer()
    req = InferenceProposalRequest(
        target_slot="career.aspiration",
        domain="career",
        authorized_premise_keys=("education.major", "skills.programming"),
        premise_snapshots={
            "education.major": "computer_science",
            "skills.programming": "Python",
        },
        inference_cycle_id="cycle_career_01",
    )
    candidates = await proposer.propose_hypotheses(req)
    assert len(candidates) >= 2

    values = [c.raw_value for c in candidates]
    assert "software_engineer" in values
    assert "game_developer" in values


# =============================================================================
# 4. Error & Edge Case Handling
# =============================================================================


@pytest.mark.asyncio
async def test_unsupported_slot_returns_empty_sequence() -> None:
    proposer = DeterministicLifeHypothesisProposer()
    req = InferenceProposalRequest(
        target_slot="unsupported.slot_key",
        domain="unsupported",
        authorized_premise_keys=("some.key",),
        premise_snapshots={"some.key": "val"},
        inference_cycle_id="cycle_unsup",
    )
    candidates = await proposer.propose_hypotheses(req)
    assert candidates == ()


@pytest.mark.asyncio
async def test_empty_authorized_keys_returns_empty_sequence() -> None:
    proposer = DeterministicLifeHypothesisProposer()
    req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=(),
        premise_snapshots={},
        inference_cycle_id="cycle_empty",
    )
    candidates = await proposer.propose_hypotheses(req)
    assert candidates == ()


@pytest.mark.asyncio
async def test_proposer_is_deterministic_on_repeated_calls() -> None:
    proposer = DeterministicLifeHypothesisProposer()
    req = InferenceProposalRequest(
        target_slot="education.pathway",
        domain="education",
        authorized_premise_keys=("academics.spm_overall", "traits.challenge_preference"),
        premise_snapshots={
            "academics.spm_overall": "8A",
            "traits.challenge_preference": "HIGH",
        },
        inference_cycle_id="cycle_det",
    )
    run1 = await proposer.propose_hypotheses(req)
    run2 = await proposer.propose_hypotheses(req)
    assert len(run1) == len(run2)
    assert [c.raw_value for c in run1] == [c.raw_value for c in run2]
    assert [c.suggested_premise_keys for c in run1] == [c.suggested_premise_keys for c in run2]


@pytest.mark.asyncio
async def test_bounded_llm_proposer_falls_back_cleanly_when_no_client() -> None:
    proposer = BoundedLLMProposer(llm_client=None)
    req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=("traits.musical_talent", "skills.instrument_playing"),
        premise_snapshots={
            "traits.musical_talent": True,
            "skills.instrument_playing": "piano",
        },
        inference_cycle_id="cycle_llm_fb",
    )
    candidates = await proposer.propose_hypotheses(req)
    assert len(candidates) >= 2
    assert any(c.raw_value == "music_performance" for c in candidates)


# =============================================================================
# 5. Proof: CandidateEnvelope is NOT a Database ORM Model
# =============================================================================


def test_candidate_envelope_is_pure_transient_dto() -> None:
    assert not hasattr(CandidateEnvelope, "__tablename__")
    assert not hasattr(CandidateEnvelope, "_sa_class_manager")
    from pydantic import BaseModel
    assert issubclass(CandidateEnvelope, BaseModel)


# =============================================================================
# 6. AST Singularity: Zero Canonical Mutation in Proposer Module
# =============================================================================


def test_proposer_ast_audit_zero_mutation_and_zero_tokens() -> None:
    proposer_file = Path("d:/Aevum/Aevum/backend/app/reality/proposer.py")
    assert proposer_file.exists()
    tree = ast.parse(proposer_file.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            # Prohibit set_fact()
            if isinstance(func, ast.Attribute) and func.attr == "set_fact":
                pytest.fail(f"Unauthorized set_fact() call found in proposer:{node.lineno}")
            # Prohibit PromotionAuthorizationToken.create()
            if isinstance(func, ast.Attribute) and func.attr == "create":
                if isinstance(func.value, ast.Name) and func.value.id == "PromotionAuthorizationToken":
                    pytest.fail(f"Unauthorized PromotionAuthorizationToken.create() in proposer:{node.lineno}")
            # Prohibit DB commit/flush/rollback
            if isinstance(func, ast.Attribute) and func.attr in ("commit", "flush", "rollback"):
                pytest.fail(f"Unauthorized DB transaction operation in proposer:{node.lineno}")
            # Prohibit network/requests/httpx calls
            if isinstance(func, ast.Attribute) and func.attr in ("get", "post", "put", "delete"):
                if isinstance(func.value, ast.Name) and func.value.id in ("requests", "http", "httpx", "urllib"):
                    pytest.fail(f"Unauthorized network call in proposer:{node.lineno}")


def test_proposer_ast_audit_zero_authority_imports() -> None:
    proposer_file = Path("d:/Aevum/Aevum/backend/app/reality/proposer.py")
    tree = ast.parse(proposer_file.read_text(encoding="utf-8"))

    prohibited_names = {
        "BiographyPromotionService",
        "PromotionAuthorizationToken",
        "CharacterCoreService",
        "CandidateRepository",
        "CompetitionService",
        "ChoiceService",
        "RealityRepairService",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in prohibited_names:
                    pytest.fail(f"Prohibited import {alias.name} in proposer.py")
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in prohibited_names:
                    pytest.fail(f"Prohibited from-import {alias.name} in proposer.py")


@pytest.mark.asyncio
async def test_invalid_request_type_returns_empty_tuple() -> None:
    proposer = DeterministicLifeHypothesisProposer()
    # Passing an arbitrary dict or object instead of InferenceProposalRequest
    res = await proposer.propose_hypotheses("not_a_request")  # type: ignore
    assert res == ()


@pytest.mark.asyncio
async def test_candidate_envelope_roles_are_non_authoritative_enums() -> None:
    proposer = DeterministicLifeHypothesisProposer()
    req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=("traits.musical_talent", "skills.instrument_playing"),
        premise_snapshots={"traits.musical_talent": True, "skills.instrument_playing": "piano"},
        inference_cycle_id="cycle_roles",
    )
    candidates = await proposer.propose_hypotheses(req)
    assert len(candidates) >= 2
    for c in candidates:
        for k, role in c.suggested_premise_roles.items():
            assert isinstance(role, PremiseRole)
            assert role in (PremiseRole.DIRECT_SUPPORT, PremiseRole.CONTEXT_SUPPORT, PremiseRole.CONTRADICTING)


@pytest.mark.asyncio
async def test_proposer_preserves_request_immutability() -> None:
    proposer = DeterministicLifeHypothesisProposer()
    snapshots = {"traits.musical_talent": True, "skills.instrument_playing": "piano"}
    auth_keys = ("traits.musical_talent", "skills.instrument_playing")
    req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=auth_keys,
        premise_snapshots=snapshots,
        inference_cycle_id="cycle_immutable",
    )
    _ = await proposer.propose_hypotheses(req)
    # Ensure request and snapshots were not modified
    assert req.premise_snapshots == {"traits.musical_talent": True, "skills.instrument_playing": "piano"}
    assert req.authorized_premise_keys == auth_keys


@pytest.mark.asyncio
async def test_unnormalizable_candidate_is_pruned_cleanly() -> None:
    # Deterministic proposer normalizes and discards non-canonical tokens
    proposer = DeterministicLifeHypothesisProposer()
    # A request that generates candidates: verify all returned values are strictly valid
    req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=("traits.musical_talent", "academics.spm_math_grade"),
        premise_snapshots={"traits.musical_talent": True, "academics.spm_math_grade": "A"},
        inference_cycle_id="cycle_prune",
    )
    candidates = await proposer.propose_hypotheses(req)
    assert len(candidates) >= 2
    for c in candidates:
        # Each raw_value must be non-empty and snake_case canonical token
        assert c.raw_value.islower()
        assert " " not in c.raw_value


def test_candidate_envelope_serialization() -> None:
    envelope = CandidateEnvelope(
        domain="education",
        slot="education.major",
        raw_value="music_performance",
        suggested_premise_keys=("traits.musical_talent",),
        suggested_premise_roles={"traits.musical_talent": PremiseRole.DIRECT_SUPPORT},
        rationale="Artistic talent alignment.",
    )
    dumped = envelope.model_dump()
    assert dumped["raw_value"] == "music_performance"
    assert dumped["suggested_premise_roles"]["traits.musical_talent"] == "DIRECT_SUPPORT"
    json_str = envelope.model_dump_json()
    assert "music_performance" in json_str
