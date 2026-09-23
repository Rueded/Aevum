"""Domain models for character physiological and cognitive wear states (Phase 7C.2).

Guarantees:
- Enforces Invariant 16: Typed domain models for StateDynamicsEngine.
- Decouples energy (vitality), fatigue (wear), sleep pressure (wake cost), and stress.
- Formally defines 7 canonical ActivityPhysiologicalProfile archetypes.
- Structured StateTransitionRecord audit provenance with deterministic rule_id.
"""

from datetime import datetime, timezone
from enum import Enum
import math
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PhysiologicalBand(str, Enum):
    """Derived qualitative representation of physical/mental state (Invariant 18)."""
    REFRESHED = "REFRESHED"
    STEADY = "STEADY"
    DROWSY = "DROWSY"
    FATIGUED = "FATIGUED"
    OVERLOADED = "OVERLOADED"


class StateTransitionTrigger(str, Enum):
    """Trigger causing a physiological state evaluation."""
    TIME_ELAPSED = "TIME_ELAPSED"
    ACTIVITY_INTERVAL = "ACTIVITY_INTERVAL"
    SLEEP_CYCLE = "SLEEP_CYCLE"
    RECONCILIATION_OFFLINE_GAP = "RECONCILIATION_OFFLINE_GAP"
    ACUTE_EVENT = "ACUTE_EVENT"


def _validate_unit_float(v: float, field_name: str) -> float:
    """Ensure float is finite and clamped between 0.0 and 1.0."""
    val = float(v)
    if math.isnan(val) or math.isinf(val):
        raise ValueError(f"{field_name} must be a finite number.")
    return max(0.0, min(1.0, val))


class ActivityPhysiologicalProfile(BaseModel):
    """Hourly physiological modification rates for an activity archetype."""
    model_config = ConfigDict(frozen=True)

    profile_id: str
    energy_rate: float = Field(..., description="Energy change per hour (negative=drain, positive=gain)")
    fatigue_rate: float = Field(..., description="Fatigue accumulation rate per hour")
    stress_rate: float = Field(..., description="Stress accumulation rate per hour")
    sleep_pressure_rate: float = Field(..., description="Sleep pressure accumulation rate per hour")
    recovery_rate: float = Field(default=0.0, description="Passive recovery pull towards baseline")


# The 7 Canonical Activity Profiles
CANONICAL_ACTIVITY_PROFILES: Dict[str, ActivityPhysiologicalProfile] = {
    "RESTORATIVE": ActivityPhysiologicalProfile(
        profile_id="RESTORATIVE",
        energy_rate=0.06,
        fatigue_rate=-0.08,
        stress_rate=-0.12,
        sleep_pressure_rate=0.04,
        recovery_rate=0.10,
    ),
    "LIGHT_COGNITIVE": ActivityPhysiologicalProfile(
        profile_id="LIGHT_COGNITIVE",
        energy_rate=-0.05,
        fatigue_rate=0.06,
        stress_rate=-0.02,
        sleep_pressure_rate=0.05,
        recovery_rate=0.05,
    ),
    "MODERATE_COGNITIVE": ActivityPhysiologicalProfile(
        profile_id="MODERATE_COGNITIVE",
        energy_rate=-0.12,
        fatigue_rate=0.14,
        stress_rate=0.04,
        sleep_pressure_rate=0.06,
        recovery_rate=0.0,
    ),
    "INTENSE_COGNITIVE": ActivityPhysiologicalProfile(
        profile_id="INTENSE_COGNITIVE",
        energy_rate=-0.22,
        fatigue_rate=0.25,
        stress_rate=0.15,
        sleep_pressure_rate=0.07,
        recovery_rate=0.0,
    ),
    "PHYSICAL_LIGHT": ActivityPhysiologicalProfile(
        profile_id="PHYSICAL_LIGHT",
        energy_rate=-0.08,
        fatigue_rate=0.10,
        stress_rate=-0.05,
        sleep_pressure_rate=0.05,
        recovery_rate=0.05,
    ),
    "PHYSICAL_MODERATE": ActivityPhysiologicalProfile(
        profile_id="PHYSICAL_MODERATE",
        energy_rate=-0.20,
        fatigue_rate=0.22,
        stress_rate=-0.08,
        sleep_pressure_rate=0.06,
        recovery_rate=0.0,
    ),
    "SLEEP": ActivityPhysiologicalProfile(
        profile_id="SLEEP",
        energy_rate=0.12,
        fatigue_rate=-0.20,
        stress_rate=-0.15,
        sleep_pressure_rate=-0.25,
        recovery_rate=0.20,
    ),
}


