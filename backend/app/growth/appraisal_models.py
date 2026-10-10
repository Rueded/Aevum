"""Phase 16.3 Appraisal & Preference Formation Models.

Defines all Phase 16.3 pure types: enums, immutable DTOs, error hierarchy,
frozen policy constants, and pure helper functions for appraisal and preference logic.

Constitutional Locks:
- FacetAppraisalKind is imported from Phase 16.1 experiential_models; NEVER redefined here.
  Phase 16.1 owns FacetAppraisalKind; Phase 16.3 consumes it.
- Lock 8 (Permanent Note A): Zero floats. All threshold comparisons use integer arithmetic.
- Lock 3 (Anti-Sycophancy): User preferences and recommendations cannot create Aevum's appraisals.
- User Preference Non-Authority Lock: Tier-3 evidence kinds are permanently blocked.
- qualia_summary is a display/audit field; it has zero influence on appraisal logic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict

# Phase 16.1 owns FacetAppraisalKind. Phase 16.3 imports and re-exports it.
# DO NOT redefine FacetAppraisalKind here.
from app.growth.experiential_models import FacetAppraisalKind  # noqa: F401


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


# =============================================================================
# Error Hierarchy
# =============================================================================

class AppraisalEpistemicError(Exception):
    """Base exception for Phase 16.3 appraisal and preference epistemic violations."""
    pass


class DuplicateAppraisalError(AppraisalEpistemicError):
    """Raised when (experience_id, facet_key) already has an authoritative appraisal.

    One experience × one facet → one authoritative appraisal (Req 8 idempotency).
    """
    pass


class UnregisteredFacetError(AppraisalEpistemicError):
    """Raised when facet_key is not registered under domain_key in character_interest_facets."""
    pass


class AppraisalMutationProhibitedError(AppraisalEpistemicError):
    """Raised when an UPDATE or DELETE is attempted on character_facet_appraisals (immutable log).

    Canonical definition is also present in growth_db_models for ORM event use.
    """
    pass


class UngroundedAppraisalEvidenceError(AppraisalEpistemicError):
    """Raised when evidence is Tier-3 (user statement), PROPOSED, REJECTED, or otherwise unauthorized."""
    pass


class AppraisalIdentityMismatchError(AppraisalEpistemicError):
    """Raised when evidence character_id/domain_key/facet_key/experience_id don't match the record."""
    pass


class TemporalAnchorMismatchError(AppraisalEpistemicError):
    """Raised when evidence.timeline_tick != record.timeline_tick (Blocker 5)."""
    pass


class UnknownGroundedSignalError(AppraisalEpistemicError):
    """Raised when grounded_signal is not in UNAMBIGUOUS_SIGNAL_MAP or AMBIGUOUS_SIGNAL_TEMPERAMENT_MAP.

    Fail-closed: unknown signals never generate an appraisal via temperament fallback.
    """
    pass


class IllegalPolarityStabilityCombinationError(AppraisalEpistemicError):
    """Raised when a (PreferencePolarity163, StabilityTier) pair violates Gate 0 Blocker 4 invariant table."""
    pass


# =============================================================================
# Enums — Phase 16.3 (all str, Enum — zero floats)
# =============================================================================

class AppraisalEvidenceKind(str, Enum):
    """Authority tier classification for appraisal evidence sources.

    Tier 1: System-minted interaction-backed evidence. LLM cannot produce these.
    Tier 2: LLM-contributed proposals. Require anchor validation before becoming GROUNDED.
    Tier 3: User statements. Always rejected at Guard 1.
    """
    # Tier 1 — Interaction-backed (system-minted, LLM-excluded)
    BEHAVIORAL_ENGAGEMENT_OUTCOME = "BEHAVIORAL_ENGAGEMENT_OUTCOME"
    SHARED_CO_EXPERIENCE_REACTION = "SHARED_CO_EXPERIENCE_REACTION"
    # Tier 2 — LLM-contributed proposal (anchor validation required before GROUNDED)
    DIRECT_FIRST_PERSON_REACTION = "DIRECT_FIRST_PERSON_REACTION"
    # Tier 3 — Non-authority (always rejected at FacetAppraisalEngine Guard 1)
    USER_RECOMMENDATION_REJECTED = "USER_RECOMMENDATION_REJECTED"
    USER_PREFERENCE_REJECTED = "USER_PREFERENCE_REJECTED"


