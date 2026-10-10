"""Adaptive Belief Revision Engine (Phase 14.4).

Governed by ADR-025 (Revision 1):
- 14.4-A: Non-Destructive Revision:
    When a belief is contradicted or superseded, its prior state is transitioned
    to SUPERSEDED / REJECTED and preserved in an append-only audit trail. Destructive
    deletions are strictly forbidden (Lock 4).
- 14.4-B: Candidate != Evidence (Lock 11):
    Candidate hypotheses are NOT evidence. Evidence must originate from PRIMARY_CANONICAL
    facts, user-confirmed statements, or verified objective world lore.
- 14.4-C: Canonical Fact Demotion Protection (Lock 8):
    Canonical facts cannot be silently demoted or deleted by autonomous construction.
    Canonical supersession requires the full reconciliation / repair pipeline.
- 14.4-D: Revision != Canonical Mutation:
    Belief revision adjusts candidate lifecycle state and internal belief records.
    It NEVER mutates canonical reality directly (zero set_fact, zero token minting).
- 14.4-E: Bounded Context (Decision D4):
    Permanent storage in append-only repository; context retrieval for prompts is
    strictly bounded (e.g., recent_k=5) to avoid unbounded prompt inflation.

Constitutional Locks (ADR-025):
  Lock 4  — Historical Lineage & Non-Destructive Revision
  Lock 8  — Canonical Facts Cannot Be Demoted by Construction
  Lock 10 — Belief Maturity != Truth
  Lock 11 — Candidate != Evidence
"""

from __future__ import annotations

from datetime import datetime, timezone
import enum
import logging
from typing import Any, Optional, Sequence
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.character.core_models import CharacterCore
from app.reality.candidate_models import CandidateHypothesis, CandidateLifecycleState
from app.reality.candidate_repository import CandidateRepository
from app.reality.models import FactStatus

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BeliefRevisionKind(str, enum.Enum):
    """Categorical taxonomy of belief revision outcomes."""

    CONFIRMATION = "CONFIRMATION"                  # New evidence directly corroborates existing belief
    PARTIAL_CONFIRMATION = "PARTIAL_CONFIRMATION"  # New evidence partially aligns with existing belief
    CONTRADICTION = "CONTRADICTION"                # New evidence contradicts existing belief without a definitive replacement
    SUPERSESSION = "SUPERSESSION"                  # New evidence establishes a newer/better-grounded fact replacing prior belief
    EXPIRY = "EXPIRY"                              # Belief lapsed or invalidated by temporal/lifecycle bounds


class EvidenceSourceType(str, enum.Enum):
    """Provenance origin of incoming evidence evaluated in revision (Lock 11)."""

    USER_STATEMENT = "USER_STATEMENT"              # Direct user utterance / conversational confirmation
    PRIMARY_CANONICAL = "PRIMARY_CANONICAL"        # Confirmed fact in CharacterCore
    WORLD_FACT = "WORLD_FACT"                      # Verified objective geographic/physical lore
    CANDIDATE_HYPOTHESIS = "CANDIDATE_HYPOTHESIS"  # Unpromoted hypothesis (FORBIDDEN as evidence: Lock 11)


# ---------------------------------------------------------------------------
# Immutable DTOs
# ---------------------------------------------------------------------------

class IncomingEvidenceItem(BaseModel):
    """Immutable representation of evidence presented for belief revision evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    source_type: EvidenceSourceType
    slot_name: str
    asserted_value: Any
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    is_definitive_replacement: bool = Field(
        default=False,
        description="True if this evidence authoritatively replaces the prior belief.",
    )
    rationale: str = ""


class BeliefRevisionRecord(BaseModel):
    """Immutable append-only audit record of a belief revision event (Lock 4, D4).

    Constitutional Invariants:
    - Never destructively modified or deleted.
    - Preserves historical lineage of Aevum's belief evolution.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    revision_id: str
    character_id: str = "aevum"
    slot_name: str
    revision_kind: BeliefRevisionKind
    prior_value: Optional[Any] = None
    revised_value: Optional[Any] = None
    prior_candidate_id: Optional[str] = None
    new_candidate_id: Optional[str] = None
    trigger_cycle_id: str
    rationale: str
    created_at: datetime = Field(default_factory=_utc_now)


