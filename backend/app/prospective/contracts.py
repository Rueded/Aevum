"""Phase 19.1 — Prospective Contracts, Epistemic DTOs & Schema Isolation.

Defines the pure immutable data transfer objects, enums, and structural contracts
for Prospective Memory, Unresolved Cognitive Threads, and Experiential Continuity.

Architectural Locks & Rules:
- GC-437: Experiential Continuity Over Memory Retrieval
- GC-438 ~ GC-450: The 13 Constitutional "≠" Invariants:
  - Open ≠ TODO
  - Open ≠ Action Required
  - Memory ≠ Prospective Thread
  - Trigger ≠ Keyword Match
  - Salience ≠ Importance Alone
  - Intention ≠ Action
  - Action ≠ Experience
  - Experience ≠ Preference
  - Remembering ≠ Mentioning
  - Open ≠ Must Be Mentioned
  - User Future ≠ Aevum Responsibility
  - Time Passing ≠ Automatic Proactivity
  - Open ≠ Belief
- Permanent Note A: Zero pseudo-probability float scoring fields.
- Schema Isolation: ProspectiveThread does NOT inherit from or multiplex with
  MemoryRecord, LifeActivity, Task, Reminder, Goal, or Notification.
- Zero execution logic, zero LLM calls, zero database mutations.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ============================================================================
# Core Enums
# ============================================================================

class ThreadLifecycleState(str, Enum):
    """Discrete cognitive lifecycle states of an unresolved thread.
    
    State transition rules are intentionally deferred to Phase 19.2.
    """
    ACTIVE = "ACTIVE"        # Fresh in conscious foreground awareness
    QUIET = "QUIET"          # Settled into background awareness, accessible
    DORMANT = "DORMANT"      # Subconscious residue, requires context-adaptive cue
    CLOSED = "CLOSED"        # Concluded through real-world outcome or explicit abandonment
    FORGOTTEN = "FORGOTTEN"  # Naturally dissolved into oblivion without resolution


class ThreadDomainKind(str, Enum):
    """Ownership triad partitioning the mental origin and accountability domain.
    
    Prevents user future possibilities from becoming Aevum's task obligations.
    """
    SELF = "SELF"              # Aevum's own unfinished personal life pursuits
    USER = "USER"              # Observed unresolved possibilities in user's life (0 task accountability)
    RELATIONAL = "RELATIONAL"  # Shared conversational or activity arcs between Aevum and user


class ClosureReasonKind(str, Enum):
    """The discrete mode by which an unresolved thread concluded."""
    REALIZED = "REALIZED"      # Possibility materialized in real action/outcome
    ABANDONED = "ABANDONED"    # Explicitly dropped, postponed indefinitely, or redirected
    OBSOLETED = "OBSOLETED"    # Premise invalidated by circumstances or timeline lapse


class ThreadProvenanceKind(str, Enum):
    """The origin context in which the prospective thread took seed."""
    CONVERSATIONAL_SPONTANEOUS = "CONVERSATIONAL_SPONTANEOUS"  # Spontaneous reaction to user dialogue
    LIFE_SIMULATION_EMERGENT = "LIFE_SIMULATION_EMERGENT"      # Reflection from Aevum's autonomous life
    SHARED_INTERACTION = "SHARED_INTERACTION"                  # Collaborative/joint activity moment


class EpistemicStanceKind(str, Enum):
    """The epistemic nature of the future-oriented thread.
    
    Strictly adheres to GC-450: Open ≠ Belief.
    Separates Intention ≠ Expectation ≠ Prediction ≠ Belief.
    Notice that 'BELIEF' is strictly excluded from prospective thread stances.
    """
    INTENTION = "INTENTION"      # Expressed desire or uncommitted plan ("想学摄影")
    EXPECTATION = "EXPECTATION"  # Anticipated possibility with open outcome ("可能年底换城市")
    PREDICTION = "PREDICTION"    # Tentative situational extrapolation ("那部电影可能快下映了")


# ============================================================================
# Descriptive Salience Coordinates (Zero Floats, Pure Qualitative Semantics)
# ============================================================================

class GravityTier(str, Enum):
    """Real-world objective weight or life thickness of the event."""
    TRIVIAL = "TRIVIAL"          # Daily fleeting chatter (e.g. choice of snack)
    MODERATE = "MODERATE"        # Casual hobby, weekend outing, recreational gear
    SIGNIFICANT = "SIGNIFICANT"  # Career shift, major relocation, foundational project
    PIVOTAL = "PIVOTAL"          # Life-defining milestone or existential transition


class ResonanceTier(str, Enum):
    """Subjective alignment with Aevum's self-identity, taste, and interests (Phase 16)."""
    PERIPHERAL = "PERIPHERAL"    # Little to no personal aesthetic/interest intersection
    MODERATE = "MODERATE"        # Mild curiosity or conversational affinity
    DEEP_CORE = "DEEP_CORE"      # Touches Aevum's core aesthetic, artistic, or worldview priors


class UncertaintyTier(str, Enum):
    """The degree of open-endedness regarding how or whether the thread resolves."""
    TENTATIVE_CHOICE = "TENTATIVE_CHOICE"  # Weighing multiple alternatives
    OPEN_EXPLORATION = "OPEN_EXPLORATION"  # Open-ended curiosity with unknown trajectory
    HIGHLY_CONTINGENT = "HIGHLY_CONTINGENT"  # Dependent on unpredictable external conditions