class AppraisalEvidenceStatus(str, Enum):
    """Lifecycle status of an AppraisalEvidence DTO."""
    PROPOSED = "PROPOSED"   # LLM-contributed; anchor validation pending
    GROUNDED = "GROUNDED"   # Anchor-validated; eligible for FacetAppraisalEngine
    REJECTED = "REJECTED"   # Failed validation; permanently excluded


class TemperamentCompatibility(str, Enum):
    """Deterministic temperament compatibility prior for a (domain, facet) pair.

    NOT a probability. NOT a float. NOT a generative authority.
    Acts as a deterministic tie-break ONLY for ambiguous (Priority 2) grounded signals.
    Bypassed entirely for unambiguous (Priority 1) signals. (Blocker 2)
    """
    STRONGLY_RESONANT = "STRONGLY_RESONANT"   # Natural alignment
    RESONANT = "RESONANT"                     # Comfortable alignment
    NEUTRAL = "NEUTRAL"                       # Neither affinity nor friction
    FRICTION = "FRICTION"                     # Baseline resistance
    STRONG_FRICTION = "STRONG_FRICTION"       # Acute aesthetic or values clash


class PolarityBucket(str, Enum):
    """Discrete mathematical aggregation bucket for consistency computation.

    POSITIVE: {STRONGLY_ATTRACTED, ENJOYABLE}
    NEUTRAL:  {NEUTRAL_INDIFFERENT}
    NEGATIVE: {TEDIOUS_EXHAUSTING, AVERSIVE_DISLIKED}
    """
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"


class PreferencePolarity163(str, Enum):
    """Phase 16.3 rich longitudinal taste posture (7-value).

    IMPORTANT: This is DISTINCT from Phase 16.2 state_machine.PreferencePolarity (4-value).
    Compatibility projection to 16.2 is handled exclusively by PreferenceCompatibilityProjector.
    Do NOT import this enum into state_machine.py or interest_domain_service.py.
    """
    UNFORMED = "UNFORMED"
    STRONGLY_PREFERRED = "STRONGLY_PREFERRED"
    PREFERRED = "PREFERRED"
    NEUTRAL = "NEUTRAL"
    DISLIKED = "DISLIKED"
    AVOIDED = "AVOIDED"
    MIXED_AMBIVALENT = "MIXED_AMBIVALENT"


class StabilityTier(str, Enum):
    """Epistemic consolidation tier — degree of resistance to transient noise."""
    UNFORMED = "UNFORMED"           # No formed preference yet
    TENTATIVE = "TENTATIVE"         # 2+ sessions; easily swayed
    STABILIZED = "STABILIZED"       # 3+ sessions; resists isolated outliers
    CONSOLIDATED = "CONSOLIDATED"   # 5+ sessions; high inertia


class PreferenceRevisionKind(str, Enum):
    """Orthogonal revision tracking — decoupled from PreferencePolarity163 (Watchpoint 5)."""
    NONE = "NONE"
    COUNTER_EVIDENCE_ACCUMULATING = "COUNTER_EVIDENCE_ACCUMULATING"
    REVISION_TRIGGERED = "REVISION_TRIGGERED"


class CompositeDomainPreference(str, Enum):
    """Derived multi-facet categorical domain preference projection.

    NO scalar averaging. NO affinity scores. Pure categorical composition.
    """
    UNFORMED = "UNFORMED"
    COMPOSITE_POSITIVE = "COMPOSITE_POSITIVE"
    COMPOSITE_NEGATIVE = "COMPOSITE_NEGATIVE"
    COMPOSITE_MIXED = "COMPOSITE_MIXED"
    COMPOSITE_NEUTRAL = "COMPOSITE_NEUTRAL"


