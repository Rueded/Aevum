"""Interest Domain State Machine & Temporal Gating Engine (Phase 16.2).

Constitutional Invariants & Guardrails Enforced:
- Lock 1 & Lock 9: Experience Provenance Eligibility Barrier.
  Only verified DIRECT_INTERACTION and SHARED_INTERACTION count as lived personal experiences.
  USER_REPORTED, OBSERVED_MEDIA, VICARIOUS_DESCRIPTION, SIMULATED, UNKNOWN, and fictional frames
  strictly do NOT contribute to personal experience or familiarity levels (Knowledge != Experience).
- Scope Invariance: PersonalGrowthState is strictly invariant under caller-selected evaluation context.
  Autobiographical claim scope (SOLITARY vs SHARED) is projected via a decoupled function.
- Orthogonality Lock: ExperienceLevel (session-governed depth) and FamiliarityLevel (facet-governed breadth)
  are strictly orthogonal. Neither dimension directly promotes the other.
- Phase 8C Session Authority: Phase 8C owns semantic temporal/session identity; Phase 16.2 is a pure consumer.
- Ephemeral Metric Projection: PersonalGrowthState metrics are derived projections from the authoritative
  experience record stream, never independently persisted as mutable growth truth in Phase 16.2.
- Curiosity Temporal Precedence: Sequential evidence ordered strictly by timeline_tick. Latest evidence
  determines curiosity posture; subsequent lived experience in the same domain resolves curiosity.
- Permanent Note A: Zero floats across all models and scoring policies.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Sequence
from pydantic import BaseModel, ConfigDict

from app.growth.experiential_models import (
    AutobiographicalClaimScope,
    ExperienceProvenanceKind,
    ExperientialRecord,
    ExposureState,
    FamiliarityLevel,
)


# =============================================================================
# Categorical Enums
# =============================================================================

class LifecycleStage(str, Enum):
    """Derived orchestration view representing the current operational posture for an interest domain."""

    UNEXPOSED = "UNEXPOSED"
    EXPOSED = "EXPOSED"
    CURIOUS = "CURIOUS"
    EXPLORING = "EXPLORING"
    FAMILIAR = "FAMILIAR"
    PREFERENCE_FORMING = "PREFERENCE_FORMING"   # Phase 16.3 Reserved
    ESTABLISHED_TASTE = "ESTABLISHED_TASTE"     # Phase 16.3 Reserved
    SATIATED = "SATIATED"                       # Phase 16.4 Reserved
    DORMANT = "DORMANT"                         # Phase 16.4 Reserved


class ExperienceLevel(str, Enum):
    """Categorical depth of first-person lived experiences across independent sessions."""

    UNEXPERIENCED = "UNEXPERIENCED"  # 0 eligible personal experiences
    NOVICE = "NOVICE"                # 1 to 2 eligible experiences
    PRACTICED = "PRACTICED"          # >= 3 eligible experiences across >= 2 distinct sessions
    EXPERIENCED = "EXPERIENCED"      # >= 7 eligible experiences across >= 4 distinct sessions


class CuriosityState(str, Enum):
    """Provenance-backed state of domain curiosity."""

    UNEXPRESSED = "UNEXPRESSED"      # No curiosity signaled
    INVITED = "INVITED"              # User recommended/invited, but Aevum has not internally engaged
    SELF_EXPRESSED = "SELF_EXPRESSED"# Aevum herself actively expressed curious interest
    RESOLVED = "RESOLVED"            # Satisfied by subsequent hands-on lived experience in this domain


class CuriosityEvidenceKind(str, Enum):
    """Provenance origin of curiosity evidence."""

    USER_RECOMMENDATION = "USER_RECOMMENDATION"
    AEVUM_EXPLICIT_INQUIRY = "AEVUM_EXPLICIT_INQUIRY"
    # AUTONOMOUS_EXPLORATION_DESIRE = "AUTONOMOUS_EXPLORATION_DESIRE" # Phase 17 Reserved


class PreferencePolarity(str, Enum):
    """Placeholder for Phase 16.3 preference polarity baseline."""

    UNFORMED = "UNFORMED"
    ATTRACTED = "ATTRACTED"
    NEUTRAL = "NEUTRAL"
    AVERSIVE = "AVERSIVE"


class ActivityState(str, Enum):
    """Placeholder for Phase 16.4 activity baseline."""

    ACTIVE = "ACTIVE"
    SATIATED = "SATIATED"
    DORMANT = "DORMANT"


# =============================================================================
# Deterministic Domain Policy Thresholds (Operational Policy Contracts)
#
# NOTE: These constants are configurable deterministic operational policy thresholds,
# NOT universal psychological truths, objective empirical laws, or probability metrics.
# They define Aevum's current organizational criteria for categorical progression.
# =============================================================================

PRACTICED_COUNT_THRESHOLD: int = 3
PRACTICED_SESSION_THRESHOLD: int = 2

EXPERIENCED_COUNT_THRESHOLD: int = 7
EXPERIENCED_SESSION_THRESHOLD: int = 4

GROUNDED_COUNT_THRESHOLD: int = 3
GROUNDED_SESSION_THRESHOLD: int = 2

PROFICIENT_COUNT_THRESHOLD: int = 6
PROFICIENT_SESSION_THRESHOLD: int = 4

MULTI_FACET_MINIMUM_THRESHOLD: int = 2


# =============================================================================
# Curiosity Reference Authority & Error Definitions
# =============================================================================

AUTHORIZED_CURIOUS_INQUIRY_PREFIXES = ("turn://", "speech_act://", "dialogue://")
AUTHORIZED_CURIOUS_RECOMMENDATION_PREFIXES = ("speech_act://", "exposure://", "turn://")
DISALLOWED_CURIOUS_EVIDENCE_PATTERNS = ("turn://fake", "speech_act://fake", "tool://fake", "unauthorized://")


class UnanchoredCuriosityEvidenceError(ValueError):
    """Raised when curiosity evidence fails reference authority anchoring."""
    pass


class CuriosityEvidence(BaseModel):
    """Immutable evidence DTO backing curiosity state derivation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_kind: CuriosityEvidenceKind
    domain_key: str
    timeline_tick: int
    evidence_source_ref: str            # e.g. "turn://dialogue/142", "speech_act://gc-384"
    expression_snippet: str = ""        # The verbatim utterance indicating inquiry


