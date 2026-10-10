"""Phase 19.4 — Epistemic Transformation & Epistemic Ladder Gatekeeper Contracts.

Defines the contracts and gatekeeper rules governing how closed prospective threads
safely transition into experiential records (Phase 16) without prematurely promoting
actions to experiences, or experiences to preferences.

Constitutional Locks:
- Closure ≠ Learning: A thread closing merely settles a future uncertainty;
  it never automatically creates knowledge or preferences.
- Thread Closure ≠ Thread Success: ClosureReason expresses real-world outcome
  type (REALIZED, ABANDONED, OBSOLETED), never goal success/failure scoring.
- The Epistemic Ladder Invariant:
    Intention ≠ Action ≠ Experience ≠ Preference
    - Without Experience, NO Preference.
    - Single Experience cannot form a sustained Preference.
    - Negative outcomes are first-class experiences.
    - Non-action closures never manufacture fake action/experience records.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class EpistemicStage(str, Enum):
    """Discrete stages in the epistemic transformation ladder.
    
    Levels must be traversed sequentially; no stage skipping is permitted.
    """
    PROSPECTIVE_INTENTION = "PROSPECTIVE_INTENTION"  # Open thread, unresolved possibility
    ACTION_RECORDED = "ACTION_RECORDED"              # Concrete action occurred in reality (0 experience)
    EXPERIENCE_ENCOUNTERED = "EXPERIENCE_ENCOUNTERED"  # Direct lived experience occurred
    SUSTAINED_EVIDENCE = "SUSTAINED_EVIDENCE"        # Repeated experiences over calendar time
    PREFERENCE_ELIGIBLE = "PREFERENCE_ELIGIBLE"      # Eligible for Phase 16 facet appraisal & preference formation


class TransformationEvidenceKind(str, Enum):
    """Categorical classification of the reality evidence accompanying a thread transition."""
    NON_ACTION_CLOSURE = "NON_ACTION_CLOSURE"      # Closed via abandonment/obsoletion (0 action, 0 experience)
    ACTION_ONLY = "ACTION_ONLY"                    # Concrete action occurred without lived experience (e.g. bought gear)
    EXPERIENCE_NEUTRAL = "EXPERIENCE_NEUTRAL"      # Lived experience with neutral/unclear appraisal
    EXPERIENCE_POSITIVE = "EXPERIENCE_POSITIVE"    # Lived experience with positive appraisal
    EXPERIENCE_NEGATIVE = "EXPERIENCE_NEGATIVE"    # Lived experience with negative appraisal (disliked)
    SUSTAINED_POSITIVE = "SUSTAINED_POSITIVE"      # Repeated longitudinal positive experiences


class TransformationAuditRecord(BaseModel):
    """Immutable audit record logging an epistemic ladder transformation."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    audit_id: str = Field(..., min_length=1, description="Unique audit identifier.")
    thread_id: str = Field(..., min_length=1, description="Associated prospective thread ID.")
    from_stage: EpistemicStage = Field(..., description="Previous epistemic stage.")
    to_stage: EpistemicStage = Field(..., description="Target epistemic stage.")
    evidence_kind: TransformationEvidenceKind = Field(..., description="Evidence category provided.")
    rationale: str = Field(..., min_length=1, max_length=500, description="Explainable transition rationale.")
    timestamp: datetime = Field(..., description="Authoritative timestamp when transformation settled.")


class IllegalEpistemicSkipError(ValueError):
    """Raised when an illegal skip across epistemic stages is attempted."""

    def __init__(self, from_stage: EpistemicStage, to_stage: EpistemicStage, reason: str):
        self.from_stage = from_stage
        self.to_stage = to_stage
        self.reason = reason
        super().__init__(
            f"Illegal Epistemic Ladder Skip: Cannot jump from {from_stage.value} "
            f"to {to_stage.value}. Reason: {reason}"
        )
