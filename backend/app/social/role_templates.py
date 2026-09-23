"""Role template catalog and SocialOpportunityProfile for Aevum Core (Phase 7C.4).

Enforces:
- Invariant 15.1: Role templates are blueprints for potential encounters, NOT existing canonical relationships.
- Invariant 15.4: Contextual social opportunity and hard gating against private spaces and exhausted states.
- Lock-in Item 4: SocialOpportunityProfile affordance architecture.
"""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.social.models import SocialDynamics, SocialOpportunityLevel


class SocialRoleCategory(str, Enum):
    """Categorical classification of social roles in Aevum's environment."""
    ACADEMIC = "ACADEMIC"
    CAMPUS_SERVICE = "CAMPUS_SERVICE"
    CREATIVE_PEER = "CREATIVE_PEER"
    COMMUNITY = "COMMUNITY"


class SocialRoleTemplate(BaseModel):
    """Immutable blueprint for an archetypal social role in the simulation.

    Enforces Invariant 15.1: Template exists != Aevum knows them.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    role_id: str
    title: str
    category: SocialRoleCategory
    allowed_locations: tuple[str, ...]
    allowed_activities: tuple[str, ...]
    baseline_dynamics: SocialDynamics
    promotion_outcome: str
    min_encounters_for_promotion: int = Field(default=3, ge=1)
    default_relationship_label: str


ALLOWED_ROLE_TEMPLATES: dict[str, SocialRoleTemplate] = {
    "course_classmate": SocialRoleTemplate(
        role_id="course_classmate",
        title="Course Classmate",
        category=SocialRoleCategory.ACADEMIC,
        allowed_locations=("LIBRARY",),
        allowed_activities=("study_coursework", "deep_focus_project"),
        baseline_dynamics=SocialDynamics(familiarity=0.05, comfort=0.15, respect=0.50, trust=0.10),
        promotion_outcome="STUDY_PEER",
        min_encounters_for_promotion=3,
        default_relationship_label="Classmate",
    ),
    "academic_advisor": SocialRoleTemplate(
        role_id="academic_advisor",
        title="Academic Advisor / Instructor",
        category=SocialRoleCategory.ACADEMIC,
        allowed_locations=("LIBRARY",),
        allowed_activities=("study_coursework", "deep_focus_project"),
        baseline_dynamics=SocialDynamics(familiarity=0.05, comfort=0.10, respect=0.75, trust=0.20),
        promotion_outcome="KNOWN_ACADEMIC_CONTACT",
        min_encounters_for_promotion=2,
        default_relationship_label="Academic Advisor",
    ),
    "campus_service_staff": SocialRoleTemplate(
        role_id="campus_service_staff",
        title="Campus Service Staff",
        category=SocialRoleCategory.CAMPUS_SERVICE,
        allowed_locations=("CAFE", "LIBRARY"),
        allowed_activities=("rest_unwind", "study_coursework", "read_literature"),
        baseline_dynamics=SocialDynamics(familiarity=0.05, comfort=0.20, respect=0.50, trust=0.05),
        promotion_outcome="RECURRING_FAMILIAR_PRESENCE",
        min_encounters_for_promotion=4,
        default_relationship_label="Service Staff",
    ),
    "creative_peer": SocialRoleTemplate(
        role_id="creative_peer",
        title="Creative / Music Peer",
        category=SocialRoleCategory.CREATIVE_PEER,
        allowed_locations=("PARK", "LIBRARY"),
        allowed_activities=("practice_instrument", "listen_music", "read_literature"),
        baseline_dynamics=SocialDynamics(familiarity=0.05, comfort=0.15, respect=0.60, trust=0.10),
        promotion_outcome="CREATIVE_PEER",
        min_encounters_for_promotion=3,
        default_relationship_label="Fellow Musician",
    ),
    "community_acquaintance": SocialRoleTemplate(
        role_id="community_acquaintance",
        title="Community Acquaintance",
        category=SocialRoleCategory.COMMUNITY,
        allowed_locations=("PARK",),
        allowed_activities=("walk_outside", "light_exercise"),
        baseline_dynamics=SocialDynamics(familiarity=0.05, comfort=0.10, respect=0.50, trust=0.05),
        promotion_outcome="CASUAL_ACQUAINTANCE",
        min_encounters_for_promotion=4,
        default_relationship_label="Park Acquaintance",
    ),
}


def get_role_template(role_id: str) -> Optional[SocialRoleTemplate]:
    """Retrieve an allowed role template by role_id."""
    return ALLOWED_ROLE_TEMPLATES.get(role_id)


def get_eligible_role_templates(location: str, activity_id: str) -> tuple[SocialRoleTemplate, ...]:
    """Find all templates eligible for a given location and activity archetype."""
    norm_loc = location.upper().strip()
    norm_act = activity_id.lower().strip().replace(" ", "_")
    return tuple(
        tmpl for tmpl in ALLOWED_ROLE_TEMPLATES.values()
        if norm_loc in tmpl.allowed_locations and any(act in norm_act or norm_act in act for act in tmpl.allowed_activities)
    )


class SocialOpportunityProfile:
    """Affordance architecture evaluating contextual social opportunity (Lock-in Item 4).

    Maps (location, activity, character physiological state) -> SocialOpportunityLevel.
    Enforces Invariant 15.4: Private spaces and exhausted states strictly yield NONE.
    """

    @classmethod
    def evaluate(
        cls,
        location: str,
        activity_id: str,
        physiological_state: Optional[Any] = None,
        desire_state: Optional[Any] = None,
    ) -> SocialOpportunityLevel:
        """Pure, deterministic evaluation of social opportunity."""
        norm_loc = location.upper().strip()
        norm_act = activity_id.lower().strip().replace(" ", "_")

        # 1. Hard Gating: Private space (HOME) strictly yields NONE (Invariant 15.4)
        if norm_loc == "HOME":
            return SocialOpportunityLevel.NONE

        # 2. Hard Gating: Private/solo recovery activities strictly yield NONE
        if norm_act in ("night_sleep", "nap", "tidy_space"):
            return SocialOpportunityLevel.NONE

        # 3. Hard Gating: Physiological exhaustion or overwhelming solitude need
        if physiological_state is not None:
            fatigue = getattr(physiological_state, "fatigue", 0.0)
            if fatigue >= 0.85:
                return SocialOpportunityLevel.NONE

        if desire_state is not None:
            solitude = getattr(desire_state, "solitude_need", 0.0)
            if solitude >= 0.80:
                return SocialOpportunityLevel.NONE

        # 4. Contextual Affordance Mapping
        if norm_loc == "LIBRARY":
            if norm_act in ("study_coursework", "deep_focus_project"):
                return SocialOpportunityLevel.HIGH
            if norm_act == "read_literature":
                return SocialOpportunityLevel.LOW

        if norm_loc == "CAFE":
            if norm_act in ("rest_unwind", "read_literature"):
                return SocialOpportunityLevel.MEDIUM
            if norm_act == "study_coursework":
                return SocialOpportunityLevel.MEDIUM

        if norm_loc == "PARK":
            if norm_act in ("walk_outside", "practice_instrument", "light_exercise"):
                return SocialOpportunityLevel.MEDIUM
            if norm_act == "listen_music":
                return SocialOpportunityLevel.LOW

        # Fallback for unrecognized public venue / activity pair
        eligible = get_eligible_role_templates(norm_loc, norm_act)
        return SocialOpportunityLevel.LOW if eligible else SocialOpportunityLevel.NONE
