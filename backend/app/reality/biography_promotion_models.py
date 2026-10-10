"""Domain models for Autonomous High-Impact Biography Promotion (Phase 7D.3).

Defines the 14 Hard Promotion Gates (12 Epistemic Eligibility Gates +
2 Execution & Mutation Safety Invariants), Authorization Policy Matrix,
single-use Promotion Authorization Token, and structured promotion records.
"""

from datetime import datetime, timezone
import enum
import hashlib
import json
from typing import Any, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PromotionGateType(str, enum.Enum):
    """The 14 Hard Promotion Gates for Phase 7D.3.
    
    Divided into:
    - 12 Epistemic Eligibility Gates (Gates 1–11, Gate 14)
    - 2 Execution & Mutation Safety Invariants (Gates 12–13)
    """

    # Epistemic Eligibility Gates
    GATE_1_USER_LOCK = "USER_LOCK"
    GATE_2_OBJECTIVE_WORLD_CONSISTENCY = "OBJECTIVE_WORLD_CONSISTENCY"
    GATE_3_TIMELINE = "TIMELINE"
    GATE_4_CAUSALITY = "CAUSALITY"
    GATE_5_GRAPH_CONSISTENCY = "GRAPH_CONSISTENCY"
    GATE_6_CANDIDATE_COMPETITION = "CANDIDATE_COMPETITION"
    GATE_7_EXPLICIT_CHOICE = "EXPLICIT_CHOICE"
    GATE_8_STRUCTURED_PROVENANCE = "STRUCTURED_PROVENANCE"
    GATE_9_NO_CIRCULAR_EVIDENCE = "NO_CIRCULAR_EVIDENCE"
    GATE_10_SEMANTIC_DISTANCE = "SEMANTIC_DISTANCE"
    GATE_11_BIOGRAPHY_CONSTRUCTION_POLICY = "BIOGRAPHY_CONSTRUCTION_POLICY"
    GATE_14_ANTI_SNOWBALL = "ANTI_SNOWBALL"

    # Execution & Mutation Safety Invariants
    GATE_12_IDEMPOTENT_COMMIT_PROTOCOL = "IDEMPOTENT_COMMIT_PROTOCOL"
    GATE_13_STRUCTURED_REVISION_RECORDING = "STRUCTURED_REVISION_RECORDING"


class PromotionGateResult(BaseModel):
    """Structured outcome of a single gate evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    gate: PromotionGateType = Field(..., description="Target gate evaluated.")
    passed: bool = Field(..., description="Whether this gate check succeeded.")
    reason: str = Field(..., description="Structured explanation of result.")
    details: dict[str, Any] = Field(default_factory=dict, description="Diagnostic audit details.")


class PromotionOrigin(str, enum.Enum):
    """Origin authority of an incoming reality claim or hypothesis."""

    USER_CLAIM = "USER_CLAIM"
    SIMULATION_BIOGRAPHY = "SIMULATION_BIOGRAPHY"
    OBJECTIVE_WORLD_FACT = "OBJECTIVE_WORLD_FACT"


class BiographyConstructionPolicy(BaseModel):
    """Versioned policy governing autonomous simulated biography construction.
    
    Deterministic parameters governing what categories are autonomously constructible.
    Zero probability semantics.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_version: str = Field(default="1.0.0", description="Policy version identifier.")
    is_active: bool = Field(default=True, description="Whether policy is active.")
    allowed_autonomous_slots: tuple[str, ...] = Field(
        default=(
            "education.major",
            "education.pathway",
            "education.institution",
            "education.university",
            "education.year",
            "career.aspiration",
            "interests.primary",
            "lifestyle.routine",
            "family.parents_occupation",
            "family.childhood_background",
            "lifestyle.transit",
            "lifestyle.beverage",
            "education.secondary_school",
            "education.music_qualification",
        ),
        description="Slot keys eligible for autonomous biography promotion.",
    )
    forbidden_slots: tuple[str, ...] = Field(
        default=(
            "identity.name",
            "identity.species",
            "identity.birth_year",
            "world.physics",
        ),
        description="Slot keys strictly forbidden from autonomous generation.",
    )
    semantic_distance_heuristic_threshold: float = Field(
        default=0.50,
        ge=0.0,
        le=1.0,
        description="Deterministic heuristic threshold (v1 policy constant; NOT a probability).",
    )
    min_viable_candidates: int = Field(default=2, ge=2, description="Minimum competing alternatives required.")
    min_choice_margin: float = Field(default=0.02, ge=0.0, description="Minimum choice score delta.")


