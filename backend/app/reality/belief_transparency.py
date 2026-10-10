"""Context Assembly & Belief Transparency Layer (Phase 14.5).

Governed by ADR-025 (Revision 1):
- Lock 10 — Belief Maturity != Truth:
    Epistemic confidence vocabulary (CONSTRUCTING, EMERGING, ESTABLISHED) tracks
    belief maturity, not truth. Time elapsed and cycle age are maturity signals only.
    A belief does not become more true because it is old.
- Three Orthogonal Axes:
    1. CanonicalStatus (Axis 1: Truth) — what the reality engine believes
    2. RecallLevel     (Axis 2: Clarity) — how vividly Aevum subjectively recalls it
    3. BeliefMaturity  (Axis 3: Maturity) — how long / how supported the belief is
- Decision D3 — CONSTRUCTING Epistemic State:
    CONSTRUCTING is an internal epistemic state, NOT a prescribed utterance template.
    Natural-language realization is delegated to the conversational LLM via
    <autonomous_belief_state> context injection. Architecture must not hardcode
    utterance patterns for any epistemic state.
- Decision D4 — Bounded Context:
    Belief revision history injected into prompt context is strictly bounded
    (e.g., max 5 records from BeliefRevisionRepository.get_recent()).
- Pure Read Projection:
    Pure serialization; zero canonical mutation authority (0 set_fact, 0 token minting).
"""

from __future__ import annotations

from datetime import datetime, timezone
import enum
import hashlib
import json
import logging
from typing import Any, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.biography.biography_models import CanonicalStatus, RecallLevel
from app.reality.belief_revision import BeliefRevisionRecord
from app.reality.candidate_models import CandidateHypothesis

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums (Axis 3: Belief Maturity)
# ---------------------------------------------------------------------------

class BeliefMaturity(str, enum.Enum):
    """Categorical maturity of an internal belief (ADR-025 Axis 3).

    Orthogonal to:
    - CanonicalStatus (Axis 1: Epistemic truth / ledger state)
    - RecallLevel     (Axis 2: Phenomenological recall clarity)
    """

    CONSTRUCTING = "CONSTRUCTING"
    """Active exploration, unpromoted candidate hypothesis, or unresolved competitive slot.
    Signals genuine epistemic ambiguity; prompts authentic humble uncertainty without
    hardcoded utterance templates or confabulation (Decision D3)."""

    EMERGING = "EMERGING"
    """Provisional belief supported across cycles (>= 1 cycle isolation boundary) or with
    a decisive competitive margin (Δ >= 0.15), OR a newly promoted canonical fact before
    long-term evidence stability is confirmed."""

    ESTABLISHED = "ESTABLISHED"
    """Long-standing canonical fact grounded in temporal duration AND verified evidence
    stability without unaddressed contradiction (Lock 10)."""


# ---------------------------------------------------------------------------
# Immutable DTOs
# ---------------------------------------------------------------------------

class BeliefTransparencyItem(BaseModel):
    """Immutable representation of a belief projected along the 3 orthogonal axes.

    Constitutional Invariant:
    - CanonicalStatus, RecallLevel, and BeliefMaturity are strictly orthogonal.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    slot_name: str = Field(..., description="Target biographical or reality slot name.")
    asserted_value: Any = Field(..., description="Belief value or proposed attribute value.")
    canonical_status: CanonicalStatus = Field(..., description="Axis 1: Truth status in reality ledger.")
    recall_level: RecallLevel = Field(
        default=RecallLevel.VIVID,
        description="Axis 2: Experiential recall clarity.",
    )
    belief_maturity: BeliefMaturity = Field(..., description="Axis 3: Epistemic support maturity.")
    cycles_observed: int = Field(default=1, ge=1, description="Number of RCL cycles this belief was observed.")
    evidence_count: int = Field(default=1, ge=0, description="Independent corroborating evidence count.")
    evidence_stable: bool = Field(default=True, description="True if free of unaddressed contradictions.")
    candidate_id: Optional[str] = Field(default=None, description="Originating CandidateHypothesis ID if provisional.")
    epistemic_notes: Optional[str] = Field(default=None, description="Optional diagnostic context.")


class BeliefTransparencyState(BaseModel):
    """Immutable collection of projected beliefs and bounded revision records.

    Constitutional Invariant:
    - Pure read-only projection (Decision D4: bounded revision history).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    character_id: str = Field(default="aevum", description="Target character identity.")
    active_beliefs: tuple[BeliefTransparencyItem, ...] = Field(
        default_factory=tuple,
        description="Active beliefs across core slots and candidate hypotheses.",
    )
    recent_revisions: tuple[BeliefRevisionRecord, ...] = Field(
        default_factory=tuple,
        description="Bounded revision history (max 5 records per Decision D4).",
    )
    context_hash_sha256: str = Field(
        default="",
        description="Deterministic SHA-256 hash of the canonical belief projection for replay integrity.",
    )


