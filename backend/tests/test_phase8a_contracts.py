"""Unit tests for Phase 8A.1 Contracts & DTOs.

Verifies:
1. Frozen immutability and extra='forbid' on all Phase 8A.1 DTOs.
2. InferenceProposalRequest validation and dot-notation enforcement.
3. CandidateEnvelope validation and non-authoritative premise roles.
4. Premise origin categorization (PRIMARY_CANONICAL vs DERIVED_CANONICAL).
5. Deterministic slot-value normalization for major, pathway, career.
6. Explicit rejection of unknown/un-normalizable values.
7. InferenceValuePolicy assessment, anti-obsession guarantees, life-stage rules.
8. Proof that DTOs are Pydantic models, NOT SQLAlchemy ORM models.
9. Proof that Phase 8A.1 contains zero canonical mutation paths.
"""

import ast
import inspect
from pathlib import Path
import pytest
from pydantic import ValidationError

from app.character.core_models import CharacterCore
from app.reality.inference_models import (
    CandidateEnvelope,
    InferenceProposalRequest,
    InferenceValueAssessment,
    InferenceValueTier,
    PremiseOriginCategory,
    PremiseRole,
    categorize_fact_origin,
)
from app.reality.inference_value_policy import InferenceValuePolicy
from app.reality.models import CoreFactItem, FactAuthority, FactSource, FactStatus
from app.reality.slot_normalizer import (
    NormalizationStatus,
    SlotNormalizationResult,
    SlotValueNormalizer,
)


# =============================================================================
# 1. DTO Frozen and Extra Field Invariants
# =============================================================================


def test_inference_proposal_request_frozen_and_extra_forbid() -> None:
    req = InferenceProposalRequest(
        target_slot="education.major",
        domain="education",
        authorized_premise_keys=("traits.musical_talent",),
        premise_snapshots={"traits.musical_talent": "HIGH"},
        known_constraints=("undergrad_requires_secondary",),
        inference_cycle_id="cycle_001",
    )
    # Frozen immutability
    with pytest.raises(ValidationError):
        req.domain = "other"  # type: ignore

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        InferenceProposalRequest(
            target_slot="education.major",
            domain="education",
            authorized_premise_keys=(),
            premise_snapshots={},
            inference_cycle_id="cycle_001",
            unauthorized_extra_field="malicious",  # type: ignore
        )


def test_candidate_envelope_frozen_and_extra_forbid() -> None:
    env = CandidateEnvelope(
        domain="education",
        slot="education.major",
        raw_value="Computer Science",
        suggested_premise_keys=("academics.math",),
        suggested_premise_roles={"academics.math": PremiseRole.DIRECT_SUPPORT},
        rationale="Strong math aptitude.",
    )
    # Frozen immutability
    with pytest.raises(ValidationError):
        env.domain = "other"  # type: ignore

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        CandidateEnvelope(
            domain="education",
            slot="education.major",
            raw_value="CS",
            sneaky_extra_field=123,  # type: ignore
        )


# =============================================================================
# 2. Validation & Dot-Notation Contracts
# =============================================================================


def test_inference_proposal_request_validation() -> None:
    # Target slot must be dot-notated
    with pytest.raises(ValidationError, match="must be dot-notated"):
        InferenceProposalRequest(
            target_slot="major",
            domain="education",
            authorized_premise_keys=(),
            premise_snapshots={},
            inference_cycle_id="cycle_001",
        )

    # Empty fields forbidden
    with pytest.raises(ValidationError, match="must not be empty"):
        InferenceProposalRequest(
            target_slot="   ",
            domain="education",
            authorized_premise_keys=(),
            premise_snapshots={},
            inference_cycle_id="cycle_001",
        )


def test_candidate_envelope_validation() -> None:
    # Slot must be dot-notated
    with pytest.raises(ValidationError, match="must be dot-notated"):
        CandidateEnvelope(
            domain="education",
            slot="major_without_dot",
            raw_value="CS",
        )

    # Empty domain forbidden
    with pytest.raises(ValidationError, match="must not be empty"):
        CandidateEnvelope(
            domain="",
            slot="education.major",
            raw_value="CS",
        )


# =============================================================================
# 3. Premise Origin Semantics (Primary vs Derived Canonical)
# =============================================================================


