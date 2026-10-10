"""Phase 19.4 — Epistemic Transformation Engine & Epistemic Ladder Gatekeeper.

Deterministic gatekeeper engine enforcing the epistemic ladder:
    Intention -> Action -> Experience -> Sustained Evidence -> Preference.

Constitutional Locks:
- Closure ≠ Learning: A thread closing merely settles a future uncertainty;
  it never automatically creates knowledge or preferences.
- Thread Closure ≠ Thread Success: ClosureReason expresses real-world outcome
  type (REALIZED, ABANDONED, OBSOLETED), never goal success/failure scoring.
- The Epistemic Ladder Invariant:
    Intention ≠ Action ≠ Experience ≠ Preference
    - Without Experience, NO Preference.
    - Single Experience cannot form a sustained Preference.
    - Negative outcomes are first-class experiences (never promote preference).
    - Non-action closures never manufacture fake action/experience records.
"""

from datetime import datetime, timezone
from typing import Optional, Set, Tuple
import uuid

from app.prospective.transformation_models import (
    EpistemicStage,
    IllegalEpistemicSkipError,
    TransformationAuditRecord,
    TransformationEvidenceKind,
)


# Canonical adjacent legal forward steps on the epistemic ladder
LEGAL_LADDER_STEPS: Set[Tuple[EpistemicStage, EpistemicStage]] = {
    # Step 1: Intention to Action
    (EpistemicStage.PROSPECTIVE_INTENTION, EpistemicStage.ACTION_RECORDED),
    # Non-action settlement at Intention stage
    (EpistemicStage.PROSPECTIVE_INTENTION, EpistemicStage.PROSPECTIVE_INTENTION),
    # Step 2: Action to Experience
    (EpistemicStage.ACTION_RECORDED, EpistemicStage.EXPERIENCE_ENCOUNTERED),
    # Negative experience settling at Experience stage without promotion
    (EpistemicStage.EXPERIENCE_ENCOUNTERED, EpistemicStage.EXPERIENCE_ENCOUNTERED),
    # Step 3: Experience to Sustained Evidence
    (EpistemicStage.EXPERIENCE_ENCOUNTERED, EpistemicStage.SUSTAINED_EVIDENCE),
    # Step 4: Sustained Evidence to Preference Eligible
    (EpistemicStage.SUSTAINED_EVIDENCE, EpistemicStage.PREFERENCE_ELIGIBLE),
}


