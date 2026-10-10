"""
social_contradiction_models.py — Social Discrepancy & Conversational Repair Contracts

Phase 15.3 Deliverable under ADR-026 (Architecture Gate Approved & Frozen):
- SocialDiscrepancyType enumeration: Benign Independence, Spatial-Temporal Tension,
  World Fact Discrepancy, Pop-Culture Meme Crossing, Biographical Statement Tension,
  Ontological Impossibility.
- TensionSeverity and SocialRepairInquiryStrategy enumerations.
- Immutable SocialDiscrepancyAnalysis DTO with strict Lock 6 anti-compensatory guards:
  `forbidden_compensatory_assumptions` explicitly forbids inventing ungrounded bridge facts.
- Gate Review Core Invariant: Tension != Contradiction != Falsehood.
  Spatial/temporal tensions and pop-culture slips carry `is_genuine_contradiction=False`.
- Pure immutable DTOs (`frozen=True, extra="forbid"`).
- Permanent Note A: Zero float confidence scores or pseudo-probabilities.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field

from app.reality.epistemic_policy_models import EpistemicTreatmentDecision


class SocialDiscrepancyType(str, Enum):
    """Categorical taxonomy of conversational and reality discrepancies."""

    BENIGN_INDEPENDENCE = "BENIGN_INDEPENDENCE"
    # Propositions touch orthogonal ontological slots (e.g. residence vs university location).
    # Zero tension, zero contradiction. Both facts peacefully co-exist.

    SPATIAL_TEMPORAL_TENSION = "SPATIAL_TEMPORAL_TENSION"
    # Severe logistical/physical tension (e.g. 700km daily drive + 8 AM class).
    # Feasible under extreme burden or missing context; NOT an ontological contradiction.
    # Requires conversational inquiry; ZERO compensatory hallucination (Lock 6).

    WORLD_FACT_DISCREPANCY = "WORLD_FACT_DISCREPANCY"
    # Asserted external fact contradicts canonical World Knowledge (e.g. "USM is in KL").
    # Mutually exclusive factual discrepancy; requires polite conversational inquiry/correction.

    POP_CULTURE_MEME_CROSSING = "POP_CULTURE_MEME_CROSSING"
    # Cross-universe character or franchise mixup (e.g. "昔涟 in Genshin").
    # Subcultural trope or playful slip; NOT a truth collapse. Requires playful banter.

    BIOGRAPHICAL_STATEMENT_TENSION = "BIOGRAPHICAL_STATEMENT_TENSION"
    # Asserted statement tensions with user's own previously asserted statements in dialogue.
    # Requires respectful conversational clarification without accusations.

    ONTOLOGICAL_IMPOSSIBILITY = "ONTOLOGICAL_IMPOSSIBILITY"
    # Biological or physical extreme hyperbole (e.g. "haven't slept in 3 weeks").
    # Discard literal proposition, preserve emotional intensity.


class TensionSeverity(str, Enum):
    """Severity tier of the detected social or spatial discrepancy."""

    NONE = "NONE"
    MILD = "MILD"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SocialRepairInquiryStrategy(str, Enum):
    """Conversational repair inquiry strategy recommended to the response generation layer."""

    NONE = "NONE"
    CASUAL_INQUIRY = "CASUAL_INQUIRY"         # Respectful conversational question asking user for clarification
    PLAYFUL_TEASE = "PLAYFUL_TEASE"           # Banter teasing the extreme distance/schedule or meme slip
    POLITE_CORRECTION = "POLITE_CORRECTION"   # Gentle factual clarification for objective world facts
    EMPATHETIC_CHECK = "EMPATHETIC_CHECK"     # Inquiring about user's exhaustion or well-being


class SocialArbiterContext(BaseModel):
    """
    Immutable input context supplied to the SocialContradictionArbiter.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    user_text: str = Field(..., description="Raw user utterance")
    treatment_decision: EpistemicTreatmentDecision = Field(..., description="Epistemic treatment decision from Phase 15.2")
    known_residence_location: Optional[str] = Field(None, description="Known user residence city/region if recorded")
    known_study_location: Optional[str] = Field(None, description="Known companion/user university location if recorded")
    daily_commute_claimed_km: Optional[int] = Field(None, description="Estimated roundtrip commute distance in kilometers")
    daily_commute_roundtrip_hours: Optional[int] = Field(None, description="Estimated daily roundtrip commute time in hours")
    relationship_teasing_permitted: bool = Field(default=True, description="Whether playful teasing is permissible")
    target_universe: Optional[str] = Field(None, description="Franchise mentioned by user if relevant")
    actual_universe: Optional[str] = Field(None, description="Actual franchise of mentioned character in world knowledge")


class SocialDiscrepancyAnalysis(BaseModel):
    """
    Immutable result of social discrepancy arbitration and conversational repair planning.

    Enforces Lock 6 (Anti-Compensatory Hallucination):
    - `forbidden_compensatory_assumptions` explicitly forbids inventing fake bridge facts.
    - `is_genuine_contradiction` decouples tension from contradiction (Tension != Contradiction != Falsehood).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    discrepancy_type: SocialDiscrepancyType = Field(..., description="Categorical discrepancy classification")
    severity: TensionSeverity = Field(..., description="Severity of logistical or cognitive tension")
    repair_strategy: SocialRepairInquiryStrategy = Field(..., description="Recommended conversational inquiry style")
    is_genuine_contradiction: bool = Field(
        ...,
        description="True ONLY for mutually exclusive ontological contradictions; False for logistical tension or memes.",
    )
    inquiry_prompt_guidance: str = Field(
        ...,
        description="Direct instruction for governed prompt assembly on how to converse naturally without hallucinating.",
    )
    forbidden_compensatory_assumptions: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Explicit list of ungrounded bridge facts the generation layer is STRICTLY FORBIDDEN from inventing.",
    )
    rationale: str = Field(..., description="Deterministic architectural explanation of arbitration decision")
