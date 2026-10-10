"""
deception_models.py — Domain models and enums for cognitive deception verification & confrontation.

Phase: Cross-Turn Deception Verification & Playful Confrontation Closed Loop.
Defines immutable domain structures for:
- Detecting hoaxes, confessions, and cross-turn contradictions.
- Maintaining cognitive grievance state machines (SUSPECTED -> VERIFIED -> CONFRONTED -> RESOLVED).
- Injecting authoritative grievance guidance into CharacterResponseContext.
"""

from __future__ import annotations

from datetime import datetime, timezone
import enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class DeceptionType(str, enum.Enum):
    """Categorization of how the falsehood/trick was manifested."""

    OUTRAGEOUS_CLAIM = "OUTRAGEOUS_CLAIM"
    """Extreme or high-impact claim needing verification (e.g. school closed for a month)."""

    RETRACTED_CONFESSION = "RETRACTED_CONFESSION"
    """User explicitly confesses they were lying / teasing ('其实我之前是骗你的')."""

    CROSS_TURN_CONTRADICTION = "CROSS_TURN_CONTRADICTION"
    """User contradicts earlier claim across turns, exposing a trick (Genshin Xianlian -> Star Rail Xianlian)."""


class GrievanceStage(str, enum.Enum):
    """Lifecycle stage of a cognitive deception grievance."""

    SUSPECTED = "SUSPECTED"
    """Deception suspected, background verification pending."""

    VERIFYING = "VERIFYING"
    """Actively verifying against authoritative knowledge."""

    VERIFIED_DECEPTION = "VERIFIED_DECEPTION"
    """Deception confirmed false; pending playful confrontation in next response (待翻旧账发难)."""

    CONFRONTED = "CONFRONTED"
    """Aevum has called the user out; awaiting user apology/comfort."""

    RECONCILING = "RECONCILING"
    """User has apologized / offered peace; Aevum is softening with playful conditions."""

    RESOLVED = "RESOLVED"
    """Closed loop; reconciled and peaceful."""


class CognitiveGrievanceContext(BaseModel):
    """Immutable context snapshot of an active cognitive grievance for prompt injection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    grievance_id: str = Field(..., description="Unique identifier of the grievance record.")
    claimed_assertion: str = Field(..., description="The original deceptive claim made by the user.")
    verified_truth: Optional[str] = Field(None, description="The authoritative verified truth discovered.")
    deception_type: DeceptionType = Field(..., description="Category of deception.")
    stage: GrievanceStage = Field(..., description="Current lifecycle stage.")
    emotional_tone: str = Field(default="playful_indignant", description="Tone to manifest (e.g. sulky, indignant).")
    confrontation_hint: str = Field(..., description="Specific behavioral guidance for calling the user out.")
