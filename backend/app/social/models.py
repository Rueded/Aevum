"""Social World & Emergent Life domain models for Aevum Core (Phase 7C.4).

Enforces:
- Invariant 15.5: Multidimensional NPC Relational Dynamics (4 orthogonal axes).
- Invariant 15.7: Grounded NPC Reality Integrity (Append-only facts with supersession).
- Rule 16: Relationships are never collapsed into a single affinity or romance metric.
"""

from datetime import datetime, timezone
from enum import Enum
import math
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_normalized_float(v: float, field_name: str) -> float:
    if math.isnan(v) or math.isinf(v):
        raise ValueError(f"{field_name} must be a finite number.")
    return max(0.0, min(1.0, float(v)))


class IdentityState(str, Enum):
    """Emergent identity progression for an encountered entity (Lock-in Item 2)."""
    ANONYMOUS = "ANONYMOUS"      # Initial slot; observed presence in a venue
    RECOGNIZED = "RECOGNIZED"    # Familiar presence; recognized face/routine
    IDENTIFIED = "IDENTIFIED"    # Stable canonical display_name established


class SocialOpportunityLevel(str, Enum):
    """Contextual affordance for social encounters (Lock-in Item 4)."""
    NONE = "NONE"      # Private spaces (HOME), sleeping, solo recovery
    LOW = "LOW"        # Quiet public spaces, solo transit
    MEDIUM = "MEDIUM"  # Semi-public communal spaces (park, cafe)
    HIGH = "HIGH"      # Structured collaborative or shared spaces (library study, campus hall)


class EncounterType(str, Enum):
    """Qualitative nature of the encounter interaction."""
    PASSING_PRESENCE = "PASSING_PRESENCE"          # Shared venue, visual awareness
    TRANSACTIONAL = "TRANSACTIONAL"                # Service exchange (coffee, book checkout)
    CASUAL_CHAT = "CASUAL_CHAT"                    # Brief informal exchange
    FOCUSED_COLLABORATION = "FOCUSED_COLLABORATION"# Working together on coursework / project
    ACADEMIC_INQUIRY = "ACADEMIC_INQUIRY"          # Formal consultation / asking instructor


class InteractionDepth(str, Enum):
    """Depth of interaction during an encounter."""
    GLANCE_OR_PRESENCE = "GLANCE_OR_PRESENCE"
    TRANSACTIONAL = "TRANSACTIONAL"
    CASUAL_EXCHANGE = "CASUAL_EXCHANGE"
    FOCUSED_COLLABORATION = "FOCUSED_COLLABORATION"
    DEEP_CONVERSATION = "DEEP_CONVERSATION"


class SocialContactStatus(str, Enum):
    """Lifecycle status of candidate and canonical social contacts."""
    PROVISIONAL = "PROVISIONAL"  # Candidate accumulating early evidence
    ELIGIBLE = "ELIGIBLE"        # Candidate ready for promotion evaluation
    PROMOTED = "PROMOTED"        # Candidate promoted to canonical reality
    ACTIVE = "ACTIVE"            # Promoted canonical social contact
    REJECTED = "REJECTED"        # Inadmissible or contradicted candidate
    DORMANT = "DORMANT"          # Contact with faded interaction
    ARCHIVED = "ARCHIVED"        # Explicitly archived contact


