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
from app.character.engine import (
    CharacterEngine,
)
from app.character.engine_models import (
    CharacterDefinitionContext,
    CharacterEmotionContext,
    CharacterMemoryContext,
    CharacterResponseContext,
    CharacterStateContext,
    format_emotion_summary,
)
from app.character.response_models import CharacterResponse
from app.character.prompt_assembler import (
    ResponseContextAssembler,
    assemble_response_llm_context,
)
from app.character.response_generator import ResponseGenerator
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
    "CharacterDefinitionContext",
    "CharacterDefinitionService",
    "CharacterEmotionContext",
    "CharacterEngine",
    "CharacterIdentity",
    "CharacterMemoryContext",
    "CharacterMood",
    "CharacterResponse",
    "CharacterResponseContext",
    "CharacterState",
    "CharacterStateConflictError",
    "CharacterStateContext",
    "CharacterStateService",
    "CharacterStateUpdate",
    "Personality",
    "Preference",
    "PreferenceSentiment",
    "ResponseContextAssembler",
    "ResponseGenerator",
    "apply_character_state_update",
    "assemble_response_llm_context",
    "create_initial_aevum_definition",
    "create_initial_aevum_state",
    "format_emotion_summary",
    "get_character_definition",
    "get_character_state",
    "update_character_definition",
    "update_character_state",
]