# ---------------------------------------------------------------------------
# Belief Maturity Classifier (Lock 10 Invariant Engine)
# ---------------------------------------------------------------------------

class BeliefMaturityClassifier:
    """Pure evaluation engine determining belief maturity according to Lock 10.

    Constitutional Lock 10:
    Belief maturity is NOT truth, and cycle age/time elapsed ALONE cannot create
    an ESTABLISHED belief. Maturity requires both temporal duration (cycles >= 2)
    AND evidence stability (evidence >= 2 and stable=True) on a CANONICAL fact.
    """

    MIN_ESTABLISHED_CYCLES: int = 2
    MIN_ESTABLISHED_EVIDENCE: int = 2

    @classmethod
    def classify(
        cls,
        canonical_status: CanonicalStatus,
        cycles_observed: int = 1,
        evidence_count: int = 1,
        evidence_stable: bool = True,
        has_decisive_margin: bool = False,
    ) -> BeliefMaturity:
        """Classify belief maturity along Axis 3 enforcing Lock 10.

        Rules:
        1. Lock 10: ESTABLISHED requires:
           - canonical_status == CanonicalStatus.CANONICAL
           - cycles_observed >= 2
           - evidence_count >= 2
           - evidence_stable is True
           (Cycle count alone, even 100 cycles, cannot make a fact ESTABLISHED without evidence stability)
        2. EMERGING if:
           - canonical_status == CanonicalStatus.CANONICAL (newly promoted or pending multi-evidence)
           - OR (canonical_status == CanonicalStatus.PROVISIONAL and evidence_stable is True and
                 (has_decisive_margin is True or evidence_count >= 2 or cycles_observed >= 2))
        3. CONSTRUCTING in all other cases:
           - Provisional in initial cycle with single evidence and no decisive margin
           - Disputed status (CanonicalStatus.DISPUTED)
           - Evidence unstable (evidence_stable is False)
           - Undefined status (CanonicalStatus.UNDEFINED)
        """
        # 1. Lock 10: Test for ESTABLISHED
        if (
            canonical_status == CanonicalStatus.CANONICAL
            and cycles_observed >= cls.MIN_ESTABLISHED_CYCLES
            and evidence_count >= cls.MIN_ESTABLISHED_EVIDENCE
            and evidence_stable is True
        ):
            return BeliefMaturity.ESTABLISHED

        # 2. Test for EMERGING
        if evidence_stable is True:
            # Canonical facts that haven't yet reached ESTABLISHED criteria start as EMERGING
            if canonical_status == CanonicalStatus.CANONICAL:
                return BeliefMaturity.EMERGING

            # Provisional candidates with decisive margin or accumulated evidence/cycles
            if canonical_status == CanonicalStatus.PROVISIONAL:
                if has_decisive_margin or evidence_count >= 2 or cycles_observed >= 2:
                    return BeliefMaturity.EMERGING

        # 3. Everything else is CONSTRUCTING (unresolved slot, active competition, disputed, unstable)
        return BeliefMaturity.CONSTRUCTING


# ---------------------------------------------------------------------------
# Belief Transparency Adapter (Prompt XML Context Serializer)
# ---------------------------------------------------------------------------

