"""Phase 16.1 Experiential Record Contracts & Provenance Schema.

Defines pure immutable DTOs, 7-tier provenance hierarchy, exposure kinds,
claim eligibility validators, and anti-hallucination qualia barriers.

Constitutional Locks:
- Lock 1: Knowledge != Experience (Provenance Hard Anchor)
- Lock 7: Zero Direct Canonical Mutation (Zero canonical reality mutation authority)
- Lock 8: Pure Categorical Grounding (Absolute Zero Float Types)
- Lock 9: Experience Provenance Non-Equivalence (User said != Aevum experienced)
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class GrowthEpistemicError(Exception):
    """Base exception for personal growth and experiential epistemic violations."""
    pass


class ExperienceMutationProhibitedError(GrowthEpistemicError):
    """Raised when an attempt is made to update or delete an immutable experience record."""
    pass


class UnanchoredExperienceProvenanceError(GrowthEpistemicError):
    """Raised when an experiential record lacks verifiable execution evidence from an authorized provider."""
    pass


class InvalidAutobiographicalClaimError(GrowthEpistemicError):
    """Raised when an autobiographical lived claim is made without qualifying provenance."""
    pass


class Phase17DeferredCapabilityError(GrowthEpistemicError):
    """Raised when a Phase 17 autonomous agency capability is invoked prematurely in Phase 16."""
    pass


class ExposureExperienceContradictionError(GrowthEpistemicError):
    """Raised when exposure is confused with or claimed as direct execution evidence."""
    pass


class ExperienceProvenanceKind(str, Enum):
    """7-Tier Provenance Hierarchy distinguishing first-person engagement from hearsay and observation."""

    DIRECT_INTERACTION = "DIRECT_INTERACTION"
    # An interaction actually executed by an authorized Phase-16 experience provider/tool,
    # with externally verifiable execution provenance.
    # ──► The ONLY provenance supporting solitary "I personally did / played / tried"

    SHARED_INTERACTION = "SHARED_INTERACTION"
    # Co-presence with user in an active session (e.g. streaming audio/media together)
    # ──► Supports "We experienced / played / listened together"
    # ──► Must NOT silently morph into solitary DIRECT_INTERACTION

    OBSERVED_MEDIA = "OBSERVED_MEDIA"
    # Direct sensory processing of media (e.g. audio track played, text lore ingested)
    # ──► Supports "I heard / saw / read"
    # ──► CANNOT support "I played the game"

    USER_REPORTED = "USER_REPORTED"
    # User recounted/narrated an experience to Aevum
    # ──► Supports "You told me about..."
    # ──► CANNOT support "I did..."

    VICARIOUS_DESCRIPTION = "VICARIOUS_DESCRIPTION"
    # Third-party documentation, wiki, guide, or article
    # ──► Supports "I know from documentation..."

    SIMULATED = "SIMULATED"
    # Fictional or sandbox hypothetical thought experiment
    # ──► Supports "In a simulation / hypothetically..."

    UNKNOWN = "UNKNOWN"
    # Insufficient or unanchored signal
    # ──► CANNOT support any autobiographical claim


class ExposureKind(str, Enum):
    """Origin of domain/topic exposure. Exposure describes introduction; provenance describes execution."""

    USER_RECOMMENDATION = "USER_RECOMMENDATION"
    # User mentioned/recommended in dialogue

    SHARED_EXPERIENCE = "SHARED_EXPERIENCE"
    # Done together in active session

    ENVIRONMENTAL_STIMULUS = "ENVIRONMENTAL_STIMULUS"
    # Desktop media playback, system cues

    DIRECT_TOOL_BACKED_EXPERIENCE = "DIRECT_TOOL_BACKED_EXPERIENCE"
    # Authorized tool-assisted session

    AUTONOMOUS_CURIOSITY = "AUTONOMOUS_CURIOSITY"
    # [PHASE 17 RESERVED - STRICTLY LOCKED IN 16]


class FacetAppraisalKind(str, Enum):
    """Immediate qualitative appraisal of a single experiential episode."""

    STRONGLY_ATTRACTED = "STRONGLY_ATTRACTED"
    ENJOYABLE = "ENJOYABLE"
    NEUTRAL_INDIFFERENT = "NEUTRAL_INDIFFERENT"
    TEDIOUS_EXHAUSTING = "TEDIOUS_EXHAUSTING"
    AVERSIVE_DISLIKED = "AVERSIVE_DISLIKED"


class ExposureState(str, Enum):
    """Structural exposure level for an interest domain."""

    UNEXPOSED = "UNEXPOSED"
    EXPOSED = "EXPOSED"
    DIRECTLY_ENCOUNTERED = "DIRECTLY_ENCOUNTERED"


class FamiliarityLevel(str, Enum):
    """Structural familiarity level for an interest facet."""

    UNAWARE = "UNAWARE"
    SURFACE_AWARE = "SURFACE_AWARE"
    CONCEPTUALLY_GROUNDED = "CONCEPTUALLY_GROUNDED"
    PROFICIENT = "PROFICIENT"


class AutobiographicalClaimScope(str, Enum):
    """Scope of first-person autobiographical expression."""

    SOLITARY = "SOLITARY"  # "I personally played / did"
    SHARED = "SHARED"      # "We played / experienced together"


# List of authorized evidence reference prefixes
AUTHORIZED_DIRECT_EVIDENCE_PREFIXES = ("tool://", "exec://", "provider://")
AUTHORIZED_SHARED_EVIDENCE_PREFIXES = ("session://", "stream://", "call://", "copresence://")
DISALLOWED_EVIDENCE_PATTERNS = ("tool://fake", "tool://unauthorized", "tool://whatever", "exec://fake")


class ExperientialRecord(BaseModel):
    """Immutable domain DTO recording a single discrete experience backed by interaction evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    experience_id: str
    character_id: str
    domain_key: str
    facet_key: str
    provenance_kind: ExperienceProvenanceKind
    exposure_kind: ExposureKind
    calendar_session_id: str
    timeline_tick: int                       # Sole semantic temporal anchor (Phase 8C)
    interaction_evidence_ref: str            # Verifiable execution anchor or provider session ID
    qualia_notes: str = ""                   # Descriptive qualitative payload, NEVER a standalone proof
    is_fictional_frame: bool = False