class PromotionEligibilityResult(BaseModel):
    """Outcome of evaluating all 14 Hard Gates against a candidate hypothesis and choice."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str = Field(..., description="Target candidate hypothesis ID.")
    slot_name: str = Field(..., description="Attribute slot evaluated.")
    is_eligible: bool = Field(..., description="True if and only if ALL gates passed.")
    passed_gates: tuple[PromotionGateType, ...] = Field(default_factory=tuple)
    failed_gates: tuple[PromotionGateType, ...] = Field(default_factory=tuple)
    gate_results: dict[str, PromotionGateResult] = Field(default_factory=dict)
    rationale: str = Field(default="", description="Machine summary of eligibility.")


class PromotionAuthorizationToken(BaseModel):
    """Single-use authorization token required by CharacterCoreService.set_fact.
    
    Structural Call-Site Enforcement:
    CharacterCoreService.set_fact rejects allow_canonical_reconciliation=True
    unless presented with a valid PromotionAuthorizationToken minted exclusively
    by BiographyPromotionService.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    token_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    character_id: str = Field(..., description="Bound character ID.")
    slot_name: str = Field(..., description="Bound fact key.")
    value_hash: str = Field(..., description="SHA-256 hash of normalized proposed value.")
    candidate_id: str = Field(..., description="Bound candidate hypothesis ID.")
    choice_decision_id: str = Field(..., description="Bound choice decision ID.")
    policy_version: str = Field(default="1.0.0")
    minted_at: datetime = Field(default_factory=_utc_now)

    @classmethod
    def create(
        cls,
        character_id: str,
        slot_name: str,
        value: Any,
        candidate_id: str,
        choice_decision_id: str,
        policy_version: str = "1.0.0",
    ) -> "PromotionAuthorizationToken":
        norm_val_str = json.dumps(value, sort_keys=True)
        v_hash = hashlib.sha256(norm_val_str.encode("utf-8")).hexdigest()
        return cls(
            character_id=character_id,
            slot_name=slot_name,
            value_hash=v_hash,
            candidate_id=candidate_id,
            choice_decision_id=choice_decision_id,
            policy_version=policy_version,
        )

    def verify(self, character_id: str, fact_key: str, value: Any) -> bool:
        """Verify that token matches the exact proposed mutation payload."""
        if self.character_id != character_id or self.slot_name != fact_key:
            return False
        norm_val_str = json.dumps(value, sort_keys=True)
        v_hash = hashlib.sha256(norm_val_str.encode("utf-8")).hexdigest()
        return self.value_hash == v_hash


class PromotionAuthorizationResult(BaseModel):
    """Outcome of origin policy and gate check governing promotion execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str = Field(..., description="Candidate hypothesis ID.")
    slot_name: str = Field(..., description="Attribute slot.")
    is_authorized: bool = Field(..., description="Whether canonical promotion is authorized.")
    authorization_code: str = Field(..., description="Canonical authorization code.")
    policy_version: str = Field(default="1.0.0")
    eligibility: PromotionEligibilityResult = Field(..., description="Full gate results.")
    token: Optional[PromotionAuthorizationToken] = Field(
        default=None,
        description="Single-use mutation token issued ONLY upon successful authorization.",
    )
    is_idempotent_replay: bool = Field(
        default=False,
        description="True if fact was already promoted and replayed safely.",
    )


class BiographyPromotionRecord(BaseModel):
    """Persistent structured audit record of a completed autonomous biography promotion."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    promotion_id: str = Field(..., description="Unique promotion identifier.")
    character_id: str = Field(default="aevum")
    slot_name: str = Field(...)
    candidate_id: str = Field(...)
    choice_decision_id: str = Field(...)
    promoted_value: Any = Field(...)
    policy_version: str = Field(default="1.0.0")
    decision_model_version: str = Field(default="1.0.0")
    previous_canonical_state: Optional[Any] = Field(default=None)
    new_canonical_state: Any = Field(...)
    gates_passed: tuple[str, ...] = Field(default_factory=tuple)
    provenance_references: tuple[str, ...] = Field(default_factory=tuple)
    authorization_code: str = Field(...)
    is_idempotent_replay: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_utc_now)