class BeliefTransparencyAdapter:
    """Pure serialization adapter projecting belief transparency into prompt XML.

    Constitutional Disciplines:
    - Pure Read Projection: Zero canonical mutations (zero writes, zero tokens).
    - Decision D3: CONSTRUCTING is an epistemic state, NOT an utterance template.
    - Decision D4: Bounded revision history (max 5 records).
    - Bitwise Replay Determinism: Replay-stable SHA-256 hash.
    """

    MAX_RECENT_REVISIONS: int = 5

    @classmethod
    def build_transparency_state(
        cls,
        character_id: str = "aevum",
        active_beliefs: Sequence[BeliefTransparencyItem] = (),
        recent_revisions: Sequence[BeliefRevisionRecord] = (),
    ) -> BeliefTransparencyState:
        """Constructs an immutable BeliefTransparencyState with bounded revisions and deterministic hash."""
        bounded_revisions = tuple(recent_revisions[-cls.MAX_RECENT_REVISIONS:])
        beliefs_tuple = tuple(active_beliefs)

        # Compute deterministic SHA-256 hash over semantic items (excluding execution timestamps)
        hasher = hashlib.sha256()
        hasher.update(character_id.encode("utf-8"))
        for b in sorted(beliefs_tuple, key=lambda x: x.slot_name):
            entry = f"{b.slot_name}:{b.asserted_value}:{b.canonical_status.value}:{b.recall_level.value}:{b.belief_maturity.value}:{b.cycles_observed}:{b.evidence_count}:{b.evidence_stable}"
            hasher.update(entry.encode("utf-8"))
        for r in bounded_revisions:
            r_entry = f"{r.revision_id}:{r.slot_name}:{r.revision_kind.value}:{r.prior_value}:{r.revised_value}"
            hasher.update(r_entry.encode("utf-8"))

        context_hash = hasher.hexdigest()

        return BeliefTransparencyState(
            character_id=character_id,
            active_beliefs=beliefs_tuple,
            recent_revisions=bounded_revisions,
            context_hash_sha256=context_hash,
        )

    @classmethod
    def format_autonomous_belief_state(cls, state: BeliefTransparencyState) -> str:
        """Format BeliefTransparencyState into structured <autonomous_belief_state> XML.

        Decision D3 Compliance:
        The constitutional guidance instructs the LLM on epistemic clarity and humble
        uncertainty for CONSTRUCTING states, but does NOT prescribe utterance templates
        or canned phrases.
        """
        lines: list[str] = [
            "<autonomous_belief_state>",
            "  <constitutional_guidance>",
            "    BELIEFS ARE AUTONOMOUSLY CONSTRUCTED WITH VARYING MATURITY ACROSS THREE ORTHOGONAL AXES:",
            "    1. Canonical Status: Epistemic ledger truth (CANONICAL / PROVISIONAL / DISPUTED / UNDEFINED).",
            "    2. Recall Level: Subjective memory clarity (VIVID / HAZY / FRAGMENTARY / UNDEFINED).",
            "    3. Belief Maturity: Support history (CONSTRUCTING / EMERGING / ESTABLISHED).",
            "    EPISTEMIC POSTURE DIRECTIVES:",
            "    - CONSTRUCTING: Active exploration/hypothesis; genuine epistemic ambiguity; express natural humble uncertainty, do not invent answers.",
            "    - EMERGING: Provisional belief supported across cycles; express as tentative or growing conviction.",
            "    - ESTABLISHED: Long-standing canonical reality; express with grounded confidence.",
            "    - DO NOT CONFABULATE: Do not treat unconfirmed hypotheses or unpromoted candidates as established reality.",
            "  </constitutional_guidance>",
        ]

        # Active beliefs block
        if state.active_beliefs:
            lines.append(f'  <active_beliefs count="{len(state.active_beliefs)}">')
            for b in sorted(state.active_beliefs, key=lambda x: x.slot_name):
                val_json = json.dumps(b.asserted_value, ensure_ascii=False)
                lines.append(
                    f'    <belief slot="{b.slot_name}" status="{b.canonical_status.value}" '
                    f'recall="{b.recall_level.value}" maturity="{b.belief_maturity.value}" '
                    f'cycles="{b.cycles_observed}" evidence_count="{b.evidence_count}">'
                )
                lines.append(f"      <value>{val_json}</value>")
                if b.candidate_id:
                    lines.append(f"      <candidate_id>{b.candidate_id}</candidate_id>")
                if b.epistemic_notes:
                    lines.append(f"      <epistemic_notes>{b.epistemic_notes}</epistemic_notes>")
                lines.append("    </belief>")
            lines.append("  </active_beliefs>")
        else:
            lines.append('  <active_beliefs count="0" />')

        # Recent belief revisions block (Decision D4 bounded context)
        if state.recent_revisions:
            lines.append(f'  <recent_belief_revisions count="{len(state.recent_revisions)}">')
            for r in state.recent_revisions:
                prior_json = json.dumps(r.prior_value, ensure_ascii=False) if r.prior_value is not None else "null"
                revised_json = json.dumps(r.revised_value, ensure_ascii=False) if r.revised_value is not None else "null"
                lines.append(
                    f'    <revision id="{r.revision_id}" kind="{r.revision_kind.value}" '
                    f'slot="{r.slot_name}" cycle="{r.trigger_cycle_id}">'
                )
                lines.append(f"      <prior_value>{prior_json}</prior_value>")
                lines.append(f"      <revised_value>{revised_json}</revised_value>")
                lines.append(f"      <rationale>{r.rationale}</rationale>")
                lines.append("    </revision>")
            lines.append("  </recent_belief_revisions>")
        else:
            lines.append('  <recent_belief_revisions count="0" />')

        lines.append("</autonomous_belief_state>")
        return "\n".join(lines)

    @classmethod
    def item_from_candidate(
        cls,
        candidate: CandidateHypothesis,
        recall_level: RecallLevel = RecallLevel.VIVID,
        cycles_observed: int = 1,
        evidence_count: Optional[int] = None,
        evidence_stable: bool = True,
        has_decisive_margin: bool = False,
        canonical_status: CanonicalStatus = CanonicalStatus.PROVISIONAL,
    ) -> BeliefTransparencyItem:
        """Helper building BeliefTransparencyItem directly from a CandidateHypothesis."""
        if evidence_count is None:
            evidence_count = getattr(candidate, "evidence_count", len(candidate.evidence_families))
        maturity = BeliefMaturityClassifier.classify(
            canonical_status=canonical_status,
            cycles_observed=cycles_observed,
            evidence_count=evidence_count,
            evidence_stable=evidence_stable,
            has_decisive_margin=has_decisive_margin,
        )
        return BeliefTransparencyItem(
            slot_name=candidate.slot_name,
            asserted_value=candidate.proposed_value,
            canonical_status=canonical_status,
            recall_level=recall_level,
            belief_maturity=maturity,
            cycles_observed=cycles_observed,
            evidence_count=evidence_count,
            evidence_stable=evidence_stable,
            candidate_id=candidate.candidate_id,
            epistemic_notes=candidate.quarantine_reason or None,
        )

    @classmethod
    def item_from_canonical_fact(
        cls,
        slot_name: str,
        value: Any,
        recall_level: RecallLevel = RecallLevel.VIVID,
        cycles_observed: int = 2,
        evidence_count: int = 2,
        evidence_stable: bool = True,
        epistemic_notes: Optional[str] = None,
    ) -> BeliefTransparencyItem:
        """Helper building BeliefTransparencyItem for an established or emerging canonical fact."""
        maturity = BeliefMaturityClassifier.classify(
            canonical_status=CanonicalStatus.CANONICAL,
            cycles_observed=cycles_observed,
            evidence_count=evidence_count,
            evidence_stable=evidence_stable,
            has_decisive_margin=True,
        )
        return BeliefTransparencyItem(
            slot_name=slot_name,
            asserted_value=value,
            canonical_status=CanonicalStatus.CANONICAL,
            recall_level=recall_level,
            belief_maturity=maturity,
            cycles_observed=cycles_observed,
            evidence_count=evidence_count,
            evidence_stable=evidence_stable,
            epistemic_notes=epistemic_notes,
        )
