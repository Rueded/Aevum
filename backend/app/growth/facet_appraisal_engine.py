"""Phase 16.3 FacetAppraisalEngine.

Deterministic, guard-chained appraisal production engine.
Pure synchronous logic. No database access. No async. No LLM calls.
Receives all necessary data as arguments from the caller.

7-Layer Guard Chain (execution order fixed; fail-closed — any violation raises immediately):
  Guard 1: Tier-3 evidence rejection (USER_RECOMMENDATION_REJECTED, USER_PREFERENCE_REJECTED)
  Guard 2: Evidence status must be GROUNDED (not PROPOSED or REJECTED)
  Guard 3: Personal-experience eligibility (Lock 1, Lock 9)
  Guard 4: Facet registration validation (Req 10)
  Guard 5: Identity anchoring (character_id / domain_key / facet_key / experience_id)
  Guard 6: Timeline tick anchoring — evidence.timeline_tick == record.timeline_tick (Blocker 5)
  Guard 7: Idempotency — no existing appraisal for (experience_id, facet_key) (Req 8)

Evaluation Priority Chain (Blocker 2 — executed after all guards pass):
  Priority 1: grounded_signal in UNAMBIGUOUS_SIGNAL_MAP → temperament bypassed entirely (G42)
  Priority 2: grounded_signal in AMBIGUOUS_SIGNAL_TEMPERAMENT_MAP → temperament as tie-break
  Priority 3: unknown signal → UnknownGroundedSignalError (fail-closed; no temperament fallback)

Constitutional Invariants:
  - FacetAppraisalKind imported from Phase 16.1 experiential_models; never redefined here.
  - appraisal.timeline_tick = record.timeline_tick (engine-set; caller cannot configure).
  - Guard failures are always fail-closed: no fallback appraisal, no silent degradation.
  - qualia_summary is never read by this engine (display/audit field only).
"""

from __future__ import annotations

import uuid

from app.growth.appraisal_models import (
    BLOCKED_EVIDENCE_KINDS,
    AppraisalEvidenceStatus,
    AppraisalIdentityMismatchError,
    CharacterTemperamentProfile,
    DuplicateAppraisalError,
    FacetAppraisalRecord,
    TemperamentCompatibility,
    TemporalAnchorMismatchError,
    UngroundedAppraisalEvidenceError,
    UnknownGroundedSignalError,
    UnregisteredFacetError,
    AppraisalEvidence,
    utc_now,
)
from app.growth.experiential_models import ExperientialRecord, FacetAppraisalKind
from app.growth.state_machine import is_eligible_personal_experience