def validate_curiosity_evidence_anchoring(evidence: CuriosityEvidence) -> None:
    """Enforces Watchpoint 3: Validates that curiosity evidence references authorized upstream records."""
    ref = evidence.evidence_source_ref.strip()
    if not ref:
        raise UnanchoredCuriosityEvidenceError("evidence_source_ref cannot be empty.")

    for pattern in DISALLOWED_CURIOUS_EVIDENCE_PATTERNS:
        if ref.startswith(pattern):
            raise UnanchoredCuriosityEvidenceError(f"Unauthorized curiosity evidence reference: {ref}")

    if evidence.evidence_kind == CuriosityEvidenceKind.AEVUM_EXPLICIT_INQUIRY:
        if not ref.startswith(AUTHORIZED_CURIOUS_INQUIRY_PREFIXES):
            raise UnanchoredCuriosityEvidenceError(
                f"AEVUM_EXPLICIT_INQUIRY requires authorized conversational prefix: {ref}"
            )
        if not evidence.expression_snippet.strip():
            raise UnanchoredCuriosityEvidenceError("AEVUM_EXPLICIT_INQUIRY requires non-empty expression_snippet.")

    elif evidence.evidence_kind == CuriosityEvidenceKind.USER_RECOMMENDATION:
        if not ref.startswith(AUTHORIZED_CURIOUS_RECOMMENDATION_PREFIXES):
            raise UnanchoredCuriosityEvidenceError(
                f"USER_RECOMMENDATION requires authorized recommendation prefix: {ref}"
            )


# =============================================================================
# Domain State Model (PersonalGrowthState)
# =============================================================================