# =============================================================================
# Frozen Constants & Policy Thresholds
# =============================================================================

TIER_1_EVIDENCE_KINDS: frozenset[AppraisalEvidenceKind] = frozenset({
    AppraisalEvidenceKind.BEHAVIORAL_ENGAGEMENT_OUTCOME,
    AppraisalEvidenceKind.SHARED_CO_EXPERIENCE_REACTION,
})

TIER_2_EVIDENCE_KINDS: frozenset[AppraisalEvidenceKind] = frozenset({
    AppraisalEvidenceKind.DIRECT_FIRST_PERSON_REACTION,
})

BLOCKED_EVIDENCE_KINDS: frozenset[AppraisalEvidenceKind] = frozenset({
    AppraisalEvidenceKind.USER_RECOMMENDATION_REJECTED,
    AppraisalEvidenceKind.USER_PREFERENCE_REJECTED,
})

# Gate 0 Blocker 4: Legal (PreferencePolarity163, StabilityTier) combinations.
# MIXED_AMBIVALENT is always TENTATIVE (never STABILIZED or CONSOLIDATED).
# UNFORMED is always UNFORMED (never any other stability).
LEGAL_POLARITY_STABILITY_COMBOS: frozenset[tuple[str, str]] = frozenset({
    (PreferencePolarity163.UNFORMED.value,           StabilityTier.UNFORMED.value),
    (PreferencePolarity163.STRONGLY_PREFERRED.value, StabilityTier.TENTATIVE.value),
    (PreferencePolarity163.STRONGLY_PREFERRED.value, StabilityTier.STABILIZED.value),
    (PreferencePolarity163.STRONGLY_PREFERRED.value, StabilityTier.CONSOLIDATED.value),
    (PreferencePolarity163.PREFERRED.value,          StabilityTier.TENTATIVE.value),
    (PreferencePolarity163.PREFERRED.value,          StabilityTier.STABILIZED.value),
    (PreferencePolarity163.PREFERRED.value,          StabilityTier.CONSOLIDATED.value),
    (PreferencePolarity163.NEUTRAL.value,            StabilityTier.TENTATIVE.value),
    (PreferencePolarity163.NEUTRAL.value,            StabilityTier.STABILIZED.value),
    (PreferencePolarity163.NEUTRAL.value,            StabilityTier.CONSOLIDATED.value),
    (PreferencePolarity163.DISLIKED.value,           StabilityTier.TENTATIVE.value),
    (PreferencePolarity163.DISLIKED.value,           StabilityTier.STABILIZED.value),
    (PreferencePolarity163.DISLIKED.value,           StabilityTier.CONSOLIDATED.value),
    (PreferencePolarity163.AVOIDED.value,            StabilityTier.TENTATIVE.value),
    (PreferencePolarity163.AVOIDED.value,            StabilityTier.STABILIZED.value),
    (PreferencePolarity163.AVOIDED.value,            StabilityTier.CONSOLIDATED.value),
    (PreferencePolarity163.MIXED_AMBIVALENT.value,   StabilityTier.TENTATIVE.value),
    # MIXED_AMBIVALENT + STABILIZED is ILLEGAL
    # MIXED_AMBIVALENT + CONSOLIDATED is ILLEGAL
    # UNFORMED + TENTATIVE/STABILIZED/CONSOLIDATED is ILLEGAL
})

# Stability advancement thresholds (integer math — Permanent Note A, zero floats)
TENTATIVE_APPRAISAL_THRESHOLD: int = 2
TENTATIVE_SESSION_THRESHOLD: int = 2
TENTATIVE_DOMINANCE_PERCENTAGE: int = 60

STABILIZED_APPRAISAL_THRESHOLD: int = 4
STABILIZED_SESSION_THRESHOLD: int = 3
STABILIZED_DOMINANCE_PERCENTAGE: int = 75

