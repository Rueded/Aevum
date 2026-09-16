"""Relationship context models for Aevum Core.

Represents semantic, qualitative interpretations of RelationshipState for LLM grounding.
Strictly excludes raw floating-point metrics, levels, XP, or romance gamification.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_FIELD_LENGTH: int = 2000


class RelationshipContext(BaseModel):
    """Immutable, semantic representation of Aevum's relationship dynamics with the user.

    Designed for injection into LLMContext.system_instructions.
    Contains strictly qualitative descriptions and interaction guidance.
    Exposes ZERO numerical metrics (trust: float, affection: float, etc.).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    relationship_summary: str = Field(
        ...,
        description="Holistic qualitative summary of the relationship state.",
    )
    familiarity_summary: str = Field(
        ...,
        description="Semantic description of mutual familiarity.",
    )
    trust_summary: str = Field(
        ...,
        description="Semantic description of mutual trust.",
    )
    comfort_summary: str = Field(
        ...,
        description="Semantic description of conversational comfort.",
    )
    affection_summary: str = Field(
        ...,
        description="Semantic description of personal fondness (strictly non-romantic).",
    )
    attachment_summary: str = Field(
        ...,
        description="Semantic description of emotional significance.",
    )
    respect_summary: str = Field(
        ...,
        description="Semantic description of mutual respect.",
    )
    interaction_guidance: str = Field(
        ...,
        description="Actionable behavioral guidelines for the LLM based on current relationship.",
    )

    @field_validator(
        "relationship_summary",
        "familiarity_summary",
        "trust_summary",
        "comfort_summary",
        "affection_summary",
        "attachment_summary",
        "respect_summary",
        "interaction_guidance",
    )
    @classmethod
    def validate_bounded_text(cls, v: str, info) -> str:
        """Ensure semantic text is bounded, non-empty, and free of raw metric syntax."""
        stripped = v.strip()
        if not stripped:
            raise ValueError(f"Field '{info.field_name}' must not be empty.")
        if len(stripped) > MAX_FIELD_LENGTH:
            raise ValueError(
                f"Field '{info.field_name}' exceeds maximum length of {MAX_FIELD_LENGTH} characters."
            )
        return stripped
