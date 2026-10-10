"""biography_models.py — Phase 12 Biographical Ontology & Contract DTOs.

Governed by ADR-023:
1. Immutability: frozen=True, extra="forbid" across all models.
2. Two orthogonal axes: CanonicalStatus (truth) vs RecallLevel (phenomenology).
3. First-class HistoryScope domain identity (AEVUM_PERSONAL vs SHARED_WITH_USER).
4. Epistemic causal integrity with domain-level CausalKnowledgeState (KNOWN / UNKNOWN).
5. Zero float confidence fields: absolute ban on pseudo-probability numbers.
6. Pure data models: zero DB, zero LLM, zero network, zero mutation authority.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self


# ============================================================================
# 1. Categorical Enums
# ============================================================================

class HistoryScope(str, Enum):
    """First-class domain scope segregating personal history from shared journey."""
    AEVUM_PERSONAL = "AEVUM_PERSONAL"      # Aevum's own life history / personal past
    SHARED_WITH_USER = "SHARED_WITH_USER"  # Co-experienced journey with the user


class LifeEra(str, Enum):
    """Developmental life eras without hardcoded age ranges or dynamic temporal states.
    
    Dynamic temporal positioning (PAST / CURRENT / FUTURE) is governed exclusively
    by Phase 8C's Authoritative Clock and Temporal Position Engine.
    """
    EARLY_CHILDHOOD = "EARLY_CHILDHOOD"
    PRIMARY_SCHOOL = "PRIMARY_SCHOOL"
    SECONDARY_SCHOOL = "SECONDARY_SCHOOL"
    POST_SECONDARY = "POST_SECONDARY"
    UNIVERSITY = "UNIVERSITY"
    ADULTHOOD = "ADULTHOOD"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class CanonicalStatus(str, Enum):
    """Epistemic truth and reality ledger status (Axis 1: Truth).
    
    Orthogonal to phenomenological recall clarity (RecallLevel).
    """
    CANONICAL = "CANONICAL"          # Ground-truth fact verified and sealed in reality ledger
    PROVISIONAL = "PROVISIONAL"      # Candidate fact under observation or verification
    DISPUTED = "DISPUTED"            # Refuted or conflicting claim under Phase 9.5 repair
    UNDEFINED = "UNDEFINED"          # Completely outside established canonical reality


class RecallLevel(str, Enum):
    """Phenomenological recall quality and experiential vividness (Axis 2: Clarity).
    
    Orthogonal to epistemic reality status (CanonicalStatus).
    A canonical fact may be subjectively hazy; an ungrounded hallucination could be vivid.
    """
    VIVID = "VIVID"                  # Rich experiential details, clear chronological sequence
    HAZY = "HAZY"                    # Confirmed core outline, but granular details are faded
    FRAGMENTARY = "FRAGMENTARY"      # Isolated sensory or episodic flash without full context
    UNDEFINED = "UNDEFINED"          # No experiential memory exists


class CausalKnowledgeState(str, Enum):
    """Domain-level semantic state for causal attributions.
    
    Guarantees UNKNOWN is a first-class programmatic state rather than a prompt tag.
    """
    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"


class CausalRelationType(str, Enum):
    """Structural causal derivation types for causal explanation graphs."""
    ORIGINATED_FROM = "ORIGINATED_FROM"  # Direct genesis or origin event/fact
    CATALYZED_BY = "CATALYZED_BY"        # Triggered or accelerated by an external catalyst
    CONDITIONED_BY = "CONDITIONED_BY"    # Constrained or enabled by a background condition
    MOTIVATED_BY = "MOTIVATED_BY"        # Driven by an internal goal or value orientation


class BiographicalDomain(str, Enum):
    """Ontological domain categories for personal facts and life experiences."""
    ORIGIN_AND_IDENTITY = "ORIGIN_AND_IDENTITY"        # Birthplace, heritage, native language
    EDUCATION_AND_GROWTH = "EDUCATION_AND_GROWTH"      # Schools, mentors, learning milestones
    PASSION_AND_DISCIPLINE = "PASSION_AND_DISCIPLINE"  # Programming spark, technical philosophies
    LIFESTYLE_AND_RHYTHM = "LIFESTYLE_AND_RHYTHM"      # Tea rituals, routines, hobbies
    RELATIONAL_AND_SOCIAL = "RELATIONAL_AND_SOCIAL"    # Childhood friends, teachers, family
    SHARED_USER_JOURNEY = "SHARED_USER_JOURNEY"        # Shared experiences with user


class PreferenceAffinity(str, Enum):
    """Attitudinal orientation toward personal preferences."""
    FAVORITE = "FAVORITE"
    ENJOYS = "ENJOYS"
    NEUTRAL = "NEUTRAL"
    DISLIKES = "DISLIKES"


# ============================================================================
# 2. Immutable DTOs & Contracts
# ============================================================================

class QualiaAnchor(BaseModel):
    """Sensory qualia anchor capturing episodic texture of memories."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    qualia_id: str
    sensory_modality: str  # e.g., "olfactory", "auditory", "visual", "multisensory"
    description: str       # e.g., "smell of dried tea leaves and whistle of the iron kettle"
    emotional_coloring: Optional[str] = None  # e.g., "serene", "nostalgic"


