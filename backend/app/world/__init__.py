"""Epistemic Grounding & Personal World domain for Aevum Core.

Owns Aevum's canonical biography, social relations, preferences, and epistemic boundaries.
"""

from app.world.models import (
    BiographyFact,
    EpistemicDirective,
    FactEpistemicStatus,
    PersonalWorldContext,
    SocialContact,
    WorldFact,
)
from app.world.context_builder import PersonalWorldContextBuilder
from app.world.epistemic_resolver import EpistemicResolver
from app.world.service import PersonalWorldService

__all__ = [
    "FactEpistemicStatus",
    "BiographyFact",
    "SocialContact",
    "WorldFact",
    "EpistemicDirective",
    "PersonalWorldContext",
    "EpistemicResolver",
    "PersonalWorldService",
    "PersonalWorldContextBuilder",
]