CONSOLIDATED_APPRAISAL_THRESHOLD: int = 7
CONSOLIDATED_SESSION_THRESHOLD: int = 5
CONSOLIDATED_DOMINANCE_PERCENTAGE: int = 80

# MIXED threshold: sufficient data but no bucket achieves 60% dominance
MIXED_APPRAISAL_THRESHOLD: int = 4
MIXED_SESSION_THRESHOLD: int = 3
MIXED_DOMINANCE_FLOOR_PERCENTAGE: int = 60

# Epistemic inertia: required opposing evidence to trigger revision
INERTIA_REVISION_APPRAISAL_THRESHOLD: int = 3
INERTIA_REVISION_SESSION_THRESHOLD: int = 2

# STRONGLY_PREFERRED / AVOIDED intensity thresholds
# Requires dominant-bucket appraisals to be at least 60% of total for "strong" classification
STRONG_INTENSITY_PERCENTAGE: int = 60


# =============================================================================
# DTOs (Pydantic, frozen=True, extra="forbid", zero floats)
# =============================================================================

class CharacterTemperamentProfile(BaseModel):
    """Deterministic temperament compatibility descriptor for a (domain, facet) pair.

    NOT a probability. NOT a float weight. A discrete categorical prior
    that acts as a tie-break for ambiguous signals only. (Blocker 2)
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    facet_key: str
    domain_key: str
    compatibility: TemperamentCompatibility


class AppraisalEvidence(BaseModel):
    """Immutable evidence DTO anchoring an episodic facet appraisal.

    Must carry evidence_status=GROUNDED before entering FacetAppraisalEngine.
    qualia_summary is a display/audit field — zero influence on appraisal logic.
    timeline_tick must equal the anchoring ExperientialRecord.timeline_tick. (Blocker 5)
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    evidence_kind: AppraisalEvidenceKind
    evidence_status: AppraisalEvidenceStatus
    experience_id: str
    character_id: str
    domain_key: str
    facet_key: str
    timeline_tick: int                # Must == record.timeline_tick (Blocker 5)
    grounded_signal: str              # Categorical tag used in engine logic
    qualia_summary: str = ""          # Display/audit ONLY. Zero influence on appraisal logic.
    evidence_source_ref: str


class FacetAppraisalRecord(BaseModel):
    """Immutable output of FacetAppraisalEngine for a single episodic appraisal.

    timeline_tick is set by the engine to record.timeline_tick. Callers cannot configure it.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    appraisal_id: str
    experience_id: str
    character_id: str
    domain_key: str
    facet_key: str
    appraisal_kind: FacetAppraisalKind
    evidence_id: str
    grounded_signal: str
    timeline_tick: int                # = experience.timeline_tick (engine-set, non-configurable)
    created_at: datetime


class PersonalPreferenceRecord(BaseModel):
    """Materialized preference projection for a (character, domain, facet) triple.

    This is a DERIVED PROJECTION of character_facet_appraisals — not a source of truth.
    Fully rebuildable from the appraisal stream alone. (Req 7)
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    preference_id: str
    character_id: str
    domain_key: str
    facet_key: str
    preference_polarity: PreferencePolarity163
    stability_tier: StabilityTier
    revision_kind: PreferenceRevisionKind
    appraisal_count: int
    distinct_session_count: int
    last_evaluated_tick: Optional[int]
    updated_at: datetime


# =============================================================================
# Pure Helper Functions (no I/O, no async)
# =============================================================================

def map_appraisal_to_bucket(kind: FacetAppraisalKind) -> PolarityBucket:
    """Pure deterministic mapping from FacetAppraisalKind to PolarityBucket.

    POSITIVE: {STRONGLY_ATTRACTED, ENJOYABLE}
    NEUTRAL:  {NEUTRAL_INDIFFERENT}
    NEGATIVE: {TEDIOUS_EXHAUSTING, AVERSIVE_DISLIKED}
    """
    if kind in (FacetAppraisalKind.STRONGLY_ATTRACTED, FacetAppraisalKind.ENJOYABLE):
        return PolarityBucket.POSITIVE
    if kind == FacetAppraisalKind.NEUTRAL_INDIFFERENT:
        return PolarityBucket.NEUTRAL
    return PolarityBucket.NEGATIVE  # TEDIOUS_EXHAUSTING or AVERSIVE_DISLIKED