class EpistemicTransformationEngine:
    """Pure deterministic gatekeeper enforcing the epistemic ladder."""

    @classmethod
    def is_preference_eligible(cls, stage: EpistemicStage) -> bool:
        """Checks if the given epistemic stage has reached preference eligibility."""
        return stage == EpistemicStage.PREFERENCE_ELIGIBLE

    @classmethod
    def has_lived_experience(cls, stage: EpistemicStage) -> bool:
        """Checks if direct lived experience has been encountered."""
        return stage in {
            EpistemicStage.EXPERIENCE_ENCOUNTERED,
            EpistemicStage.SUSTAINED_EVIDENCE,
            EpistemicStage.PREFERENCE_ELIGIBLE,
        }

    @classmethod
    def has_action_occurred(cls, stage: EpistemicStage) -> bool:
        """Checks if a concrete real-world action has occurred."""
        return stage in {
            EpistemicStage.ACTION_RECORDED,
            EpistemicStage.EXPERIENCE_ENCOUNTERED,
            EpistemicStage.SUSTAINED_EVIDENCE,
            EpistemicStage.PREFERENCE_ELIGIBLE,
        }

    @classmethod
    def validate_transformation(
        cls,
        from_stage: EpistemicStage,
        to_stage: EpistemicStage,
        evidence_kind: TransformationEvidenceKind,
    ) -> None:
        """Validates that a stage transition strictly adheres to the epistemic ladder.

        Raises:
            IllegalEpistemicSkipError: If attempting to skip required ladder stages.
            ValueError: If evidence_kind does not substantiate the requested transition.
        """
        # 1. Anti-Skipping: Intention cannot jump directly to Experience or Preference
        if from_stage == EpistemicStage.PROSPECTIVE_INTENTION:
            if to_stage in {
                EpistemicStage.EXPERIENCE_ENCOUNTERED,
                EpistemicStage.SUSTAINED_EVIDENCE,
                EpistemicStage.PREFERENCE_ELIGIBLE,
            }:
                raise IllegalEpistemicSkipError(
                    from_stage=from_stage,
                    to_stage=to_stage,
                    reason=(
                        "Intention cannot skip directly to Experience or Preference. "
                        "A concrete real-world action must be recorded first."
                    ),
                )
            if to_stage == EpistemicStage.ACTION_RECORDED:
                if evidence_kind != TransformationEvidenceKind.ACTION_ONLY:
                    raise IllegalEpistemicSkipError(
                        from_stage=from_stage,
                        to_stage=to_stage,
                        reason=(
                            f"Transition to ACTION_RECORDED requires ACTION_ONLY evidence, "
                            f"got '{evidence_kind.value}'."
                        ),
                    )
            elif to_stage == EpistemicStage.PROSPECTIVE_INTENTION:
                if evidence_kind != TransformationEvidenceKind.NON_ACTION_CLOSURE:
                    raise ValueError(
                        f"Non-advancing transition at PROSPECTIVE_INTENTION requires "
                        f"NON_ACTION_CLOSURE, got '{evidence_kind.value}'."
                    )

        # 2. Anti-Skipping: Action cannot jump directly to Sustained Evidence or Preference
        elif from_stage == EpistemicStage.ACTION_RECORDED:
            if to_stage in {
                EpistemicStage.SUSTAINED_EVIDENCE,
                EpistemicStage.PREFERENCE_ELIGIBLE,
            }:
                raise IllegalEpistemicSkipError(
                    from_stage=from_stage,
                    to_stage=to_stage,
                    reason=(
                        "Action cannot skip directly to Sustained Evidence or Preference. "
                        "Action is NOT experience; lived experience must be encountered first."
                    ),
                )
            if to_stage == EpistemicStage.EXPERIENCE_ENCOUNTERED:
                if evidence_kind not in {
                    TransformationEvidenceKind.EXPERIENCE_POSITIVE,
                    TransformationEvidenceKind.EXPERIENCE_NEUTRAL,
                    TransformationEvidenceKind.EXPERIENCE_NEGATIVE,
                }:
                    raise IllegalEpistemicSkipError(
                        from_stage=from_stage,
                        to_stage=to_stage,
                        reason=(
                            f"Transition to EXPERIENCE_ENCOUNTERED requires lived experience evidence, "
                            f"got '{evidence_kind.value}'."
                        ),
                    )

        # 3. Anti-Skipping: Single Experience cannot jump directly to Preference
        elif from_stage == EpistemicStage.EXPERIENCE_ENCOUNTERED:
            if to_stage == EpistemicStage.PREFERENCE_ELIGIBLE:
                raise IllegalEpistemicSkipError(
                    from_stage=from_stage,
                    to_stage=to_stage,
                    reason=(
                        "Single lived experience cannot skip directly to Preference. "
                        "Requires longitudinal Sustained Evidence first."
                    ),
                )
            if to_stage == EpistemicStage.SUSTAINED_EVIDENCE:
                if evidence_kind == TransformationEvidenceKind.EXPERIENCE_NEGATIVE:
                    raise IllegalEpistemicSkipError(
                        from_stage=from_stage,
                        to_stage=to_stage,
                        reason="Negative lived experience cannot advance the preference ladder.",
                    )
                if evidence_kind != TransformationEvidenceKind.SUSTAINED_POSITIVE:
                    raise IllegalEpistemicSkipError(
                        from_stage=from_stage,
                        to_stage=to_stage,
                        reason=(
                            f"Transition to SUSTAINED_EVIDENCE requires SUSTAINED_POSITIVE evidence, "
                            f"got '{evidence_kind.value}'."
                        ),
                    )
            elif to_stage == EpistemicStage.EXPERIENCE_ENCOUNTERED:
                # Retaining stage e.g. recording negative outcome or neutral settlement
                pass

        # 4. Sustained Evidence to Preference
        elif from_stage == EpistemicStage.SUSTAINED_EVIDENCE:
            if to_stage == EpistemicStage.PREFERENCE_ELIGIBLE:
                if evidence_kind != TransformationEvidenceKind.SUSTAINED_POSITIVE:
                    raise IllegalEpistemicSkipError(
                        from_stage=from_stage,
                        to_stage=to_stage,
                        reason=(
                            f"Transition to PREFERENCE_ELIGIBLE requires SUSTAINED_POSITIVE evidence, "
                            f"got '{evidence_kind.value}'."
                        ),
                    )

        # 5. Check if step is in canonical ladder steps
        if (from_stage, to_stage) not in LEGAL_LADDER_STEPS:
            raise IllegalEpistemicSkipError(
                from_stage=from_stage,
                to_stage=to_stage,
                reason=f"Transition from {from_stage.value} to {to_stage.value} is not a valid ladder progression.",
            )

    @classmethod
    def advance_stage(
        cls,
        thread_id: str,
        from_stage: EpistemicStage,
        to_stage: EpistemicStage,
        evidence_kind: TransformationEvidenceKind,
        rationale: str,
        timestamp: Optional[datetime] = None,
        audit_id: Optional[str] = None,
    ) -> TransformationAuditRecord:
        """Explicitly advances from one stage to another, validating legality.

        Raises:
            IllegalEpistemicSkipError: If transition is illegal.
        """
        cls.validate_transformation(from_stage, to_stage, evidence_kind)
        ts = timestamp or datetime.now(timezone.utc)
        aid = audit_id or f"audit_{uuid.uuid4().hex[:12]}"

        return TransformationAuditRecord(
            audit_id=aid,
            thread_id=thread_id,
            from_stage=from_stage,
            to_stage=to_stage,
            evidence_kind=evidence_kind,
            rationale=rationale,
            timestamp=ts,
        )

    @classmethod
    def evaluate_transition(
        cls,
        thread_id: str,
        current_stage: EpistemicStage,
        evidence_kind: TransformationEvidenceKind,
        rationale: str,
        timestamp: Optional[datetime] = None,
        audit_id: Optional[str] = None,
    ) -> Tuple[EpistemicStage, TransformationAuditRecord]:
        """Deterministically evaluates the next epistemic stage given current stage and evidence.

        Returns:
            Tuple of (next_stage, audit_record).

        Raises:
            IllegalEpistemicSkipError: If evidence attempts an illegal skip.
            ValueError: If evidence cannot be evaluated for the current stage.
        """
        ts = timestamp or datetime.now(timezone.utc)
        aid = audit_id or f"audit_{uuid.uuid4().hex[:12]}"

        # Scenario A: Non-action closure at Intention stage
        if (
            current_stage == EpistemicStage.PROSPECTIVE_INTENTION
            and evidence_kind == TransformationEvidenceKind.NON_ACTION_CLOSURE
        ):
            record = TransformationAuditRecord(
                audit_id=aid,
                thread_id=thread_id,
                from_stage=EpistemicStage.PROSPECTIVE_INTENTION,
                to_stage=EpistemicStage.PROSPECTIVE_INTENTION,
                evidence_kind=evidence_kind,
                rationale=rationale,
                timestamp=ts,
            )
            return EpistemicStage.PROSPECTIVE_INTENTION, record

        # Scenario B: Action evidence for Intention
        if (
            current_stage == EpistemicStage.PROSPECTIVE_INTENTION
            and evidence_kind == TransformationEvidenceKind.ACTION_ONLY
        ):
            record = TransformationAuditRecord(
                audit_id=aid,
                thread_id=thread_id,
                from_stage=EpistemicStage.PROSPECTIVE_INTENTION,
                to_stage=EpistemicStage.ACTION_RECORDED,
                evidence_kind=evidence_kind,
                rationale=rationale,
                timestamp=ts,
            )
            return EpistemicStage.ACTION_RECORDED, record

        # Scenario C: Lived Experience for Action
        if current_stage == EpistemicStage.ACTION_RECORDED and evidence_kind in {
            TransformationEvidenceKind.EXPERIENCE_POSITIVE,
            TransformationEvidenceKind.EXPERIENCE_NEUTRAL,
            TransformationEvidenceKind.EXPERIENCE_NEGATIVE,
        }:
            record = TransformationAuditRecord(
                audit_id=aid,
                thread_id=thread_id,
                from_stage=EpistemicStage.ACTION_RECORDED,
                to_stage=EpistemicStage.EXPERIENCE_ENCOUNTERED,
                evidence_kind=evidence_kind,
                rationale=rationale,
                timestamp=ts,
            )
            return EpistemicStage.EXPERIENCE_ENCOUNTERED, record

        # Scenario D: Negative outcome settles at Experience level without preference promotion
        if (
            current_stage == EpistemicStage.EXPERIENCE_ENCOUNTERED
            and evidence_kind == TransformationEvidenceKind.EXPERIENCE_NEGATIVE
        ):
            record = TransformationAuditRecord(
                audit_id=aid,
                thread_id=thread_id,
                from_stage=EpistemicStage.EXPERIENCE_ENCOUNTERED,
                to_stage=EpistemicStage.EXPERIENCE_ENCOUNTERED,
                evidence_kind=evidence_kind,
                rationale=rationale,
                timestamp=ts,
            )
            return EpistemicStage.EXPERIENCE_ENCOUNTERED, record

        # Scenario E: Sustained positive evidence for Experience
        if (
            current_stage == EpistemicStage.EXPERIENCE_ENCOUNTERED
            and evidence_kind == TransformationEvidenceKind.SUSTAINED_POSITIVE
        ):
            record = TransformationAuditRecord(
                audit_id=aid,
                thread_id=thread_id,
                from_stage=EpistemicStage.EXPERIENCE_ENCOUNTERED,
                to_stage=EpistemicStage.SUSTAINED_EVIDENCE,
                evidence_kind=evidence_kind,
                rationale=rationale,
                timestamp=ts,
            )
            return EpistemicStage.SUSTAINED_EVIDENCE, record

        # Scenario F: Sustained positive evidence reaching Preference Eligibility
        if (
            current_stage == EpistemicStage.SUSTAINED_EVIDENCE
            and evidence_kind == TransformationEvidenceKind.SUSTAINED_POSITIVE
        ):
            record = TransformationAuditRecord(
                audit_id=aid,
                thread_id=thread_id,
                from_stage=EpistemicStage.SUSTAINED_EVIDENCE,
                to_stage=EpistemicStage.PREFERENCE_ELIGIBLE,
                evidence_kind=evidence_kind,
                rationale=rationale,
                timestamp=ts,
            )
            return EpistemicStage.PREFERENCE_ELIGIBLE, record

        # Detect illegal skip attempts:
        if current_stage == EpistemicStage.PROSPECTIVE_INTENTION:
            if evidence_kind in {
                TransformationEvidenceKind.EXPERIENCE_POSITIVE,
                TransformationEvidenceKind.EXPERIENCE_NEUTRAL,
                TransformationEvidenceKind.EXPERIENCE_NEGATIVE,
            }:
                raise IllegalEpistemicSkipError(
                    from_stage=current_stage,
                    to_stage=EpistemicStage.EXPERIENCE_ENCOUNTERED,
                    reason="Intention cannot skip directly to Experience without concrete Action.",
                )
            if evidence_kind == TransformationEvidenceKind.SUSTAINED_POSITIVE:
                raise IllegalEpistemicSkipError(
                    from_stage=current_stage,
                    to_stage=EpistemicStage.PREFERENCE_ELIGIBLE,
                    reason="Intention cannot skip directly to Preference without Action and Experience.",
                )

        if current_stage == EpistemicStage.ACTION_RECORDED:
            if evidence_kind == TransformationEvidenceKind.SUSTAINED_POSITIVE:
                raise IllegalEpistemicSkipError(
                    from_stage=current_stage,
                    to_stage=EpistemicStage.SUSTAINED_EVIDENCE,
                    reason="Action cannot skip directly to Sustained Evidence without lived Experience.",
                )

        raise ValueError(
            f"Cannot evaluate transition from stage '{current_stage.value}' "
            f"with evidence kind '{evidence_kind.value}'."
        )
