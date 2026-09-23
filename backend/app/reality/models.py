"""Domain models and enums for Aevum Reality Ledger & Character Core."""

from datetime import datetime, timezone
import enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from app.reality.registry import FactKeyRegistry


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FactAuthority(str, enum.Enum):
    """Authority and modification precedence of a reality fact."""

    USER_LOCKED = "USER_LOCKED"
    USER_CONFIGURED = "USER_CONFIGURED"
    AEVUM_CANONICAL = "AEVUM_CANONICAL"
    SYSTEM_BASELINE = "SYSTEM_BASELINE"


class FactStatus(str, enum.Enum):
    """Lifecycle and verification state of a reality fact."""

    CANONICAL = "CANONICAL"
    CANDIDATE = "CANDIDATE"
    DISPUTED = "DISPUTED"
    FALSIFIED = "FALSIFIED"
    EPHEMERAL = "EPHEMERAL"


class FactSource(str, enum.Enum):
    """Historical provenance of a reality fact."""

    USER_CONFIGURED = "USER_CONFIGURED"
    AEVUM_INFERRED = "AEVUM_INFERRED"
    CONVERSATION = "CONVERSATION"
    SYSTEM_BASELINE = "SYSTEM_BASELINE"


class LedgerTier(str, enum.Enum):
    """Visual and operational categorization tier in Reality Ledger."""

    USER_EDITABLE = "USER_EDITABLE"      # Green tier
    AEVUM_EMERGENT = "AEVUM_EMERGENT"    # Yellow tier
    SYSTEM_INTEGRITY = "SYSTEM_INTEGRITY" # Red tier


class CoreFactItem(BaseModel):
    """Immutable domain representation of an atomic Character Core fact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(..., description="Unique dot-notated fact key, e.g. 'identity.name'")
    category: str = Field(..., description="Domain category, e.g. 'identity', 'education'")
    value: Any = Field(..., description="Validated domain fact value")
    source: FactSource = Field(..., description="Original historical provenance")
    authority: FactAuthority = Field(..., description="Modification precedence level")
    status: FactStatus = Field(default=FactStatus.CANONICAL, description="Current verification lifecycle status")
    epistemic_confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Epistemic certainty [0.0, 1.0]")
    locked: bool = Field(default=False, description="Whether fact is strictly locked against LLM drift")
    explanation: Optional[str] = Field(default=None, description="Optional rationale or causal bridge description")
    created_at: datetime = Field(default_factory=_utc_now, description="UTC creation timestamp")
    updated_at: datetime = Field(default_factory=_utc_now, description="UTC last update timestamp")

    @field_validator("key", "category")
    @classmethod
    def validate_non_empty_key(cls, v: str, info: ValidationInfo) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name} must not be empty or whitespace.")
        return v.strip()

    @field_validator("value")
    @classmethod
    def validate_value_with_registry(cls, v: Any, info: ValidationInfo) -> Any:
        key = info.data.get("key")
        if key:
            return FactKeyRegistry.validate(key, v)
        return v

    @model_validator(mode="after")
    def validate_lock_invariant(self) -> "CoreFactItem":
        """Enforce the strict lock invariant: locked == True <==> authority == USER_LOCKED."""
        if self.locked and self.authority != FactAuthority.USER_LOCKED:
            raise ValueError(
                f"Fact '{self.key}' with locked=True must have authority=USER_LOCKED, got authority={self.authority.value}"
            )
        if not self.locked and self.authority == FactAuthority.USER_LOCKED:
            raise ValueError(
                f"Fact '{self.key}' with authority=USER_LOCKED must have locked=True"
            )
        return self

    @property
    def is_locked(self) -> bool:
        """Convenience check for user lock."""
        return self.locked

    @property
    def tier(self) -> LedgerTier:
        """Map fact to Reality Ledger visualization tier."""
        if self.authority == FactAuthority.SYSTEM_BASELINE:
            return LedgerTier.SYSTEM_INTEGRITY
        if self.source == FactSource.USER_CONFIGURED or self.authority in (FactAuthority.USER_CONFIGURED, FactAuthority.USER_LOCKED):
            return LedgerTier.USER_EDITABLE
        return LedgerTier.AEVUM_EMERGENT