class ExposureEvent(BaseModel):
    """Immutable domain DTO recording an exposure or recommendation event."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    exposure_id: str
    character_id: str
    domain_key: str
    exposure_kind: ExposureKind
    source_speech_act: Optional[str] = None  # e.g. "ASSERTION", "MEME" from Phase 15
    context_notes: str = ""
    timeline_tick: int                       # Semantic clock tick from Phase 8C


class InterestDomainRecord(BaseModel):
    """Immutable domain DTO representing an active interest domain container."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    domain_key: str
    character_id: str
    display_name: str
    exposure_state: ExposureState = ExposureState.UNEXPOSED
    created_at_tick: int


class InterestFacetRecord(BaseModel):
    """Immutable domain DTO representing a sub-facet under an interest domain."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    facet_key: str
    domain_key: str
    character_id: str
    display_name: str
    experience_count: int = 0
    familiarity_level: FamiliarityLevel = FamiliarityLevel.UNAWARE
    last_experienced_tick: Optional[int] = None


# ─────────────────────────────────────────────────────────────────────────────
# Boundary Guard Functions
# ─────────────────────────────────────────────────────────────────────────────

def validate_autobiographical_claim_eligibility(
    provenance: ExperienceProvenanceKind,
    claim_scope: AutobiographicalClaimScope = AutobiographicalClaimScope.SOLITARY,
) -> bool:
    """Enforces Lock 1 & Lock 9: Determines if a provenance kind can support an autobiographical claim.

    Rules:
    - SOLITARY ("I personally did / played"): Strictly requires DIRECT_INTERACTION.
      SHARED_INTERACTION cannot support solitary claims.
    - SHARED ("We did / experienced together"): Requires DIRECT_INTERACTION or SHARED_INTERACTION.
    - All other provenance kinds (OBSERVED_MEDIA, USER_REPORTED, VICARIOUS_DESCRIPTION,
      SIMULATED, UNKNOWN) return False for both scopes.
    """
    if claim_scope == AutobiographicalClaimScope.SOLITARY:
        return provenance == ExperienceProvenanceKind.DIRECT_INTERACTION
    if claim_scope == AutobiographicalClaimScope.SHARED:
        return provenance in (
            ExperienceProvenanceKind.DIRECT_INTERACTION,
            ExperienceProvenanceKind.SHARED_INTERACTION,
        )
    return False


def validate_interaction_evidence_anchoring(
    provenance: ExperienceProvenanceKind,
    evidence_ref: str,
) -> None:
    """Enforces Lock 1, Lock 9, and Blocker 2: Validates that DIRECT and SHARED claims have authentic evidence.

    Raises UnanchoredExperienceProvenanceError if:
    - evidence_ref is empty/whitespace.
    - DIRECT_INTERACTION does not use an authorized direct execution provider.
    - SHARED_INTERACTION does not use an authorized co-presence/session provider.
    - evidence_ref matches known fake/unauthorized patterns.
    """
    if not isinstance(evidence_ref, str) or not evidence_ref.strip():
        raise UnanchoredExperienceProvenanceError(
            f"Provenance {provenance.value} requires a non-empty interaction_evidence_ref."
        )

    ref = evidence_ref.strip()

    # Block known fake/mock strings
    for disallowed in DISALLOWED_EVIDENCE_PATTERNS:
        if ref.startswith(disallowed):
            raise UnanchoredExperienceProvenanceError(
                f"interaction_evidence_ref '{ref}' is an unauthorized mock and cannot anchor {provenance.value}."
            )

    if provenance == ExperienceProvenanceKind.DIRECT_INTERACTION:
        if not any(ref.startswith(prefix) for prefix in AUTHORIZED_DIRECT_EVIDENCE_PREFIXES):
            raise UnanchoredExperienceProvenanceError(
                f"DIRECT_INTERACTION requires an authorized direct provider prefix {AUTHORIZED_DIRECT_EVIDENCE_PREFIXES}, got '{ref}'."
            )
    elif provenance == ExperienceProvenanceKind.SHARED_INTERACTION:
        if not any(ref.startswith(prefix) for prefix in AUTHORIZED_SHARED_EVIDENCE_PREFIXES):
            raise UnanchoredExperienceProvenanceError(
                f"SHARED_INTERACTION requires an authorized shared session prefix {AUTHORIZED_SHARED_EVIDENCE_PREFIXES}, got '{ref}'."
            )


def validate_phase16_exposure_source(kind: ExposureKind) -> None:
    """Enforces Phase 17 Lockout: Rejects AUTONOMOUS_CURIOSITY in Phase 16."""
    if kind == ExposureKind.AUTONOMOUS_CURIOSITY:
        raise Phase17DeferredCapabilityError(
            "AUTONOMOUS_CURIOSITY is strictly deferred to Phase 17 (Agency) and cannot be produced in Phase 16."
        )


def validate_qualia_evidence_barrier(evidence_ref: str, qualia_notes: str) -> None:
    """Enforces Watchpoint 5: qualia_notes cannot self-validate without verified execution evidence."""
    if qualia_notes and (not evidence_ref or not evidence_ref.strip()):
        raise UnanchoredExperienceProvenanceError(
            "qualia_notes cannot self-validate an experience without an authorized interaction_evidence_ref."
        )