def test_premise_origin_categorization() -> None:
    # 1. Primary canonical: USER_CONFIGURED
    user_fact = CoreFactItem(
        key="traits.musical_talent",
        category="traits",
        value=True,
        source=FactSource.USER_CONFIGURED,
        authority=FactAuthority.USER_CONFIGURED,
        status=FactStatus.CANONICAL,
    )
    assert categorize_fact_origin(user_fact) == PremiseOriginCategory.PRIMARY_CANONICAL

    # 2. Primary canonical: CONVERSATION
    conv_fact = CoreFactItem(
        key="preferences.music",
        category="preferences",
        value="loves_piano",
        source=FactSource.CONVERSATION,
        authority=FactAuthority.AEVUM_CANONICAL,
        status=FactStatus.CANONICAL,
    )
    assert categorize_fact_origin(conv_fact) == PremiseOriginCategory.PRIMARY_CANONICAL

    # 3. Primary canonical: SYSTEM_BASELINE
    base_fact = CoreFactItem(
        key="identity.species",
        category="identity",
        value="human",
        source=FactSource.SYSTEM_BASELINE,
        authority=FactAuthority.SYSTEM_BASELINE,
        status=FactStatus.CANONICAL,
    )
    assert categorize_fact_origin(base_fact) == PremiseOriginCategory.PRIMARY_CANONICAL

    # 4. Derived canonical: AEVUM_INFERRED
    inferred_fact = CoreFactItem(
        key="education.major",
        category="education",
        value="computer_science",
        source=FactSource.AEVUM_INFERRED,
        authority=FactAuthority.AEVUM_CANONICAL,
        status=FactStatus.CANONICAL,
    )
    assert categorize_fact_origin(inferred_fact) == PremiseOriginCategory.DERIVED_CANONICAL
    # Strict Invariant: An inferred fact can NEVER masquerade as a PRIMARY_CANONICAL fact!
    assert categorize_fact_origin(inferred_fact) != PremiseOriginCategory.PRIMARY_CANONICAL

    # 5. Non-canonical fact
    candidate_fact = CoreFactItem(
        key="education.university",
        category="education",
        value="USM",
        source=FactSource.CONVERSATION,
        authority=FactAuthority.AEVUM_CANONICAL,
        status=FactStatus.CANDIDATE,
    )
    assert categorize_fact_origin(candidate_fact) == PremiseOriginCategory.NON_CANONICAL


# =============================================================================
# 4. Slot Value Normalization (Major, Pathway, Career)
# =============================================================================


def test_slot_value_normalizer_major_success() -> None:
    cases = [
        ("CS", "computer_science"),
        ("Computer Science", "computer_science"),
        ("com sci", "computer_science"),
        ("bsc computer science", "computer_science"),
        ("computer science (b.sc)", "computer_science"),
        ("SE", "software_engineering"),
        ("software engineering", "software_engineering"),
        ("Music", "music_performance"),
        ("music performance", "music_performance"),
        ("piano performance", "music_performance"),
        ("Sound Engineering", "sound_engineering"),
        ("audio production", "sound_engineering"),
        ("Digital Media", "digital_media"),
        ("multimedia design", "digital_media"),
        ("BIS", "business_information_systems"),
        ("Information Systems", "business_information_systems"),
        ("EE", "electrical_engineering"),
        ("multimedia", "multimedia"),
    ]
    for raw, expected in cases:
        res = SlotValueNormalizer.normalize("education.major", raw)
        assert res.is_valid is True
        assert res.status == NormalizationStatus.VALID
        assert res.normalized_value == expected


def test_slot_value_normalizer_major_invalid() -> None:
    res = SlotValueNormalizer.normalize("education.major", "Astrophysics and Alchemy")
    assert res.is_valid is False
    assert res.status == NormalizationStatus.INVALID
    assert res.normalized_value == "Astrophysics and Alchemy"
    assert "Unknown or un-normalizable major" in (res.rejection_reason or "")


def test_slot_value_normalizer_pathway_success() -> None:
    cases = [
        ("STPM", "STPM"),
        ("form 6", "STPM"),
        ("form six", "STPM"),
        ("tingkatan 6", "STPM"),
        ("matrikulasi", "MATRIKULASI"),
        ("matriculation", "MATRIKULASI"),
        ("matrik", "MATRIKULASI"),
        ("foundation", "FOUNDATION"),
        ("foundation in science", "FOUNDATION"),
        ("diploma", "DIPLOMA"),
        ("A-Level", "A_LEVEL"),
        ("a level", "A_LEVEL"),
    ]
    for raw, expected in cases:
        res = SlotValueNormalizer.normalize("education.pathway", raw)
        assert res.is_valid is True
        assert res.normalized_value == expected