class BeliefRevisionProposal(BaseModel):
    """Immutable outcome of AdaptiveBeliefRevisionEngine evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    is_valid_revision: bool
    revision_kind: BeliefRevisionKind
    record: Optional[BeliefRevisionRecord] = None
    rejection_reason: Optional[str] = None
    target_lifecycle_state: Optional[CandidateLifecycleState] = None


# ---------------------------------------------------------------------------
# Append-Only Revision Repository (Lock 4, Decision D4)
# ---------------------------------------------------------------------------

class BeliefRevisionRepository:
    """Permanent append-only repository for BeliefRevisionRecords.

    Storage:
    Permanent audit trail. Destructive deletions are strictly prohibited.
    Context:
    Retrieval for prompt generation is bounded (get_recent, default limit=5).
    """

    def __init__(self) -> None:
        self._records: list[BeliefRevisionRecord] = []

    def append(self, record: BeliefRevisionRecord) -> None:
        """Append a new revision record. Append-only; never mutates existing."""
        self._records.append(record)

    def get_history(
        self,
        character_id: str = "aevum",
        slot_name: Optional[str] = None,
        limit: int = 50,
    ) -> list[BeliefRevisionRecord]:
        """Query permanent audit history."""
        results = [
            r for r in self._records
            if r.character_id == character_id and (slot_name is None or r.slot_name == slot_name)
        ]
        return results[-limit:]

    def get_recent(
        self,
        character_id: str = "aevum",
        limit: int = 5,
    ) -> list[BeliefRevisionRecord]:
        """Bounded context retrieval for prompt context assembly (Decision D4)."""
        results = [r for r in self._records if r.character_id == character_id]
        return results[-limit:]

    def count(self, character_id: str = "aevum") -> int:
        """Total number of audit records stored."""
        return sum(1 for r in self._records if r.character_id == character_id)


# ---------------------------------------------------------------------------
# Adaptive Belief Revision Engine (Pure Evaluation: Zero Canonical Mutations)
# ---------------------------------------------------------------------------

class AdaptiveBeliefRevisionEngine:
    """Pure evaluation engine governing belief revision decisions.

    Constitutional Discipline:
    - Lock 11 (Candidate != Evidence): Rejects any revision attempt sourced from
      a CANDIDATE_HYPOTHESIS.
    - Lock 8 (Canonical Fact Protection): CANONICAL facts cannot be demoted or deleted.
    - Zero mutation authority: Evaluates proposals; does NOT write to database or call set_fact().
    """

    def evaluate_revision(
        self,
        candidate: CandidateHypothesis,
        evidence: IncomingEvidenceItem,
        core: Optional[CharacterCore] = None,
        cycle_id: str = "cycle-rev",
    ) -> BeliefRevisionProposal:
        """Evaluate how incoming evidence affects an existing candidate belief."""
        # 1. Lock 11: Candidate != Evidence Gate
        if evidence.source_type == EvidenceSourceType.CANDIDATE_HYPOTHESIS:
            return BeliefRevisionProposal(
                is_valid_revision=False,
                revision_kind=BeliefRevisionKind.CONTRADICTION,
                rejection_reason="LOCK_11_CANDIDATE_NOT_EVIDENCE: CandidateHypothesis cannot serve as evidence.",
            )

        # 2. Lock 8: Canonical Fact Demotion Protection
        if core:
            fact = core.get_fact(candidate.slot_name)
            if fact and fact.status == FactStatus.CANONICAL:
                if fact.value == candidate.proposed_value and evidence.asserted_value != candidate.proposed_value:
                    # An existing CANONICAL fact cannot be demoted by standard construction revision
                    return BeliefRevisionProposal(
                        is_valid_revision=False,
                        revision_kind=BeliefRevisionKind.CONTRADICTION,
                        rejection_reason=(
                            "LOCK_8_CANONICAL_DEMOTION_BLOCKED: Canonical facts cannot be demoted "
                            "by autonomous belief revision. Requires full reconciliation pipeline."
                        ),
                    )

        # Slot matching check
        if candidate.slot_name != evidence.slot_name:
            return BeliefRevisionProposal(
                is_valid_revision=False,
                revision_kind=BeliefRevisionKind.CONTRADICTION,
                rejection_reason=f"Slot mismatch: candidate '{candidate.slot_name}' vs evidence '{evidence.slot_name}'",
            )

        # Normalization for string comparisons
        cand_val_str = str(candidate.proposed_value).strip().lower()
        ev_val_str = str(evidence.asserted_value).strip().lower()

        revision_id = f"rev_{uuid.uuid4().hex[:8]}"

        # 3. Decision Tree: Revision Kind Classification

        # A. Exact Match -> CONFIRMATION
        if cand_val_str == ev_val_str:
            record = BeliefRevisionRecord(
                revision_id=revision_id,
                character_id=candidate.entity_id,
                slot_name=candidate.slot_name,
                revision_kind=BeliefRevisionKind.CONFIRMATION,
                prior_value=candidate.proposed_value,
                revised_value=candidate.proposed_value,
                prior_candidate_id=candidate.candidate_id,
                trigger_cycle_id=cycle_id,
                rationale=f"Evidence '{evidence.evidence_id}' corroborated existing belief.",
            )
            return BeliefRevisionProposal(
                is_valid_revision=True,
                revision_kind=BeliefRevisionKind.CONFIRMATION,
                record=record,
                target_lifecycle_state=CandidateLifecycleState.ACTIVE,
            )

        # B. Partial Match -> PARTIAL_CONFIRMATION
        if cand_val_str in ev_val_str or ev_val_str in cand_val_str:
            record = BeliefRevisionRecord(
                revision_id=revision_id,
                character_id=candidate.entity_id,
                slot_name=candidate.slot_name,
                revision_kind=BeliefRevisionKind.PARTIAL_CONFIRMATION,
                prior_value=candidate.proposed_value,
                revised_value=evidence.asserted_value,
                prior_candidate_id=candidate.candidate_id,
                trigger_cycle_id=cycle_id,
                rationale=f"Evidence partially aligns with belief '{cand_val_str}'.",
            )
            return BeliefRevisionProposal(
                is_valid_revision=True,
                revision_kind=BeliefRevisionKind.PARTIAL_CONFIRMATION,
                record=record,
                target_lifecycle_state=CandidateLifecycleState.ACTIVE,
            )

        # C. Contradiction with Definitive Replacement -> SUPERSESSION (Lock 4)
        if evidence.is_definitive_replacement:
            record = BeliefRevisionRecord(
                revision_id=revision_id,
                character_id=candidate.entity_id,
                slot_name=candidate.slot_name,
                revision_kind=BeliefRevisionKind.SUPERSESSION,
                prior_value=candidate.proposed_value,
                revised_value=evidence.asserted_value,
                prior_candidate_id=candidate.candidate_id,
                trigger_cycle_id=cycle_id,
                rationale=(
                    f"Definitive evidence from '{evidence.source_type.value}' "
                    f"superseded prior value '{candidate.proposed_value}' with '{evidence.asserted_value}'."
                ),
            )
            return BeliefRevisionProposal(
                is_valid_revision=True,
                revision_kind=BeliefRevisionKind.SUPERSESSION,
                record=record,
                target_lifecycle_state=CandidateLifecycleState.SUPERSEDED,
            )

        # D. Contradiction without Replacement -> CONTRADICTION
        record = BeliefRevisionRecord(
            revision_id=revision_id,
            character_id=candidate.entity_id,
            slot_name=candidate.slot_name,
            revision_kind=BeliefRevisionKind.CONTRADICTION,
            prior_value=candidate.proposed_value,
            revised_value=None,
            prior_candidate_id=candidate.candidate_id,
            trigger_cycle_id=cycle_id,
            rationale=f"Evidence contradicted belief '{cand_val_str}' without a definitive replacement.",
        )
        return BeliefRevisionProposal(
            is_valid_revision=True,
            revision_kind=BeliefRevisionKind.CONTRADICTION,
            record=record,
            target_lifecycle_state=CandidateLifecycleState.REJECTED,
        )


# ---------------------------------------------------------------------------
# Belief Reconciliation Service (Atomic Execution of Approved Revisions)
# ---------------------------------------------------------------------------

class BeliefReconciliationService:
    """Orchestrates atomic application of approved belief revision proposals.

    Responsibilities:
    1. Records the BeliefRevisionRecord into the append-only repository (Lock 4).
    2. Updates the candidate's lifecycle state via CandidateRepository:
       - For SUPERSESSION: transitions prior candidate to SUPERSEDED (preserved, never deleted).
       - For CONTRADICTION: transitions prior candidate to REJECTED.
       - For CONFIRMATION: preserves prior candidate as ACTIVE.
    3. Canonical Boundary:
       Never calls set_fact() or mints tokens. Canonical reconciliation requires
       explicit delegation to BiographyPromotionService or RealityRepairService.
    """

    def __init__(
        self,
        revision_repo: Optional[BeliefRevisionRepository] = None,
        candidate_repo: Optional[CandidateRepository] = None,
    ) -> None:
        self.revision_repo = revision_repo or BeliefRevisionRepository()
        self.candidate_repo = candidate_repo

    async def apply_revision(
        self,
        candidate: CandidateHypothesis,
        proposal: BeliefRevisionProposal,
    ) -> Optional[BeliefRevisionRecord]:
        """Atomically persist revision record and transition candidate state."""
        if not proposal.is_valid_revision or proposal.record is None:
            logger.warning(
                "Refusing to apply invalid belief revision for candidate '%s': %s",
                candidate.candidate_id, proposal.rejection_reason,
            )
            return None

        # 1. Append-only persistence into audit trail (Lock 4, D4)
        self.revision_repo.append(proposal.record)

        # 2. Update Candidate Lifecycle State in repository if available
        if self.candidate_repo is not None and proposal.target_lifecycle_state is not None:
            await self.candidate_repo.update_lifecycle_state(
                candidate_id=candidate.candidate_id,
                new_state=proposal.target_lifecycle_state,
            )

        return proposal.record