class FacetAppraisalEngine:
    """Deterministic facet appraisal production engine.

    Constitutional Invariants:
    - FacetAppraisalKind is imported from Phase 16.1 experiential_models.py; NOT redefined here.
    - appraisal.timeline_tick is ALWAYS set to record.timeline_tick by this engine.
      Callers cannot provide or override the timeline_tick of the resulting FacetAppraisalRecord.
    - Guard chain is fail-closed: any guard failure raises immediately; NO fallback appraisal.
    - Priority 1 (unambiguous signals): temperament is NOT consulted (G42 verifies this).
    - Priority 2 (ambiguous signals): temperament acts as a deterministic tie-break only.
    - Priority 3 (unknown signal): raises UnknownGroundedSignalError; temperament cannot rescue it.
    - qualia_summary from evidence is NEVER read by this engine.
    """

    # Priority 1 — Unambiguous signals: direct appraisal derivation; temperament bypassed (G42)
    UNAMBIGUOUS_SIGNAL_MAP: dict[str, FacetAppraisalKind] = {
        "lyrical_resonance":          FacetAppraisalKind.STRONGLY_ATTRACTED,
        "flow_state_achieved":        FacetAppraisalKind.STRONGLY_ATTRACTED,
        "deep_immersion":             FacetAppraisalKind.STRONGLY_ATTRACTED,
        "emotional_resonance":        FacetAppraisalKind.STRONGLY_ATTRACTED,
        "aesthetic_delight":          FacetAppraisalKind.STRONGLY_ATTRACTED,
        "engaged_completion":         FacetAppraisalKind.ENJOYABLE,
        "willing_return":             FacetAppraisalKind.ENJOYABLE,
        "explicit_positive_reaction": FacetAppraisalKind.ENJOYABLE,
        "indifferent_completion":     FacetAppraisalKind.NEUTRAL_INDIFFERENT,
        "no_notable_reaction":        FacetAppraisalKind.NEUTRAL_INDIFFERENT,
        "exhausting_loop":            FacetAppraisalKind.TEDIOUS_EXHAUSTING,
        "mechanical_fatigue":         FacetAppraisalKind.TEDIOUS_EXHAUSTING,
        "early_abandonment":          FacetAppraisalKind.TEDIOUS_EXHAUSTING,
        "acute_aversion":             FacetAppraisalKind.AVERSIVE_DISLIKED,
        "explicit_discomfort":        FacetAppraisalKind.AVERSIVE_DISLIKED,
        "values_dissonance":          FacetAppraisalKind.AVERSIVE_DISLIKED,
        "active_rejection":           FacetAppraisalKind.AVERSIVE_DISLIKED,
    }

    # Priority 2 — Ambiguous signals: temperament acts as deterministic tie-break
    AMBIGUOUS_SIGNAL_TEMPERAMENT_MAP: dict[str, dict[TemperamentCompatibility, FacetAppraisalKind]] = {
        "routine_interaction": {
            TemperamentCompatibility.STRONGLY_RESONANT: FacetAppraisalKind.ENJOYABLE,
            TemperamentCompatibility.RESONANT:          FacetAppraisalKind.ENJOYABLE,
            TemperamentCompatibility.NEUTRAL:           FacetAppraisalKind.NEUTRAL_INDIFFERENT,
            TemperamentCompatibility.FRICTION:          FacetAppraisalKind.NEUTRAL_INDIFFERENT,
            TemperamentCompatibility.STRONG_FRICTION:   FacetAppraisalKind.NEUTRAL_INDIFFERENT,
        },
        "moderate_engagement": {
            TemperamentCompatibility.STRONGLY_RESONANT: FacetAppraisalKind.ENJOYABLE,
            TemperamentCompatibility.RESONANT:          FacetAppraisalKind.ENJOYABLE,
            TemperamentCompatibility.NEUTRAL:           FacetAppraisalKind.NEUTRAL_INDIFFERENT,
            TemperamentCompatibility.FRICTION:          FacetAppraisalKind.NEUTRAL_INDIFFERENT,
            TemperamentCompatibility.STRONG_FRICTION:   FacetAppraisalKind.TEDIOUS_EXHAUSTING,
        },
        "neutral_completion": {
            TemperamentCompatibility.STRONGLY_RESONANT: FacetAppraisalKind.ENJOYABLE,
            TemperamentCompatibility.RESONANT:          FacetAppraisalKind.NEUTRAL_INDIFFERENT,
            TemperamentCompatibility.NEUTRAL:           FacetAppraisalKind.NEUTRAL_INDIFFERENT,
            TemperamentCompatibility.FRICTION:          FacetAppraisalKind.NEUTRAL_INDIFFERENT,
            TemperamentCompatibility.STRONG_FRICTION:   FacetAppraisalKind.TEDIOUS_EXHAUSTING,
        },
    }

    def evaluate_appraisal(
        self,
        record: ExperientialRecord,
        evidence: AppraisalEvidence,
        temperament: CharacterTemperamentProfile,
        existing_appraisal_pairs: frozenset[tuple[str, str]],
        registered_facet_keys: frozenset[str],
        registered_domain_keys: frozenset[str] = frozenset(),
    ) -> FacetAppraisalRecord:
        """Evaluate and produce an authoritative FacetAppraisalRecord.

        All 7 guards run in fixed order before evaluation. Any guard failure raises
        immediately; execution does not continue (fail-closed principle).

        Args:
            record: Verified ExperientialRecord from Phase 16.1.
            evidence: AppraisalEvidence DTO (must carry evidence_status=GROUNDED).
            temperament: Deterministic temperament profile for (domain, facet).
            existing_appraisal_pairs: Frozenset of (experience_id, facet_key) already persisted.
            registered_facet_keys: Valid facet_keys for the domain (from character_interest_facets).
            registered_domain_keys: Valid domain_keys (from character_interest_domains; optional).

        Returns:
            FacetAppraisalRecord with timeline_tick = record.timeline_tick (engine-set).

        Raises:
            UngroundedAppraisalEvidenceError: Guard 1 (Tier-3), Guard 2 (not GROUNDED),
                Guard 3 (ineligible experience).
            UnregisteredFacetError: Guard 4 (unregistered domain or facet).
            AppraisalIdentityMismatchError: Guard 5 (identity anchor failure).
            TemporalAnchorMismatchError: Guard 6 (timeline tick mismatch).
            DuplicateAppraisalError: Guard 7 (idempotency violation).
            UnknownGroundedSignalError: Unknown grounded_signal (fail-closed; no fallback).
        """
        # ─── Guard 1: Tier-3 blocked evidence kinds ───────────────────────────
        # User recommendations and user preference declarations are permanently
        # blocked from creating Aevum's appraisals (Anti-Sycophancy Lock).
        if evidence.evidence_kind in BLOCKED_EVIDENCE_KINDS:
            raise UngroundedAppraisalEvidenceError(
                f"Evidence kind '{evidence.evidence_kind.value}' is Tier-3 non-authority and is "
                f"always rejected. User preferences and recommendations cannot create Aevum's "
                f"appraisals (User Preference Non-Authority Lock)."
            )

        # ─── Guard 2: Evidence status must be GROUNDED ────────────────────────
        # PROPOSED evidence (LLM-contributed) requires anchor validation before
        # it may enter this engine. REJECTED evidence is permanently excluded.
        if evidence.evidence_status != AppraisalEvidenceStatus.GROUNDED:
            raise UngroundedAppraisalEvidenceError(
                f"Evidence '{evidence.evidence_id}' has status '{evidence.evidence_status.value}'. "
                f"Only GROUNDED evidence is eligible for appraisal production. "
                f"PROPOSED evidence must pass anchor validation first."
            )

        # ─── Guard 3: Personal-experience eligibility (Lock 1, Lock 9) ────────
        if not is_eligible_personal_experience(record):
            raise UngroundedAppraisalEvidenceError(
                f"Experience '{record.experience_id}' "
                f"(provenance={record.provenance_kind.value}, "
                f"fictional_frame={record.is_fictional_frame}) is not an eligible personal "
                f"experience. Only DIRECT_INTERACTION and non-fictional SHARED_INTERACTION "
                f"qualify (Knowledge != Experience)."
            )

        # ─── Guard 4: Facet & domain registration (Req 10) ───────────────────
        if registered_domain_keys and evidence.domain_key not in registered_domain_keys:
            raise UnregisteredFacetError(
                f"Domain '{evidence.domain_key}' is not registered in character_interest_domains."
            )
        if evidence.facet_key not in registered_facet_keys:
            raise UnregisteredFacetError(
                f"Facet '{evidence.facet_key}' is not a registered sub-facet of domain "
                f"'{evidence.domain_key}' in character_interest_facets."
            )

        # ─── Guard 5: Identity anchoring ──────────────────────────────────────
        if (
            evidence.character_id != record.character_id
            or evidence.domain_key != record.domain_key
            or evidence.facet_key != record.facet_key
            or evidence.experience_id != record.experience_id
        ):
            raise AppraisalIdentityMismatchError(
                f"Identity mismatch between evidence and experience record. "
                f"Evidence: (char={evidence.character_id!r}, domain={evidence.domain_key!r}, "
                f"facet={evidence.facet_key!r}, exp={evidence.experience_id!r}). "
                f"Record: (char={record.character_id!r}, domain={record.domain_key!r}, "
                f"facet={record.facet_key!r}, exp={record.experience_id!r})."
            )

        # ─── Guard 6: Timeline tick anchoring (Blocker 5) ─────────────────────
        # Appraisals must be anchored to the moment of experience, not the
        # moment of post-interaction analysis. Prevents temporal drift.
        if evidence.timeline_tick != record.timeline_tick:
            raise TemporalAnchorMismatchError(
                f"Timeline tick mismatch: evidence.timeline_tick={evidence.timeline_tick} "
                f"!= record.timeline_tick={record.timeline_tick}. "
                f"Appraisal must be anchored to the experience's Phase 8C tick."
            )

        # ─── Guard 7: Idempotency (Req 8) ──────────────────────────────────────
        # One experience × one facet → one authoritative appraisal.
        pair_key = (evidence.experience_id, evidence.facet_key)
        if pair_key in existing_appraisal_pairs:
            raise DuplicateAppraisalError(
                f"An authoritative appraisal already exists for "
                f"(experience_id={evidence.experience_id!r}, facet_key={evidence.facet_key!r}). "
                f"Use revision events for retrospective re-appraisal (not yet implemented in 16.3)."
            )

        # ─── Evaluation Priority Chain (Blocker 2) ────────────────────────────
        signal = evidence.grounded_signal
        # NOTE: qualia_summary is NEVER read here. Only grounded_signal drives evaluation.

        if signal in self.UNAMBIGUOUS_SIGNAL_MAP:
            # Priority 1: Unambiguous signal → temperament bypassed entirely (G42)
            appraisal_kind = self.UNAMBIGUOUS_SIGNAL_MAP[signal]

        elif signal in self.AMBIGUOUS_SIGNAL_TEMPERAMENT_MAP:
            # Priority 2: Ambiguous signal → temperament as deterministic tie-break
            compat = temperament.compatibility
            appraisal_kind = self.AMBIGUOUS_SIGNAL_TEMPERAMENT_MAP[signal][compat]

        else:
            # Priority 3: Unknown signal → fail-closed (no fallback, no temperament rescue)
            raise UnknownGroundedSignalError(
                f"Unknown grounded_signal '{signal}'. Signal must be registered in "
                f"UNAMBIGUOUS_SIGNAL_MAP or AMBIGUOUS_SIGNAL_TEMPERAMENT_MAP. "
                f"Fail-closed: no temperament-based appraisal fabrication allowed."
            )

        # ─── Produce FacetAppraisalRecord ──────────────────────────────────────
        return FacetAppraisalRecord(
            appraisal_id=str(uuid.uuid4()),
            experience_id=record.experience_id,
            character_id=record.character_id,
            domain_key=record.domain_key,
            facet_key=record.facet_key,
            appraisal_kind=appraisal_kind,
            evidence_id=evidence.evidence_id,
            grounded_signal=signal,
            # Engine-set timeline_tick = record.timeline_tick (Blocker 5, non-configurable)
            timeline_tick=record.timeline_tick,
            created_at=utc_now(),
        )