class SocialDynamics(BaseModel):
    """Immutable 4-axis orthogonal relationship metrics between Aevum and an NPC.

    Enforces Invariant 15.5 & Rule 16:
    - familiarity: How recognizable they are (routine, presence).
    - comfort: Ease and casualness of conversation.
    - respect: Regard for competence, role, or intellect.
    - trust: Emotional vulnerability and reliability.
    Metrics never collapse into a single romance or affinity score.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    familiarity: float = Field(default=0.05, ge=0.0, le=1.0)
    comfort: float = Field(default=0.10, ge=0.0, le=1.0)
    respect: float = Field(default=0.50, ge=0.0, le=1.0)
    trust: float = Field(default=0.10, ge=0.0, le=1.0)

    @field_validator("familiarity", "comfort", "respect", "trust", mode="before")
    @classmethod
    def validate_metrics(cls, v: float, info: object) -> float:
        name = getattr(info, "field_name", "metric")
        return _validate_normalized_float(float(v), name)

    def apply_encounter(
        self,
        encounter_type: EncounterType,
        interaction_depth: InteractionDepth,
        valence: float = 0.0,
    ) -> "SocialDynamics":
        """Compute bounded, causal orthogonal progression (GC-038 & GC-042).

        Increments are strictly bounded [0.01, 0.08] and decoupled across dimensions.
        """
        d_fam = 0.0
        d_com = 0.0
        d_res = 0.0
        d_tru = 0.0

        if encounter_type == EncounterType.PASSING_PRESENCE:
            d_fam = 0.03
            d_com = 0.01
        elif encounter_type == EncounterType.TRANSACTIONAL:
            d_fam = 0.04
            d_com = 0.02
            d_tru = 0.01
        elif encounter_type == EncounterType.CASUAL_CHAT:
            d_fam = 0.06
            d_com = 0.05
            d_res = 0.02
            d_tru = 0.02
        elif encounter_type == EncounterType.FOCUSED_COLLABORATION:
            d_fam = 0.07
            d_com = 0.04
            d_res = 0.06
            d_tru = 0.05
        elif encounter_type == EncounterType.ACADEMIC_INQUIRY:
            d_fam = 0.05
            d_com = 0.02
            d_res = 0.08
            d_tru = 0.03

        # Interaction depth booster
        if interaction_depth in (InteractionDepth.FOCUSED_COLLABORATION, InteractionDepth.DEEP_CONVERSATION):
            d_com += 0.02
            d_tru += 0.02

        # Valence modulation (pleasant interaction boosts comfort; friction reduces comfort and respect)
        if valence > 0.0:
            d_com += min(0.04, 0.04 * valence)
        elif valence < 0.0:
            # Friction penalty overcomes default chat comfort gain
            d_com -= (0.05 + 0.05 * abs(valence))
            d_res -= (0.03 + 0.03 * abs(valence))

        return SocialDynamics(
            familiarity=_validate_normalized_float(self.familiarity + d_fam, "familiarity"),
            comfort=_validate_normalized_float(self.comfort + d_com, "comfort"),
            respect=_validate_normalized_float(self.respect + d_res, "respect"),
            trust=_validate_normalized_float(self.trust + d_tru, "trust"),
        )


class SocialCandidate(BaseModel):
    """Provisional candidate accumulating evidence prior to promotion (Invariant 15.3)."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    character_id: str = "aevum"
    role_template_id: str
    identity_state: IdentityState = IdentityState.ANONYMOUS
    status: SocialContactStatus = SocialContactStatus.PROVISIONAL
    first_observed_at: datetime
    last_observed_at: datetime
    encounter_count: int = Field(default=1, ge=1)
    dynamics: SocialDynamics = Field(default_factory=SocialDynamics)


class NPCEntity(BaseModel):
    """Authoritative domain representation of a promoted canonical contact."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    character_id: str = "aevum"
    candidate_id: Optional[str] = None
    role_template_id: str
    display_name: str
    relationship_label: str
    traits: str
    status: SocialContactStatus = SocialContactStatus.ACTIVE
    dynamics: SocialDynamics
    first_met_at: datetime
    last_encountered_at: Optional[datetime] = None


class NPCFact(BaseModel):
    """Append-only canonical fact about an NPC with supersession support (Lock-in Item 1)."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    npc_id: str
    fact_key: str
    fact_value: str
    status: str = "ACTIVE"
    supersedes_id: Optional[str] = None
    superseded_by: Optional[str] = None
    source_encounter_id: Optional[str] = None
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None
    established_at: datetime = Field(default_factory=_utc_now)
