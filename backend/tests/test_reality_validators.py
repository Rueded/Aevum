"""Unit tests for Reality Validators (Phase 7B.3.3).

Verifies ConsistencyValidator, TimelineValidator, CausalityValidator,
and WorldKnowledgeValidator.
"""

from app.character.core_models import CharacterCore
from app.reality.candidate_models import CandidateFact, InferenceScope, RealityImpact
from app.reality.models import CoreFactItem, FactAuthority, FactSource, FactStatus
from app.reality.validators import (
    CausalityValidator,
    ConsistencyValidator,
    TimelineValidator,
    WorldKnowledgeValidator,
)


def _make_sample_core(locked_key: str = "identity.name") -> CharacterCore:
    facts = {
        "identity.name": CoreFactItem(
            key="identity.name",
            category="identity",
            value="Aevum",
            source=FactSource.SYSTEM_BASELINE,
            authority=FactAuthority.USER_LOCKED,
            status=FactStatus.CANONICAL,
            locked=True,
        ),
        "identity.age": CoreFactItem(
            key="identity.age",
            category="identity",
            value=20,
            source=FactSource.SYSTEM_BASELINE,
            authority=FactAuthority.SYSTEM_BASELINE,
            status=FactStatus.CANONICAL,
            locked=False,
        ),
        "education.pre_u": CoreFactItem(
            key="education.pre_u",
            category="education",
            value="STPM",
            source=FactSource.AEVUM_INFERRED,
            authority=FactAuthority.AEVUM_CANONICAL,
            status=FactStatus.CANONICAL,
            locked=False,
        ),
    }
    return CharacterCore(character_id="aevum", facts=facts)


def test_consistency_validator_locked_invariant() -> None:
    core = _make_sample_core()
    # Candidate trying to change locked identity.name
    cand = CandidateFact(
        id="cand-001",
        fact_key="identity.name",
        value="Alice",
        impact=RealityImpact.HIGH,
    )
    result = ConsistencyValidator.validate(cand, core)
    assert result.is_valid is False
    assert any("locked" in r for r in result.reasons)


def test_consistency_validator_compatible_candidate() -> None:
    core = _make_sample_core()
    cand = CandidateFact(
        id="cand-002",
        fact_key="preferences.study_beverage",
        value="warm tea",
        impact=RealityImpact.LOW,
    )
    result = ConsistencyValidator.validate(cand, core)
    assert result.is_valid is True


def test_timeline_validator_stpm_undergraduate_year() -> None:
    core = _make_sample_core()

    # Age 20, STPM -> Year 1 or 2 is plausible
    cand_yr2 = CandidateFact(
        id="cand-yr2",
        fact_key="education.year",
        value=2,
        impact=RealityImpact.LOW,
        inference_scope=InferenceScope.DEPENDENT,
    )
    res_yr2 = TimelineValidator.validate(cand_yr2, core)
    assert res_yr2.is_valid is True

    # Age 20 -> Year 4 doctorate or graduated 5 years ago is chronologically impossible
    cand_doc = CandidateFact(
        id="cand-doc",
        fact_key="education.year",
        value=5,
        impact=RealityImpact.HIGH,
        inference_scope=InferenceScope.SPECULATIVE,
    )
    res_doc = TimelineValidator.validate(cand_doc, core)
    assert res_doc.is_valid is False
    assert any("chronologically implausible" in r for r in res_doc.reasons)


def test_causality_validator_physical_laws() -> None:
    cand_sun_west = CandidateFact(
        id="cand-sun",
        fact_key="world.astronomy.sun_rises",
        value="West",
        impact=RealityImpact.LOW,
    )
    res_sun = CausalityValidator.validate(cand_sun_west)
    assert res_sun.is_valid is False
    assert any("violates static physical fact" in r for r in res_sun.reasons)

    cand_sun_east = CandidateFact(
        id="cand-sun-east",
        fact_key="world.astronomy.sun_rises",
        value="East",
        impact=RealityImpact.LOW,
    )
    res_east = CausalityValidator.validate(cand_sun_east)
    assert res_east.is_valid is True


def test_world_knowledge_validator_campuses() -> None:
    cand_usm_kl = CandidateFact(
        id="cand-usm-kl",
        fact_key="world.usm.main_campus",
        value="Kuala Lumpur",
        impact=RealityImpact.HIGH,
    )
    res_usm = WorldKnowledgeValidator.validate(cand_usm_kl)
    assert res_usm.is_valid is False

    cand_usm_penang = CandidateFact(
        id="cand-usm-p",
        fact_key="world.usm.main_campus",
        value="Penang",
        impact=RealityImpact.HIGH,
    )
    res_usm_p = WorldKnowledgeValidator.validate(cand_usm_penang)
    assert res_usm_p.is_valid is True
