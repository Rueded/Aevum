"""Unit tests for Evidence, Subject Attribution, and Belief domain models (Phase 7B.3.1).

Verifies:
- Explicit decoupling between BeliefState and RealityState.
- Strict subject attribution (AEVUM, USER, NPC, WORLD).
- Unknown classification (INFERABLE, UNVERIFIABLE, AMBIGUOUS, HIGH_IMPACT, GENUINELY_PRIVATE).
- Dual permissions (inference_permission vs disclosure_permission).
- Temporal validity windows and supersession tracking.
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.reality.belief_models import (
    BeliefClaim,
    EpistemicStatus,
    FactSubject,
    UnknownType,
)
from app.reality.evidence_models import (
    EvidenceExtractionMode,
    EvidenceRecord,
    EvidenceSource,
)
from app.reality.models import CoreFactItem, FactAuthority, FactSource, FactStatus


def test_evidence_record_creation() -> None:
    now = datetime.now(timezone.utc)
    ev = EvidenceRecord(
        id="ev-001",
        source=EvidenceSource.USER_CONVERSATION,
        raw_text="你平时看书的时候一般喝什么？茶还是咖啡？",
        speaker="USER",
        observed_at=now,
        confidence=1.0,
        extraction_mode=EvidenceExtractionMode.EXPLICIT_ASSERTION,
    )
    assert ev.id == "ev-001"
    assert ev.source == EvidenceSource.USER_CONVERSATION
    assert ev.speaker == "USER"
    assert ev.confidence == 1.0
    assert ev.extraction_mode == EvidenceExtractionMode.EXPLICIT_ASSERTION


def test_evidence_record_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        EvidenceRecord(
            id="ev-bad",
            source=EvidenceSource.AEVUM_STATEMENT,
            raw_text="test",
            speaker="AEVUM",
            confidence=1.5,
        )

    with pytest.raises(ValidationError):
        EvidenceRecord(
            id="ev-bad",
            source=EvidenceSource.AEVUM_STATEMENT,
            raw_text="test",
            speaker="AEVUM",
            confidence=-0.1,
        )


def test_belief_claim_subject_attribution() -> None:
    b_aevum = BeliefClaim(
        belief_id="b-001",
        subject=FactSubject.AEVUM,
        fact_key="preferences.study_beverage",
        proposed_value="chamomile tea",
        epistemic_status=EpistemicStatus.PLAUSIBLE,
        confidence=0.9,
    )
    assert b_aevum.subject == FactSubject.AEVUM
    assert b_aevum.epistemic_status == EpistemicStatus.PLAUSIBLE

    b_world = BeliefClaim(
        belief_id="b-002",
        subject=FactSubject.WORLD,
        fact_key="world.astronomy.sun_rises",
        proposed_value="East",
        epistemic_status=EpistemicStatus.KNOWN,
        confidence=1.0,
    )
    assert b_world.subject == FactSubject.WORLD


def test_belief_claim_dual_permissions() -> None:
    # A belief can be internally inferred (inference_permission=True)
    # but not yet permitted to be asserted as undisputed fact (disclosure_permission=False)
    b = BeliefClaim(
        belief_id="b-003",
        subject=FactSubject.AEVUM,
        fact_key="education.major",
        proposed_value="English Literature",
        epistemic_status=EpistemicStatus.PLAUSIBLE,
        confidence=0.85,
        inference_permission=True,
        disclosure_permission=False,
    )
    assert b.inference_permission is True
    assert b.disclosure_permission is False


def test_belief_claim_temporal_validity_and_supersession() -> None:
    b1 = BeliefClaim(
        belief_id="b-004",
        subject=FactSubject.AEVUM,
        fact_key="location.residence",
        proposed_value="Penang",
        epistemic_status=EpistemicStatus.KNOWN,
        confidence=0.95,
        effective_from="2023-09-01",
        effective_until="2024-06-30",
    )
    assert b1.effective_from == "2023-09-01"
    assert b1.effective_until == "2024-06-30"

    b2 = BeliefClaim(
        belief_id="b-005",
        subject=FactSubject.AEVUM,
        fact_key="location.residence",
        proposed_value="Kuala Lumpur",
        epistemic_status=EpistemicStatus.KNOWN,
        confidence=0.95,
        effective_from="2024-07-01",
        supersedes_id=b1.belief_id,
    )
    assert b2.supersedes_id == "b-004"


def test_belief_is_not_core_fact_item() -> None:
    # Strict architectural invariant: BeliefClaim != CoreFactItem
    b = BeliefClaim(
        belief_id="b-006",
        subject=FactSubject.AEVUM,
        fact_key="preferences.study_beverage",
        proposed_value="tea",
    )
    assert not isinstance(b, CoreFactItem)

    c = CoreFactItem(
        key="preferences.study_beverage",
        category="preferences",
        value="tea",
        source=FactSource.AEVUM_INFERRED,
        authority=FactAuthority.AEVUM_CANONICAL,
        status=FactStatus.CANONICAL,
    )
    assert isinstance(c, CoreFactItem)
    assert not isinstance(c, BeliefClaim)


def test_unknown_type_classification() -> None:
    assert UnknownType.INFERABLE.value == "INFERABLE"
    assert UnknownType.UNVERIFIABLE.value == "UNVERIFIABLE"
    assert UnknownType.AMBIGUOUS.value == "AMBIGUOUS"
    assert UnknownType.HIGH_IMPACT.value == "HIGH_IMPACT"
    assert UnknownType.GENUINELY_PRIVATE.value == "GENUINELY_PRIVATE"
