"""Reality History and Version Revision models (Phase 7B.3).

Maintains versioned revisions of facts over time when life circumstances change
or facts evolve, without silently deleting or wiping historical ground truth.
"""

from datetime import datetime, timezone
import uuid
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RealityRevisionRecord(BaseModel):
    """Immutable domain model representing a temporal revision of a reality fact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique revision ID.")
    character_id: str = Field(default="aevum", description="Target character identifier.")
    fact_key: str = Field(..., description="Dot-notated fact key, e.g. 'identity.age', 'location.residence'.")
    value: Any = Field(..., description="The value of the fact during this revision window.")
    effective_from: Optional[str] = Field(default=None, description="ISO timestamp or date when this fact became true.")
    effective_until: Optional[str] = Field(default=None, description="ISO timestamp or date when superseded or expired.")
    supersedes_id: Optional[str] = Field(default=None, description="ID of prior revision superseded by this one.")
    superseded_by: Optional[str] = Field(default=None, description="ID of subsequent revision replacing this one.")
    created_at: datetime = Field(default_factory=_utc_now, description="UTC creation timestamp.")

    @field_validator("id", "character_id", "fact_key")
    @classmethod
    def validate_non_empty(cls, v: str, info: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name} must not be empty or whitespace.")
        return v.strip()

    @property
    def is_current(self) -> bool:
        """A revision is current if it has not been superseded or expired."""
        return self.superseded_by is None and self.effective_until is None
