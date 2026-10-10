"""Phase 19.3 — Contextual Resonance & Cognitive Attention Contracts.

Defines the pure immutable data transfer objects and enums governing
contextual resonance, accessibility, cognitive attention, and the agency of silence.

Constitutional Locks:
- The 7-Stage Non-Cascading Cognitive Chain:
    Encounter -> Resonance -> Accessibility/Recall -> Attention -> Expression Disposition -> Mention/Silence -> Action
    Each stage is strictly decoupled and can halt independently without implicit cascade.
- The Three Distinct Decisions:
    1. Resonance: "Does this reality event semantically relate to the thread?"
    2. Attention: "Does Aevum consciously attend to this relation right now?" (Preference ≠ Attention)
    3. Expression: "Does Aevum choose to voice this, or remain silent?" (Attention ≠ Mention)
- Silence as First-Class Agency:
    "想到了，但没说" (Recalled, attended, but consciously remained silent).
- Internal Audit Isolation:
    ResonanceEvaluation is strictly internal audit metadata; it never leaks into
    dialogue prompts or mandates self-disclosure. Silence means simply not saying it.
- Permanent Note A: Zero pseudo-probability float scoring fields.
"""


from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ResonanceDegree(str, Enum):
    """Discrete categorical tier of contextual resonance between an event and a thread.
    
    Zero float scores. Evaluated through semantic correspondence.
    """
    NONE = "NONE"                                  # No contextual or narrative relation
    TANGENTIAL = "TANGENTIAL"                      # Remote, incidental, or peripheral association
    PLAUSIBLE = "PLAUSIBLE"                        # Meaningful contextual alignment without explicit identity
    DIRECT_CORRESPONDENCE = "DIRECT_CORRESPONDENCE"  # Direct semantic fulfillment or confrontation of the unresolved thread


class AttentionDecision(str, Enum):
    """Aevum's conscious attention allocation toward a resonant thread.
    
    Recall ≠ Attention: A thread may resonate and be accessible, but Aevum
    can consciously choose to disregard it or keep it in peripheral awareness.
    """
    DISREGARD_FOR_NOW = "DISREGARD_FOR_NOW"      # Notice fleetingly, but choose not to allocate cognitive attention
    PERIPHERAL_AWARENESS = "PERIPHERAL_AWARENESS"  # Retain as gentle background context without focal centering
    FOCAL_ATTENTION = "FOCAL_ATTENTION"            # Actively bring the thread to focal conscious awareness


class ExpressionDisposition(str, Enum):
    """Aevum's verbalization choice regarding an attended prospective thread.
    
    Attention ≠ Mention: Even when focusing on a thread, Aevum possesses
    the complete agency to remain silent.
    """
    REMAIN_SILENT = "REMAIN_SILENT"                      # Consciously choose not to voice or mention ("想到了，但没说")
    ALLOW_SPONTANEOUS_MENTION = "ALLOW_SPONTANEOUS_MENTION"  # Permit natural conversational surfacing if dialogue naturally drifts there
    RESERVE_FOR_LATER = "RESERVE_FOR_LATER"              # Hold in heart for a more appropriate future moment


class RealityEventContext(BaseModel):
    """Contextual descriptor of a reality event being evaluated for thread resonance."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str = Field(..., min_length=1, description="Unique identifier of the reality event.")
    event_summary: str = Field(..., min_length=1, max_length=500, description="Semantic description of what occurred.")
    occurred_at: datetime = Field(..., description="Authoritative timestamp when the event occurred.")
    turn_id: Optional[str] = Field(default=None, description="Dialogue turn ID if origin is conversational.")
    is_user_initiated: bool = Field(default=True, description="Whether the event arose from user input vs autonomous life.")


class ResonanceEvaluation(BaseModel):
    """Immutable audit DTO recording the complete 3-stage resonance & silence evaluation.
    
    Enforces the cognitive separation chain:
    Reality Event -> Resonance -> Accessibility -> Attention -> Expression/Silence.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_id: str = Field(..., min_length=1, description="Canonical identifier of this evaluation.")
    thread_id: str = Field(..., min_length=1, description="Identifier of the evaluated thread.")
    event_id: str = Field(..., min_length=1, description="Identifier of the reality event.")
    resonance_degree: ResonanceDegree = Field(..., description="Evaluated degree of contextual resonance.")
    attention_decision: AttentionDecision = Field(..., description="Whether Aevum allocates cognitive attention.")
    expression_disposition: ExpressionDisposition = Field(..., description="Whether Aevum chooses to voice or remain silent.")
    silence_rationale: Optional[str] = Field(
        default=None,
        max_length=500,
        description=(
            "Internal audit rationale when Aevum chooses REMAIN_SILENT or DISREGARD. "
            "Strictly internal; barred from dialogue context or mandatory self-disclosure."
        ),
    )
    evaluated_at: datetime = Field(..., description="Authoritative timestamp when evaluation occurred.")