class PersonalGrowthState(BaseModel):
    """Immutable composite domain state representing personal growth in an interest domain.

    Constitutional Lock:
    All metrics (distinct_session_count, total_experience_count, etc.) are ephemeral
    deterministic projections derived from the authoritative experience record stream;
    they are NEVER independently persisted as mutable growth truth in Phase 16.2.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    character_id: str
    domain_key: str
    exposure_state: ExposureState
    experience_level: ExperienceLevel
    familiarity_level: FamiliarityLevel
    curiosity_state: CuriosityState = CuriosityState.UNEXPRESSED
    preference_polarity: PreferencePolarity = PreferencePolarity.UNFORMED
    activity_state: ActivityState = ActivityState.ACTIVE

    # Concrete, verifiable evidence metrics (Ephemeral deterministic projections from DB stream)
    distinct_session_count: int = 0
    total_experience_count: int = 0
    distinct_facet_count_experienced: int = 0
    first_experience_tick: Optional[int] = None
    latest_experience_tick: Optional[int] = None


# =============================================================================
# Experience Provenance Eligibility Barrier & Claim Projection
# =============================================================================

def is_eligible_personal_experience(record: ExperientialRecord) -> bool:
    """Enforces Lock 1, Lock 9 & Blocker 1: Invariant evaluation of genuine lived personal experiences.

    Rules:
    - If is_fictional_frame is True: False (simulations/fictional frames do not count as real-world lived experience).
    - DIRECT_INTERACTION: True (solitary personal experience).
    - SHARED_INTERACTION: True (co-present shared personal experience with user).
    - USER_REPORTED, OBSERVED_MEDIA, VICARIOUS_DESCRIPTION, SIMULATED, UNKNOWN:
      Strictly False (Knowledge != Experience).
    """
    if record.is_fictional_frame:
        return False
    return record.provenance_kind in (
        ExperienceProvenanceKind.DIRECT_INTERACTION,
        ExperienceProvenanceKind.SHARED_INTERACTION,
    )


def project_autobiographical_claim_support(
    records: Sequence[ExperientialRecord],
    claim_scope: AutobiographicalClaimScope,
) -> bool:
    """Decoupled projection function evaluating whether historical records support a specific dialogue claim.

    Rules:
    - SOLITARY: Requires at least one eligible record with DIRECT_INTERACTION.
      SHARED_INTERACTION cannot support a claim of solitary autonomous execution.
    - SHARED: Requires at least one eligible record with DIRECT_INTERACTION or SHARED_INTERACTION.
    """
    eligible = [r for r in records if is_eligible_personal_experience(r)]
    if not eligible:
        return False
    if claim_scope == AutobiographicalClaimScope.SOLITARY:
        return any(r.provenance_kind == ExperienceProvenanceKind.DIRECT_INTERACTION for r in eligible)
    if claim_scope == AutobiographicalClaimScope.SHARED:
        return True
    return False


# =============================================================================
# Pure Deterministic Derivation Functions
# =============================================================================

def derive_curiosity_state(
    curiosity_evidence_chain: Sequence[CuriosityEvidence],
    eligible_experience_records: Sequence[ExperientialRecord],
    domain_key: Optional[str] = None,
) -> CuriosityState:
    """Derives CuriosityState strictly from chronological evidence and subsequent experience resolution.

    Temporal Precedence & Domain Isolation Rules:
    1. Filter and validate all curiosity evidence anchors.
    2. Filter curiosity evidence for the specified domain_key if provided.
    3. If no valid curiosity evidence exists: return UNEXPRESSED.
    4. Sort curiosity evidence strictly by Phase 8C timeline_tick ascending.
    5. Select latest applicable evidence E_latest.
    6. Check if any eligible personal experience in the SAME domain occurred at or after E_latest.timeline_tick:
       - If yes: return CuriosityState.RESOLVED.
    7. If not resolved:
       - If E_latest.evidence_kind == AEVUM_EXPLICIT_INQUIRY: return CuriosityState.SELF_EXPRESSED.
       - If E_latest.evidence_kind == USER_RECOMMENDATION: return CuriosityState.INVITED.
    8. Default: return CuriosityState.UNEXPRESSED.
    """
    if not curiosity_evidence_chain:
        return CuriosityState.UNEXPRESSED

    valid_evidences: list[CuriosityEvidence] = []
    for ev in curiosity_evidence_chain:
        validate_curiosity_evidence_anchoring(ev)
        if domain_key is None or ev.domain_key == domain_key:
            valid_evidences.append(ev)

    if not valid_evidences:
        return CuriosityState.UNEXPRESSED

    # Sort strictly by Phase 8C authoritative timeline_tick
    sorted_ev = sorted(valid_evidences, key=lambda x: x.timeline_tick)
    latest_ev = sorted_ev[-1]

    # Check for subsequent lived experience resolution within the SAME domain
    target_domain = latest_ev.domain_key
    resolved = any(
        is_eligible_personal_experience(r)
        and r.domain_key == target_domain
        and r.timeline_tick >= latest_ev.timeline_tick
        for r in eligible_experience_records
    )
    if resolved:
        return CuriosityState.RESOLVED

    if latest_ev.evidence_kind == CuriosityEvidenceKind.AEVUM_EXPLICIT_INQUIRY:
        return CuriosityState.SELF_EXPRESSED
    elif latest_ev.evidence_kind == CuriosityEvidenceKind.USER_RECOMMENDATION:
        return CuriosityState.INVITED

    return CuriosityState.UNEXPRESSED


def evaluate_experience_level(records: Sequence[ExperientialRecord]) -> ExperienceLevel:
    """Evaluates depth of engagement across distinct semantic sessions, filtering for eligible experiences only."""
    eligible = [r for r in records if is_eligible_personal_experience(r)]
    if not eligible:
        return ExperienceLevel.UNEXPERIENCED

    distinct_sessions = {r.calendar_session_id for r in eligible if r.calendar_session_id}
    count = len(eligible)

    if count >= EXPERIENCED_COUNT_THRESHOLD and len(distinct_sessions) >= EXPERIENCED_SESSION_THRESHOLD:
        return ExperienceLevel.EXPERIENCED
    if count >= PRACTICED_COUNT_THRESHOLD and len(distinct_sessions) >= PRACTICED_SESSION_THRESHOLD:
        return ExperienceLevel.PRACTICED
    return ExperienceLevel.NOVICE


def evaluate_familiarity_level(
    exposure_state: ExposureState,
    records: Sequence[ExperientialRecord],
) -> FamiliarityLevel:
    """Evaluates breadth across sub-facets and longitudinal session dispersion using eligible experiences only."""
    eligible = [r for r in records if is_eligible_personal_experience(r)]
    if not eligible:
        if exposure_state != ExposureState.UNEXPOSED:
            return FamiliarityLevel.SURFACE_AWARE
        return FamiliarityLevel.UNAWARE

    distinct_sessions = {r.calendar_session_id for r in eligible if r.calendar_session_id}
    distinct_facets = {r.facet_key for r in eligible if r.facet_key}
    count = len(eligible)

    # Requirement: Multi-facet breadth AND longitudinal session dispersion
    if (
        count >= PROFICIENT_COUNT_THRESHOLD
        and len(distinct_sessions) >= PROFICIENT_SESSION_THRESHOLD
        and len(distinct_facets) >= MULTI_FACET_MINIMUM_THRESHOLD
    ):
        return FamiliarityLevel.PROFICIENT
    if (
        count >= GROUNDED_COUNT_THRESHOLD
        and len(distinct_sessions) >= GROUNDED_SESSION_THRESHOLD
        and len(distinct_facets) >= MULTI_FACET_MINIMUM_THRESHOLD
    ):
        return FamiliarityLevel.CONCEPTUALLY_GROUNDED
    return FamiliarityLevel.SURFACE_AWARE


def derive_lifecycle_stage(state: PersonalGrowthState) -> LifecycleStage:
    """Derive the orchestration LifecycleStage from underlying orthogonal factual states.

    Strict Precedence Order (Zero State Masking):
    1. Inactivity overrides (Phase 16.4):
       - If activity_state == DORMANT: return DORMANT
       - If activity_state == SATIATED: return SATIATED
    2. Preference maturity (Phase 16.3):
       - If preference_polarity != UNFORMED and experience_level in (PRACTICED, EXPERIENCED):
         return ESTABLISHED_TASTE
       - If preference_polarity != UNFORMED:
         return PREFERENCE_FORMING
    3. Familiarity depth:
       - If familiarity_level in (CONCEPTUALLY_GROUNDED, PROFICIENT):
         return FAMILIAR
    4. Active exploration:
       - If experience_level in (NOVICE, PRACTICED, EXPERIENCED) or state.total_experience_count > 0:
         return EXPLORING
    5. Inbound self-expressed curiosity:
       - If curiosity_state == CuriosityState.SELF_EXPRESSED:
         return CURIOUS
    6. Exposure / Invitation:
       - If exposure_state != ExposureState.UNEXPOSED or curiosity_state == CuriosityState.INVITED:
         return EXPOSED
    7. Baseline:
       - return UNEXPOSED
    """
    if state.activity_state == ActivityState.DORMANT:
        return LifecycleStage.DORMANT
    if state.activity_state == ActivityState.SATIATED:
        return LifecycleStage.SATIATED

    if state.preference_polarity != PreferencePolarity.UNFORMED:
        if state.experience_level in (ExperienceLevel.PRACTICED, ExperienceLevel.EXPERIENCED):
            return LifecycleStage.ESTABLISHED_TASTE
        return LifecycleStage.PREFERENCE_FORMING

    if state.familiarity_level in (FamiliarityLevel.CONCEPTUALLY_GROUNDED, FamiliarityLevel.PROFICIENT):
        return LifecycleStage.FAMILIAR

    if state.experience_level != ExperienceLevel.UNEXPERIENCED or state.total_experience_count > 0:
        return LifecycleStage.EXPLORING

    if state.curiosity_state == CuriosityState.SELF_EXPRESSED:
        return LifecycleStage.CURIOUS

    if state.exposure_state != ExposureState.UNEXPOSED or state.curiosity_state == CuriosityState.INVITED:
        return LifecycleStage.EXPOSED

    return LifecycleStage.UNEXPOSED
