"""Provider-independent application state models for Aevum Core."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ApplicationState(BaseModel):
    """Provider-independent representation of canonical application state.

    This model represents the minimal foundation for application-owned state.
    It contains strictly lifecycle and concurrency metadata (id, version, updated_at).
    No domain-specific character, emotion, relationship, or memory fields are
    present; those will be owned by their respective future subsystems.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(
        default="canonical",
        description="Stable identifier for canonical application state.",
    )
    version: int = Field(
        default=1,
        ge=1,
        description="Monotonically increasing version counter for optimistic concurrency.",
    )
    updated_at: datetime = Field(
        description="UTC timestamp of the most recent state update.",
    )
