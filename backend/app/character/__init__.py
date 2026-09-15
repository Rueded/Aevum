"""Character Foundation and Character State package for Aevum Core."""

from app.character.models import (
    Boundary,
    CharacterDefinition,
    CharacterIdentity,
    Personality,
    Preference,
    PreferenceSentiment,
)
from app.character.service import (
    CharacterDefinitionConflictError,
    CharacterDefinitionService,
    create_initial_aevum_definition,
    get_character_definition,
    update_character_definition,
)
from app.character.state_models import (
    CharacterMood,
    CharacterState,
    CharacterStateUpdate,
)
from app.character.state_service import (
    CharacterStateConflictError,
    CharacterStateService,
    apply_character_state_update,
    create_initial_aevum_state,
    get_character_state,
    update_character_state,
)

__all__ = [
    "Boundary",
    "CharacterDefinition",
    "CharacterDefinitionConflictError",
    "CharacterDefinitionService",
    "CharacterIdentity",
    "CharacterMood",
    "CharacterState",
    "CharacterStateConflictError",
    "CharacterStateService",
    "CharacterStateUpdate",
    "Personality",
    "Preference",
    "PreferenceSentiment",
    "apply_character_state_update",
    "create_initial_aevum_definition",
    "create_initial_aevum_state",
    "get_character_definition",
    "get_character_state",
    "update_character_definition",
    "update_character_state",
]