class SocialContactRecord(BaseModel):
    """Third-party social contacts and relationship anchors in personal history."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    contact_id: str
    display_name: str
    relation_role: str                     # e.g., "grandfather", "coding_club_peer", "high_school_math_teacher"
    era_first_met: LifeEra
    scope: HistoryScope = HistoryScope.AEVUM_PERSONAL
    is_user: bool = False

    @model_validator(mode="after")
    def validate_contact_isolation(self) -> Self:
        if self.scope == HistoryScope.AEVUM_PERSONAL and self.is_user:
            raise ValueError("Lock 4 Violation: Aevum personal past cannot contain the User as a personal contact")
        if self.is_user and self.scope != HistoryScope.SHARED_WITH_USER:
            raise ValueError("Contact representing the user must have HistoryScope.SHARED_WITH_USER")
        return self


class CausalRelation(BaseModel):
    """Structural causal derivation edge in the canonical causal explanation graph.
    
    The explanation graph is constrained to be an acyclic DAG within a causal scope.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    relation_id: str
    source_id: str  # ID of the antecedent event or background fact
    target_id: str  # ID of the resultant preference, habit, or life event
    relation_type: CausalRelationType
    narrative_summary: str

    @model_validator(mode="after")
    def validate_anti_self_loop(self) -> Self:
        if self.source_id == self.target_id:
            raise ValueError(f"Self-referential causal relation forbidden: source_id={self.source_id} == target_id")
        return self


class PersonalPreference(BaseModel):
    """Grounded personal preference with strict domain-level causal state."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    preference_id: str
    category: str                               # e.g., "beverage", "music", "computing"
    object_name: str                            # e.g., "black tea", "classical piano", "systems programming"
    affinity: PreferenceAffinity
    era_acquired: LifeEra
    causal_state: CausalKnowledgeState = CausalKnowledgeState.UNKNOWN
    causal_relation_id: Optional[str] = None    # Set only when causal_state == KNOWN

    @model_validator(mode="after")
    def validate_causal_consistency(self) -> Self:
        if self.causal_state == CausalKnowledgeState.UNKNOWN and self.causal_relation_id is not None:
            raise ValueError("UNKNOWN causal_state cannot have causal_relation_id")
        if self.causal_state == CausalKnowledgeState.KNOWN and not self.causal_relation_id:
            raise ValueError("KNOWN causal_state requires non-empty causal_relation_id")
        return self


class BiographicalFact(BaseModel):
    """Slow-moving or invariant state assertions about Aevum holding across time windows."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    fact_id: str
    domain: BiographicalDomain
    subject: str = "aevum"
    attribute_key: str                          # e.g., "birth_place", "native_language"
    attribute_value: str                        # e.g., "Johor Bahru", "Mandarin"
    scope: HistoryScope = HistoryScope.AEVUM_PERSONAL
    era: LifeEra
    canonical_status: CanonicalStatus = CanonicalStatus.CANONICAL
    recall_level: RecallLevel = RecallLevel.VIVID
    provenance: str                             # e.g., "seed_canon", "verified_dialogue"
    valid_from_era: LifeEra
    valid_to_era: Optional[LifeEra] = None

    @model_validator(mode="after")
    def validate_fact_invariants(self) -> Self:
        if self.scope == HistoryScope.AEVUM_PERSONAL and self.subject != "aevum":
            raise ValueError("BiographicalFact with AEVUM_PERSONAL scope must have subject='aevum'")
        return self


class LifeEventRecord(BaseModel):
    """Discrete bounded temporal occurrence that happened to or was enacted by Aevum."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str
    scope: HistoryScope = HistoryScope.AEVUM_PERSONAL
    era: LifeEra
    domain: BiographicalDomain
    headline: str
    summary: str
    location_anchor: Optional[str] = None
    participant_ids: list[str] = Field(default_factory=list)
    user_present: bool = False
    session_anchor: Optional[str] = None
    canonical_status: CanonicalStatus = CanonicalStatus.CANONICAL
    recall_level: RecallLevel = RecallLevel.VIVID
    qualia_ids: list[str] = Field(default_factory=list)
    causal_antecedent_ids: list[str] = Field(default_factory=list)
    resultant_fact_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_scope_domain_consistency(self) -> Self:
        """Lock 4: Domain-Scope Alignment.
        
        HistoryScope governs domain authority (whom this history belongs to).
        user_present, participants, and session_anchor are flexible provenance/participant metadata.
        Explicit semantic conflict: BiographicalDomain.SHARED_USER_JOURNEY requires HistoryScope.SHARED_WITH_USER.
        """
        if self.domain == BiographicalDomain.SHARED_USER_JOURNEY and self.scope != HistoryScope.SHARED_WITH_USER:
            raise ValueError(
                "Lock 4 Violation: BiographicalDomain.SHARED_USER_JOURNEY requires HistoryScope.SHARED_WITH_USER"
            )
        return self


class BiographicalAnchor(BaseModel):
    """Seed/Content Design Guideline container combining facts, events, qualia, and contacts.
    
    Anchors are non-mandatory (Resolution 8): Aevum may contain a bounded set of anchors
    when independently established by evidence. No anchor is mandatory.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    anchor_id: str
    domain: BiographicalDomain
    core_fact: BiographicalFact
    key_event: Optional[LifeEventRecord] = None
    qualia: Optional[QualiaAnchor] = None
    primary_contact: Optional[SocialContactRecord] = None
    canonical_status: CanonicalStatus = CanonicalStatus.CANONICAL
    recall_level: RecallLevel = RecallLevel.VIVID
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_domain_alignment(self) -> Self:
        if self.core_fact.domain != self.domain:
            raise ValueError(
                f"Anchor domain '{self.domain}' does not match core_fact domain '{self.core_fact.domain}'"
            )
        if self.key_event is not None and self.key_event.domain != self.domain:
            raise ValueError(
                f"Anchor domain '{self.domain}' does not match key_event domain '{self.key_event.domain}'"
            )
        return self