def evaluate_consistency_threshold(
    bucket_count: int,
    total_count: int,
    required_percentage: int,
) -> bool:
    """Exact integer ratio comparison (Permanent Note A — Zero Floats).

    Equivalent to: (bucket_count / total_count) >= (required_percentage / 100)
    Formulated as: bucket_count * 100 >= total_count * required_percentage

    Args:
        bucket_count: Count of appraisals in the target bucket.
        total_count: Total appraisal count.
        required_percentage: Integer percentage threshold (e.g. 75 means 75%).

    Returns:
        True if bucket_count / total_count >= required_percentage / 100.
    """
    if total_count == 0:
        return False
    return (bucket_count * 100) >= (total_count * required_percentage)


def validate_legal_polarity_stability_combo(
    polarity: PreferencePolarity163,
    stability: StabilityTier,
) -> None:
    """Enforce Gate 0 Blocker 4 invariant table. Raises on illegal combination.

    MIXED_AMBIVALENT is always TENTATIVE.
    UNFORMED is always UNFORMED.
    Any other combination with UNFORMED polarity is illegal.
    """
    combo = (polarity.value, stability.value)
    if combo not in LEGAL_POLARITY_STABILITY_COMBOS:
        raise IllegalPolarityStabilityCombinationError(
            f"Illegal (PreferencePolarity163={polarity.value}, StabilityTier={stability.value}) "
            f"combination. "
            f"MIXED_AMBIVALENT must always be TENTATIVE; UNFORMED must always pair with UNFORMED."
        )


def compute_composite_domain_preference(
    facet_preferences: list[PersonalPreferenceRecord],
) -> CompositeDomainPreference:
    """Derive categorical composite domain preference from per-facet preferences.

    NO scalar averaging. NO affinity scores. Pure categorical composition (Req 9).

    Algorithm:
    - formed = facets with non-UNFORMED, non-MIXED_AMBIVALENT polarity
    - positive_formed = {STRONGLY_PREFERRED, PREFERRED}
    - negative_formed = {DISLIKED, AVOIDED}
    - neutral_formed  = {NEUTRAL}
    - positive AND negative → COMPOSITE_MIXED
    - positive only → COMPOSITE_POSITIVE
    - negative only → COMPOSITE_NEGATIVE
    - neutral only  → COMPOSITE_NEUTRAL
    - nothing formed → COMPOSITE_UNFORMED
    """
    if not facet_preferences:
        return CompositeDomainPreference.UNFORMED

    formed = [
        f for f in facet_preferences
        if f.preference_polarity not in (
            PreferencePolarity163.UNFORMED,
            PreferencePolarity163.MIXED_AMBIVALENT,
        )
    ]

    if not formed:
        return CompositeDomainPreference.UNFORMED

    positive_formed = [
        f for f in formed
        if f.preference_polarity in (
            PreferencePolarity163.STRONGLY_PREFERRED,
            PreferencePolarity163.PREFERRED,
        )
    ]
    negative_formed = [
        f for f in formed
        if f.preference_polarity in (
            PreferencePolarity163.DISLIKED,
            PreferencePolarity163.AVOIDED,
        )
    ]
    neutral_formed = [
        f for f in formed
        if f.preference_polarity == PreferencePolarity163.NEUTRAL
    ]

    if positive_formed and negative_formed:
        return CompositeDomainPreference.COMPOSITE_MIXED
    if positive_formed:
        return CompositeDomainPreference.COMPOSITE_POSITIVE
    if negative_formed:
        return CompositeDomainPreference.COMPOSITE_NEGATIVE
    if neutral_formed:
        return CompositeDomainPreference.COMPOSITE_NEUTRAL
    return CompositeDomainPreference.UNFORMED
