"""Activity templates and grounding policies for autonomous life simulation.

Adheres to:
- Invariant 14: Selector only instantiates pre-registered templates within reality boundaries.
- Invariant 21: Templates are capabilities, not biographical facts.
- Patch A: Unified sleep hard threshold (min_sleep_pressure_threshold = 0.50).
- Patch D: Generic location archetypes (HOME, PARK, LIBRARY, CAFE) without fabricated geography.
"""

from enum import Enum
from typing import Dict, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field
from app.life.models import LifeActivityType


class ActivityGroundingPolicy(str, Enum):
    """Prerequisite grounding requirement for an activity template."""
    UNIVERSAL = "UNIVERSAL"                    # Biological/routine human needs (sleep, nap, rest, tidy, walk)
    PREFERENCE_GROUNDED = "PREFERENCE_GROUNDED" # Grounded in explicit Character Bible traits/preferences (music, reading)
    CONTEXT_REQUIRED = "CONTEXT_REQUIRED"       # Grounded in persisted contextual reality facts (e.g. student context)
    GOAL_REQUIRED = "GOAL_REQUIRED"             # Strictly requires an active, linked LifeGoal to be eligible


class ActivityTemplate(BaseModel):
    """Immutable template representing an available activity capability."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    template_id: str = Field(..., description="Unique immutable template identifier.")
    activity_type: LifeActivityType = Field(..., description="Canonical activity category.")
    title: str = Field(..., description="Canonical title for instantiated activity.")
    description: str = Field(..., description="Factual description.")
    grounding_policy: ActivityGroundingPolicy = Field(..., description="Prerequisite grounding requirement.")
    default_location: str = Field(default="HOME", description="Canonical location archetype (HOME, PARK, LIBRARY, CAFE).")
    default_duration_minutes: int = Field(default=60, ge=15, le=600, description="Default duration in minutes.")
    profile_id: str = Field(..., description="Canonical physiological profile archetype (RESTORATIVE, SLEEP, etc.).")

    # Needs & Desire Alignment
    primary_desire_alignment: Tuple[str, ...] = Field(default_factory=tuple)
    base_preference: float = Field(default=0.5, ge=0.0, le=1.0)

    # Hard Gating Limits
    required_energy_min: float = Field(default=0.0, ge=0.0, le=1.0)
    max_fatigue_threshold: float = Field(default=1.0, ge=0.0, le=1.0)
    max_stress_threshold: float = Field(default=1.0, ge=0.0, le=1.0)
    min_sleep_pressure_threshold: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Unified hard gating threshold for sleep templates (0.50 for sleep/nap)."
    )
    allowed_start_hours: Tuple[int, ...] = Field(
        default=(),
        description="Allowed local solar hours (0-23) for starting the activity. Activity duration may freely cross midnight."
    )

    # Goal Matching Tags (consumed for matching existing active goals; NEVER creates goals)
    goal_tags: Tuple[str, ...] = Field(default_factory=tuple)


CANONICAL_ACTIVITY_TEMPLATES: Dict[str, ActivityTemplate] = {
    "night_sleep": ActivityTemplate(
        template_id="night_sleep",
        activity_type=LifeActivityType.REST,
        title="Night Sleep",
        description="Full night restorative sleep cycle.",
        grounding_policy=ActivityGroundingPolicy.UNIVERSAL,
        default_location="HOME",
        default_duration_minutes=480,
        profile_id="SLEEP",
        primary_desire_alignment=("REST", "REST_AND_RECHARGE"),
        base_preference=0.85,
        min_sleep_pressure_threshold=0.50,
        allowed_start_hours=(21, 22, 23, 0, 1, 2, 3, 4, 5, 6, 7),
    ),
    "nap": ActivityTemplate(
        template_id="nap",
        activity_type=LifeActivityType.REST,
        title="Afternoon Nap",
        description="Brief restorative afternoon nap.",
        grounding_policy=ActivityGroundingPolicy.UNIVERSAL,
        default_location="HOME",
        default_duration_minutes=45,
        profile_id="SLEEP",
        primary_desire_alignment=("REST", "REST_AND_RECHARGE"),
        base_preference=0.60,
        min_sleep_pressure_threshold=0.50,
        allowed_start_hours=(12, 13, 14, 15, 16),
    ),
    "rest_unwind": ActivityTemplate(
        template_id="rest_unwind",
        activity_type=LifeActivityType.REST,
        title="Quiet Rest & Reflection",
        description="Quiet rest, relaxing and reflecting at home.",
        grounding_policy=ActivityGroundingPolicy.UNIVERSAL,
        default_location="HOME",
        default_duration_minutes=45,
        profile_id="RESTORATIVE",
        primary_desire_alignment=("REST", "REST_AND_RECHARGE", "QUIET_CONTEMPLATION"),
        base_preference=0.70,
    ),
    "tidy_space": ActivityTemplate(
        template_id="tidy_space",
        activity_type=LifeActivityType.OTHER,
        title="Tidy Living Space",
        description="Tidying up personal room and desk space.",
        grounding_policy=ActivityGroundingPolicy.UNIVERSAL,
        default_location="HOME",
        default_duration_minutes=30,
        profile_id="PHYSICAL_LIGHT",
        base_preference=0.50,
        allowed_start_hours=tuple(range(8, 21)),
        goal_tags=("chore", "tidy", "clean"),
    ),
    "walk_outside": ActivityTemplate(
        template_id="walk_outside",
        activity_type=LifeActivityType.OUTING,
        title="Take a Walk",
        description="Casual outdoor walk in the nearby park.",
        grounding_policy=ActivityGroundingPolicy.UNIVERSAL,
        default_location="PARK",
        default_duration_minutes=45,
        profile_id="PHYSICAL_LIGHT",
        base_preference=0.65,
        required_energy_min=0.25,
        max_fatigue_threshold=0.75,
        allowed_start_hours=tuple(range(6, 20)),
        goal_tags=("health", "walk", "exercise", "outdoor"),
    ),
    "light_exercise": ActivityTemplate(
        template_id="light_exercise",
        activity_type=LifeActivityType.EXERCISE,
        title="Light Physical Exercise",
        description="Stretching and light physical routine at home.",
        grounding_policy=ActivityGroundingPolicy.UNIVERSAL,
        default_location="HOME",
        default_duration_minutes=30,
        profile_id="PHYSICAL_MODERATE",
        base_preference=0.60,
        required_energy_min=0.30,
        max_fatigue_threshold=0.65,
        allowed_start_hours=tuple(range(7, 20)),
        goal_tags=("exercise", "fitness", "workout"),
    ),
    "listen_music": ActivityTemplate(
        template_id="listen_music",
        activity_type=LifeActivityType.MUSIC,
        title="Listen to Music",
        description="Listening to favorite records and acoustic pieces.",
        grounding_policy=ActivityGroundingPolicy.PREFERENCE_GROUNDED,
        default_location="HOME",
        default_duration_minutes=45,
        profile_id="RESTORATIVE",
        primary_desire_alignment=("REST", "REST_AND_RECHARGE", "CONNECTION", "CASUAL_ENGAGEMENT"),
        base_preference=0.80,
        goal_tags=("music", "listen"),
    ),
    "read_literature": ActivityTemplate(
        template_id="read_literature",
        activity_type=LifeActivityType.READING,
        title="Read Literature",
        description="Reading contemporary fiction and literature.",
        grounding_policy=ActivityGroundingPolicy.PREFERENCE_GROUNDED,
        default_location="HOME",
        default_duration_minutes=60,
        profile_id="LIGHT_COGNITIVE",
        primary_desire_alignment=("CURIOSITY", "QUIET_CONTEMPLATION"),
        base_preference=0.85,
        allowed_start_hours=tuple(range(8, 24)),
        goal_tags=("reading", "literature", "book", "read"),
    ),
    "practice_instrument": ActivityTemplate(
        template_id="practice_instrument",
        activity_type=LifeActivityType.MUSIC,
        title="Practice Musical Instrument",
        description="Acoustic instrument practice focusing on tone and technique.",
        grounding_policy=ActivityGroundingPolicy.PREFERENCE_GROUNDED,
        default_location="HOME",
        default_duration_minutes=60,
        profile_id="MODERATE_COGNITIVE",
        primary_desire_alignment=("MASTERY", "SOLITARY_FOCUS"),
        base_preference=0.80,
        required_energy_min=0.30,
        max_fatigue_threshold=0.65,
        allowed_start_hours=tuple(range(9, 21)),
        goal_tags=("music", "instrument", "practice", "violin", "guitar", "piano"),
    ),
    "study_coursework": ActivityTemplate(
        template_id="study_coursework",
        activity_type=LifeActivityType.STUDY,
        title="Study & Coursework Review",
        description="Reviewing coursework materials and academic texts.",
        grounding_policy=ActivityGroundingPolicy.CONTEXT_REQUIRED,
        default_location="HOME",
        default_duration_minutes=90,
        profile_id="MODERATE_COGNITIVE",
        primary_desire_alignment=("MASTERY", "SOLITARY_FOCUS", "CURIOSITY"),
        base_preference=0.75,
        required_energy_min=0.35,
        max_fatigue_threshold=0.70,
        allowed_start_hours=tuple(range(8, 22)),
        goal_tags=("study", "academic", "coursework", "learn"),
    ),
    "deep_focus_project": ActivityTemplate(
        template_id="deep_focus_project",
        activity_type=LifeActivityType.PERSONAL_PROJECT,
        title="Work on Personal Project",
        description="Intensive focus work on an active personal project.",
        grounding_policy=ActivityGroundingPolicy.GOAL_REQUIRED,
        default_location="HOME",
        default_duration_minutes=120,
        profile_id="INTENSE_COGNITIVE",
        primary_desire_alignment=("MASTERY", "SOLITARY_FOCUS", "ACHIEVEMENT"),
        base_preference=0.75,
        required_energy_min=0.45,
        max_fatigue_threshold=0.60,
        allowed_start_hours=tuple(range(9, 21)),
        goal_tags=("project", "coding", "personal_project", "writing"),
    ),
}


def get_template_by_id(template_id: str) -> Optional[ActivityTemplate]:
    """Retrieve an activity template by ID."""
    return CANONICAL_ACTIVITY_TEMPLATES.get(template_id)


def get_template_by_title(title: str) -> Optional[ActivityTemplate]:
    """Retrieve an activity template by title matching."""
    norm = title.lower().strip().replace(" ", "_")
    for tmpl in CANONICAL_ACTIVITY_TEMPLATES.values():
        tmpl_norm = tmpl.title.lower().replace(" ", "_")
        if (
            tmpl.template_id == norm
            or tmpl.template_id in norm
            or norm in tmpl.template_id
            or tmpl_norm in norm
            or norm in tmpl_norm
        ):
            return tmpl
    return None

