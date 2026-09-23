"""Contradiction and Reconciliation domain models (Phase 7B.3).

Defines contradiction categories, repair strategies, and structured resolution outputs.
"""

import enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.reality.belief_models import EpistemicStatus


class ContradictionType(str, enum.Enum):
    """Categorical nature of an epistemic or conversational contradiction."""

    NONE = "NONE"
    SURFACE_TENSION = "SURFACE_TENSION"                # Apparent mismatch reconcilable via contextual bridge
    GENUINE_MISSPEAK = "GENUINE_MISSPEAK"              # Character verbal slip (e.g. graduated 5 years ago at age 20)
    USER_FACTUAL_ERROR = "USER_FACTUAL_ERROR"          # User asserts objective falsehood (e.g. sun rises in west)
    WORLD_KNOWLEDGE_CONFLICT = "WORLD_KNOWLEDGE_CONFLICT" # Misattribution in external lore or geography
    SELF_SLIP = "SELF_SLIP"                            # Character notices own oversight during ongoing discourse
    ANOMALOUS_HIGH_IMPACT = "ANOMALOUS_HIGH_IMPACT"    # Sudden massive disruption requiring official verification


class RepairStrategy(str, enum.Enum):
    """Authoritative strategy prescribed by Reality Engine for resolving the contradiction."""

    NONE = "NONE"
    CONTEXTUAL_BRIDGE = "CONTEXTUAL_BRIDGE"            # Provide plausible real-world context (break, holiday, visit)
    MISSPEAK_ADMISSION = "MISSPEAK_ADMISSION"          # Acknowledge human slip of tongue naturally
    FACTUAL_DISAGREEMENT = "FACTUAL_DISAGREEMENT"      # Express natural incredulity / correction without trust loss
    SELF_CORRECTION = "SELF_CORRECTION"                # Rectify own geographical or logical slip gracefully
    DEMAND_VERIFICATION = "DEMAND_VERIFICATION"        # Treat as unverified pending proof; preserve current state


class ContradictionResolution(BaseModel):
    """Structured resolution produced by ContradictionResolver."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contradiction_type: ContradictionType = Field(default=ContradictionType.NONE)
    repair_strategy: RepairStrategy = Field(default=RepairStrategy.NONE)
    contextual_bridge: Optional[str] = Field(
        default=None,
        description="Suggested real-world contextual explanation (e.g. 'semester_break', 'weekend_family_visit').",
    )
    repair_guidance: Optional[str] = Field(
        default=None,
        description="Machine guidance instructing social/LLM layer how to repair in-character.",
    )
    canonical_mutated: bool = Field(
        default=False,
        description="Whether canonical Core reality was altered (bridges must NEVER mutate reality).",
    )
    claim_status: EpistemicStatus = Field(
        default=EpistemicStatus.KNOWN,
        description="Epistemic outcome status of the underlying claim.",
    )
    rationale: str = Field(
        default="",
        description="Explainable reasoning for the contradiction resolution.",
    )
