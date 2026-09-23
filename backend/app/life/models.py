from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class LifeActivityType(str, Enum):
    STUDY = "STUDY"
    CLASS = "CLASS"
    MUSIC = "MUSIC"
    READING = "READING"
    GAME = "GAME"
    ANIME = "ANIME"
    MOVIE = "MOVIE"
    EXERCISE = "EXERCISE"
    COOKING = "COOKING"
    SOCIAL = "SOCIAL"
    OUTING = "OUTING"
    REST = "REST"
    PERSONAL_PROJECT = "PERSONAL_PROJECT"
    OTHER = "OTHER"

class LifeActivityStatus(str, Enum):
    ONGOING = "ONGOING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class LifePlanStatus(str, Enum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class LifeEventType(str, Enum):
    ACTIVITY_COMPLETED = "ACTIVITY_COMPLETED"
    PLAN_COMPLETED = "PLAN_COMPLETED"
    PLAN_CANCELLED = "PLAN_CANCELLED"
    SOCIAL_EVENT = "SOCIAL_EVENT"
    PERSONAL_DISCOVERY = "PERSONAL_DISCOVERY"
    SUCCESS = "SUCCESS"
    SETBACK = "SETBACK"
    ROUTINE = "ROUTINE"
    OTHER = "OTHER"

class LifeGoalStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"
    ABANDONED = "ABANDONED"

class LifeState(BaseModel):
    """Authoritative representation of what Aevum is currently doing."""
    id: str = Field(default="aevum")
    character_id: str = Field(default="aevum")
    current_activity: str
    current_location: str
    status: str = Field(default="ACTIVE")
    version: int = Field(default=1)
    updated_at: datetime

class LifeActivity(BaseModel):
    """A discrete activity in the character's life."""
    id: str
    plan_id: Optional[str] = None
    goal_id: Optional[str] = None
    character_id: str
    activity_type: LifeActivityType
    title: str
    description: str
    location: str
    status: LifeActivityStatus
    started_at: datetime
    planned_end_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    created_at: datetime

class LifePlan(BaseModel):
    """A planned action or intention."""
    id: str
    plan_id: Optional[str] = None
    goal_id: Optional[str] = None
    character_id: str
    title: str
    description: str
    planned_start: Optional[datetime] = None
    planned_end: Optional[datetime] = None
    status: LifePlanStatus
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    created_at: datetime
    updated_at: datetime

class LifeEvent(BaseModel):
    """A factual event that occurred in the character's life."""
    id: str
    plan_id: Optional[str] = None
    character_id: str
    event_type: LifeEventType
    title: str
    description: str
    occurred_at: datetime
    significance: float = Field(default=0.5, ge=0.0, le=1.0)
    idempotency_key: Optional[str] = Field(default=None, description="Deterministic deduplication key.")
    created_at: datetime

class LifeGoal(BaseModel):
    """A personal goal."""
    id: str
    plan_id: Optional[str] = None
    character_id: str
    title: str
    description: str
    status: LifeGoalStatus
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    progress_per_completion: float = Field(
        ..., ge=0.01, le=1.0,
        description="Factual progress increment awarded per completed linked activity."
    )
    created_at: datetime
    updated_at: datetime