def test_slot_value_normalizer_pathway_invalid() -> None:
    res = SlotValueNormalizer.normalize("education.pathway", "Ancient Sorcery Apprenticeship")
    assert res.is_valid is False
    assert res.status == NormalizationStatus.INVALID
    assert "Unknown or un-normalizable pathway" in (res.rejection_reason or "")


def test_slot_value_normalizer_career_success() -> None:
    cases = [
        ("software engineer", "software_engineer"),
        ("swe", "software_engineer"),
        ("programmer", "software_engineer"),
        ("game dev", "game_developer"),
        ("game developer", "game_developer"),
        ("musician", "musician"),
        ("pianist", "musician"),
        ("sound designer", "sound_designer"),
        ("music producer", "music_producer"),
        ("data analyst", "data_analyst"),
        ("researcher", "academic_researcher"),
    ]
    for raw, expected in cases:
        res = SlotValueNormalizer.normalize("career.aspiration", raw)
        assert res.is_valid is True
        assert res.normalized_value == expected


def test_slot_value_normalizer_career_invalid() -> None:
    res = SlotValueNormalizer.normalize("career.aspiration", "Galactic Emperor")
    assert res.is_valid is False
    assert res.status == NormalizationStatus.INVALID
    assert "Unknown or un-normalizable career aspiration" in (res.rejection_reason or "")


def test_slot_value_normalizer_unsupported_slot() -> None:
    res = SlotValueNormalizer.normalize("identity.name", "Alice")
    assert res.is_valid is False
    assert res.status == NormalizationStatus.UNSUPPORTED_SLOT
    assert "not currently configured" in (res.rejection_reason or "")

    res_empty = SlotValueNormalizer.normalize("", "anything")
    assert res_empty.is_valid is False
    assert res_empty.status == NormalizationStatus.UNSUPPORTED_SLOT


# =============================================================================
# 5. Inference Value Policy (Anti-Obsession & Life Stage Assessment)
# =============================================================================


def test_inference_value_policy_forbidden_slots() -> None:
    for slot in ("identity.name", "identity.birth_year", "identity.species", "world.physics"):
        res = InferenceValuePolicy.evaluate_slot(slot)
        assert res.tier == InferenceValueTier.ZERO
        assert res.is_worth_inferring is False
        assert "Forbidden slot" in res.reason


def test_inference_value_policy_speculative_narrative_slots() -> None:
    for slot in ("relationships.childhood_friend", "identity.pet_name", "narrative.trauma_history"):
        res = InferenceValuePolicy.evaluate_slot(slot)
        assert res.tier == InferenceValueTier.ZERO
        assert res.is_worth_inferring is False
        assert "Unanchored speculative narrative slot" in res.reason


def test_inference_value_policy_low_impact_preferences() -> None:
    for slot in ("preferences.study_beverage", "preferences.favorite_color", "lifestyle.commute_mode"):
        res = InferenceValuePolicy.evaluate_slot(slot)
        assert res.tier == InferenceValueTier.LOW
        assert res.is_worth_inferring is False
        assert "Low-impact preference detail" in res.reason


def test_inference_value_policy_high_value_slots() -> None:
    # education.major is high value
    res_major = InferenceValuePolicy.evaluate_slot("education.major")
    assert res_major.tier == InferenceValueTier.HIGH
    assert res_major.is_worth_inferring is True

    # education.pathway is high value
    res_path = InferenceValuePolicy.evaluate_slot("education.pathway")
    assert res_path.tier == InferenceValueTier.HIGH
    assert res_path.is_worth_inferring is True

    # career.aspiration is medium value
    res_career = InferenceValuePolicy.evaluate_slot("career.aspiration")
    assert res_career.tier == InferenceValueTier.MEDIUM
    assert res_career.is_worth_inferring is True