def map_activity_to_profile(activity_type_str: str, title: Optional[str] = None) -> ActivityPhysiologicalProfile:
    """Map a LifeActivityType or activity title string to its authoritative profile archetype."""
    combined = f"{activity_type_str} {title or ''}".upper()
    if "SLEEP" in combined:
        return CANONICAL_ACTIVITY_PROFILES["SLEEP"]
    if any(k in combined for k in ("REST", "RESTORATIVE", "NAP", "RECHARGE")):
        return CANONICAL_ACTIVITY_PROFILES["RESTORATIVE"]
    if any(k in combined for k in ("EXAM", "DEADLINE", "INTENSE", "CRUNCH")):
        return CANONICAL_ACTIVITY_PROFILES["INTENSE_COGNITIVE"]
    if any(k in combined for k in ("STUDY", "CLASS", "SEMINAR", "RESEARCH", "HOMEWORK")):
        return CANONICAL_ACTIVITY_PROFILES["MODERATE_COGNITIVE"]
    if any(k in combined for k in ("EXERCISE", "WORKOUT", "RUN", "JOG", "GYM")):
        return CANONICAL_ACTIVITY_PROFILES["PHYSICAL_MODERATE"]
    if any(k in combined for k in ("OUTING", "WALK", "WALKING", "CHORES", "CLEAN")):
        return CANONICAL_ACTIVITY_PROFILES["PHYSICAL_LIGHT"]
    if any(k in combined for k in ("MUSIC", "PRACTICE", "VIOLIN", "GUITAR", "PIANO", "PROJECT")):
        return CANONICAL_ACTIVITY_PROFILES["MODERATE_COGNITIVE"]
    if any(k in combined for k in ("READING", "ANIME", "MOVIE", "GAME", "SOCIAL", "COOKING")):
        return CANONICAL_ACTIVITY_PROFILES["LIGHT_COGNITIVE"]
    return CANONICAL_ACTIVITY_PROFILES["LIGHT_COGNITIVE"]


class CharacterPhysiologicalState(BaseModel):
    """Immutable representation of character physical and mental energy wear."""
    model_config = ConfigDict(frozen=True)

    energy: float = Field(default=0.75, description="Available physical and cognitive vitality on [0.0, 1.0]")
    fatigue: float = Field(default=0.15, description="Wear and tear accumulated from exertion on [0.0, 1.0]")
    stress: float = Field(default=0.15, description="Tension from cognitive/environmental load on [0.0, 1.0]")
    sleep_pressure: float = Field(default=0.20, description="Homeostatic sleep drive from wakefulness on [0.0, 1.0]")
    qualitative_band: PhysiologicalBand = Field(
        default=PhysiologicalBand.STEADY,
        description="One-way derived presentation band for qualitative context"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC instant of last state calculation"
    )

    @field_validator("energy", "fatigue", "stress", "sleep_pressure", mode="before")
    @classmethod
    def validate_normalized(cls, v: Any, info: Any) -> float:
        return _validate_unit_float(float(v), info.field_name)


class StateTransitionRecord(BaseModel):
    """Immutable audit record for explainable physiological state transitions."""
    model_config = ConfigDict(frozen=True)

    id: str
    character_id: str
    timestamp: datetime
    trigger_type: StateTransitionTrigger
    activity_id: Optional[str] = None
    time_interval_seconds: float = 0.0
    before_state: Dict[str, float]
    after_state: Dict[str, float]
    delta: Dict[str, float]
    circadian_modifier: float = 0.0
    rule_id: str
    reason: str