class ThreadEnduranceTier(str, Enum):
    """Natural cognitive staying power distinguishing durable arcs from conversational noise."""
    EPHEMERAL_TALK = "EPHEMERAL_TALK"  # Conversational spark, fades quickly without reinforcement
    SEASONAL = "SEASONAL"              # Lasts over weeks/months across casual encounters
    DURABLE_ARC = "DURABLE_ARC"        # Multi-month or year-long longitudinal thread


class SalienceCoordinates(BaseModel):
    """Four-dimensional descriptive coordinates representing thread salience.
    
    Constitutional Lock:
    The four dimensions are strictly descriptive analytical coordinates,
    NOT an additive scoring function, threshold formula, or thread-creation filter.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    gravity: GravityTier = Field(
        ...,
        description="Objective real-world gravity of the underlying topic.",
    )
    resonance: ResonanceTier = Field(
        ...,
        description="Subjective alignment with Aevum's personal interests and aesthetic priors.",
    )
    uncertainty: UncertaintyTier = Field(
        ...,
        description="Degree of outcome open-endedness and unresolved tension.",
    )
    endurance: ThreadEnduranceTier = Field(
        ...,
        description="Natural cognitive endurance distinguishing durable arcs from ephemeral noise.",
    )


# ============================================================================
# Prospective Thread (The Core Semantic Container)
# ============================================================================

class ProspectiveThread(BaseModel):
    """Semantic container representing an unresolved future-oriented cognitive thread.
    
    Normative Architecture Definition:
    An Open Thread is a semantic structure within Aevum's continuous state model
    representing a future-oriented direction that has not yet reached a real-world
    resolution, and still holds sufficient continued significance.
    
    Constitutional Invariants Enforced by Type & Validators:
    - Open ≠ TODO (extra='forbid', zero task/reminder/assignee/priority fields)
    - Open ≠ Action Required (pure state container, zero execution authority)
    - Memory ≠ Prospective Thread (isolated schema, zero inheritance from MemoryRecord)
    - Open ≠ Belief (epistemic_stance strictly limited to non-belief open attitudes)
    - Consistent Closure Lifecycle (closure_reason & closed_at strictly governed by state)
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    thread_id: str = Field(
        ...,
        min_length=1,
        description="Canonical identifier of the thread (e.g. 'thrd_a1b2c3d4').",
    )
    character_id: str = Field(
        ...,
        min_length=1,
        description="Identifier of the character owning this perspective (e.g. 'aevum').",
    )
    user_id: str = Field(
        ...,
        min_length=1,
        description="Identifier of the conversation partner / user.",
    )
    domain: ThreadDomainKind = Field(
        ...,
        description="Ownership domain: SELF (Aevum's own), USER (user's life), or RELATIONAL (us).",
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Concise semantic label of the unresolved thread (e.g. '胶片摄影探索').",
    )
    narrative_anchor: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Contextual narrative origin describing where the thread took seed.",
    )
    epistemic_stance: EpistemicStanceKind = Field(
        ...,
        description="Epistemic nature of the future orientation (INTENTION, EXPECTATION, PREDICTION).",
    )
    lifecycle_state: ThreadLifecycleState = Field(
        ...,
        description="Discrete cognitive lifecycle state (ACTIVE, QUIET, DORMANT, CLOSED, FORGOTTEN).",
    )
    salience: SalienceCoordinates = Field(
        ...,
        description="Four-dimensional descriptive coordinates (Gravity, Resonance, Uncertainty, Endurance).",
    )
    provenance: ThreadProvenanceKind = Field(
        ...,
        description="Origin context: conversational, autonomous life emergent, or shared interaction.",
    )
    created_at: datetime = Field(
        ...,
        description="Authoritative timestamp when the thread took seed.",
    )
    updated_at: datetime = Field(
        ...,
        description="Authoritative timestamp when the thread state was last updated.",
    )
    last_contextual_contact_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp of the most recent contextual touchpoint or recall.",
    )
    closure_reason: Optional[ClosureReasonKind] = Field(
        default=None,
        description="Reason for closure, present if and only if lifecycle_state is CLOSED.",
    )
    closure_summary: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Brief summary of how the thread resolved, if CLOSED.",
    )
    closed_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when closure occurred, present if and only if lifecycle_state is CLOSED.",
    )

    @model_validator(mode="after")
    def validate_closure_invariants(self) -> "ProspectiveThread":
        """Enforces strict bidirectional closure lifecycle invariants."""
        if self.lifecycle_state == ThreadLifecycleState.CLOSED:
            if self.closure_reason is None:
                raise ValueError(
                    "ProspectiveThread with lifecycle_state=CLOSED must specify 'closure_reason'."
                )
            if self.closed_at is None:
                raise ValueError(
                    "ProspectiveThread with lifecycle_state=CLOSED must specify 'closed_at'."
                )
        else:
            if self.closure_reason is not None:
                raise ValueError(
                    f"ProspectiveThread with lifecycle_state={self.lifecycle_state.value} "
                    f"must NOT have 'closure_reason' (got: {self.closure_reason.value})."
                )
            if self.closed_at is not None:
                raise ValueError(
                    f"ProspectiveThread with lifecycle_state={self.lifecycle_state.value} "
                    f"must NOT have 'closed_at'."
                )
        return self