def test_inference_value_policy_inapplicable_life_stage_constraint() -> None:
    # If character is already postgraduate, undergraduate major inference is inapplicable
    grad_core = CharacterCore(
        character_id="aevum",
        facts={
            "education.level": CoreFactItem(
                key="education.level",
                category="education",
                value="postgraduate",
                source=FactSource.USER_CONFIGURED,
                authority=FactAuthority.USER_CONFIGURED,
                status=FactStatus.CANONICAL,
            )
        },
    )
    res = InferenceValuePolicy.evaluate_slot("education.major", core=grad_core)
    assert res.is_worth_inferring is False
    assert "post-undergraduate" in res.reason

    # If character is already undergraduate, pre-u pathway inference is inapplicable
    undergrad_core = CharacterCore(
        character_id="aevum",
        facts={
            "education.level": CoreFactItem(
                key="education.level",
                category="education",
                value="undergraduate",
                source=FactSource.USER_CONFIGURED,
                authority=FactAuthority.USER_CONFIGURED,
                status=FactStatus.CANONICAL,
            )
        },
    )
    res_path = InferenceValuePolicy.evaluate_slot("education.pathway", core=undergrad_core)
    assert res_path.is_worth_inferring is False
    assert "already in or past university" in res_path.reason


def test_inference_value_policy_already_canonical_slot() -> None:
    core_with_major = CharacterCore(
        character_id="aevum",
        facts={
            "education.major": CoreFactItem(
                key="education.major",
                category="education",
                value="music_performance",
                source=FactSource.AEVUM_INFERRED,
                authority=FactAuthority.AEVUM_CANONICAL,
                status=FactStatus.CANONICAL,
            )
        },
    )
    res = InferenceValuePolicy.evaluate_slot("education.major", core=core_with_major)
    assert res.tier == InferenceValueTier.ZERO
    assert res.is_worth_inferring is False
    assert "already contains canonical fact" in res.reason


def test_inference_value_policy_user_locked_slot() -> None:
    core_locked = CharacterCore(
        character_id="aevum",
        facts={
            "education.major": CoreFactItem(
                key="education.major",
                category="education",
                value="computer_science",
                source=FactSource.USER_CONFIGURED,
                authority=FactAuthority.USER_LOCKED,
                status=FactStatus.CANONICAL,
                locked=True,
            )
        },
    )
    res = InferenceValuePolicy.evaluate_slot("education.major", core=core_locked)
    assert res.tier == InferenceValueTier.ZERO
    assert res.is_worth_inferring is False
    assert "locked by user authority" in res.reason


# =============================================================================
# 6. Proof: DTOs are NOT SQLAlchemy ORM Models
# =============================================================================


def test_dtos_are_not_sqlalchemy_orm_models() -> None:
    dtos = [
        InferenceProposalRequest,
        CandidateEnvelope,
        SlotNormalizationResult,
        InferenceValueAssessment,
    ]
    for dto_cls in dtos:
        assert not hasattr(dto_cls, "__tablename__"), f"{dto_cls.__name__} must not have __tablename__"
        assert not hasattr(dto_cls, "_sa_class_manager"), f"{dto_cls.__name__} must not be managed by SQLAlchemy"
        # Confirm pure Pydantic inheritance
        from pydantic import BaseModel
        assert issubclass(dto_cls, BaseModel), f"{dto_cls.__name__} must inherit from BaseModel"


# =============================================================================
# 7. AST Singularity: Zero Canonical Mutation in Phase 8A.1
# =============================================================================


def test_zero_canonical_mutation_in_phase8a1_modules() -> None:
    """Static AST check verifying zero set_fact or token creation in 8A.1 modules."""
    module_files = [
        Path("app/reality/inference_models.py"),
        Path("app/reality/slot_normalizer.py"),
        Path("app/reality/inference_value_policy.py"),
    ]
    for rel_path in module_files:
        full_path = Path("d:/Aevum/Aevum/backend") / rel_path
        assert full_path.exists(), f"Module {full_path} must exist"
        tree = ast.parse(full_path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                # Prohibit set_fact calls
                if isinstance(func, ast.Attribute) and func.attr == "set_fact":
                    pytest.fail(f"Unauthorized set_fact() call found in {rel_path}:{node.lineno}")
                # Prohibit token minting
                if isinstance(func, ast.Attribute) and func.attr == "create":
                    if isinstance(func.value, ast.Name) and func.value.id == "PromotionAuthorizationToken":
                        pytest.fail(f"Unauthorized PromotionAuthorizationToken.create() in {rel_path}:{node.lineno}")
                # Prohibit direct SQL execute
                if isinstance(func, ast.Attribute) and func.attr in ("commit", "flush", "rollback"):
                    pytest.fail(f"Unauthorized DB transaction call in {rel_path}:{node.lineno}")
