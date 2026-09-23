"""Social World & Emergent Life module for Aevum Core (Phase 7C.4)."""

from app.social.models import (
    IdentityState,
    SocialOpportunityLevel,
    EncounterType,
    InteractionDepth,
    SocialContactStatus,
    SocialDynamics,
    SocialCandidate,
    NPCEntity,
    NPCFact,
)
from app.social.role_templates import (
    SocialRoleCategory,
    SocialRoleTemplate,
    ALLOWED_ROLE_TEMPLATES,
    SocialOpportunityProfile,
    get_role_template,
)

__all__ = [
    "IdentityState",
    "SocialOpportunityLevel",
    "EncounterType",
    "InteractionDepth",
    "SocialContactStatus",
    "SocialDynamics",
    "SocialCandidate",
    "NPCEntity",
    "NPCFact",
    "SocialRoleCategory",
    "SocialRoleTemplate",
    "ALLOWED_ROLE_TEMPLATES",
    "SocialOpportunityProfile",
    "get_role_template",
]
