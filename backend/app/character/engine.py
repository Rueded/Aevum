"""Character engine for Aevum Core.

Orchestrates the gathering of character, relational, emotional, and memory state
needed to make a response decision:
User Input
    ↓
CharacterEngine
├── CharacterDefinition
├── CharacterState
├── Relevant Memory Context
├── Relationship Context
└── Emotion Context
    ↓
CharacterResponseContext

Guarantees:
- Read-only orchestration: Zero mutations to CharacterState, CharacterDefinition, RelationshipState, EmotionState, or Memory.
- Pure context assembly: Zero LLM generation, zero prompt execution, zero database writes.
- Deterministic output: Equivalent inputs and domain states always yield equivalent response contexts.
- Explicit failures: Missing or invalid required domain states fail explicitly rather than silently fabricating data.
- Domain encapsulation: Context objects expose no raw database ORM records, SQL objects, version numbers, or retrieval scores.
"""

from collections.abc import Sequence
import logging
from typing import Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.engine_models import (
    CharacterBehaviorContext,
    CharacterDefinitionContext,
    CharacterEmotionContext,
    CharacterMemoryContext,
    CharacterResponseContext,
    CharacterStateContext,
)
from app.character.models import CharacterDefinition
from app.character.service import CharacterDefinitionService
from app.character.state_models import CharacterState
from app.character.state_service import CharacterStateService
from app.emotion.emotion_models import EmotionState
from app.emotion.service import EmotionService
from app.memory.embedding_provider import EmbeddingProvider
from app.memory.hybrid_retrieval_service import HybridMemoryRetrievalService
from app.memory.models import HybridMemoryResult, HybridMemoryRetrievalQuery, Memory
from app.relationship.context_builder import RelationshipContextBuilder
from app.relationship.models import RelationshipState
from app.relationship.service import RelationshipService
from app.life.models import LifeState, LifeEvent
from app.life.services import LifeService
from app.life.context_builder import LifeContextBuilder

logger = logging.getLogger(__name__)


class CharacterEngine:
    """Orchestrates gathering domain context for response decision making."""

    def __init__(
        self,
        session: Optional[AsyncSession] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ) -> None:
        self._session = session
        self._embedding_provider = embedding_provider

    async def build_response_context(
        self,
        user_input: str,
        character_id: str = "aevum",
        user_id: str = "user",
        character_definition: Optional[CharacterDefinition] = None,
        character_state: Optional[CharacterState] = None,
        relationship_state: Optional[RelationshipState] = None,
        emotion_state: Optional[EmotionState] = None,
        memories: Optional[Sequence[Union[HybridMemoryResult, Memory]]] = None,
        life_state: Optional[LifeState] = None,
        recent_events: Optional[Sequence[LifeEvent]] = None,
    ) -> CharacterResponseContext:
        """Gather all relevant domain contexts into a structured CharacterResponseContext.

        Args:
            user_input: Current user input statement or query.
            character_id: Identifier of the character (default "aevum").
            user_id: Identifier of the user (default "user").
            character_definition: Optional pre-loaded CharacterDefinition.
            character_state: Optional pre-loaded CharacterState.
            relationship_state: Optional pre-loaded RelationshipState.
            emotion_state: Optional pre-loaded EmotionState.
            memories: Optional pre-retrieved memory sequence.

        Returns:
            An immutable CharacterResponseContext.

        Raises:
            ValueError: If user_input is empty or whitespace.
            RuntimeError: If required domain state cannot be loaded due to missing session or missing record.
        """
        # 1. Validate user input
        if not isinstance(user_input, str) or not user_input.strip():
            raise ValueError("user_input must not be empty or whitespace.")
        cleaned_user_input = user_input.strip()

        # 2. Character definition context
        if character_definition is None:
            if self._session is None:
                raise RuntimeError("Cannot load character_definition without a database session.")
            char_def_service = CharacterDefinitionService(self._session)
            character_definition = await char_def_service.get_character(character_id)
            if character_definition is None:
                raise RuntimeError(f"Character definition '{character_id}' not found.")

        char_ctx = CharacterDefinitionContext.from_definition(character_definition)

        # 3. Character state context
        if character_state is None:
            if self._session is None:
                raise RuntimeError("Cannot load character_state without a database session.")
            char_state_service = CharacterStateService(self._session)
            character_state = await char_state_service.get_state(character_id)
            if character_state is None:
                raise RuntimeError(f"Character state for '{character_id}' not found.")

        state_ctx = CharacterStateContext.from_state(character_state)

        # 4. Relationship context
        if relationship_state is None:
            if self._session is None:
                raise RuntimeError("Cannot load relationship_state without a database session.")
            rel_service = RelationshipService(self._session)
            relationship_state = await rel_service.get_relationship_state(relationship_id=user_id)
            if relationship_state is None:
                raise RuntimeError(f"Relationship state for user '{user_id}' not found.")

        rel_ctx = RelationshipContextBuilder.build(relationship_state)

        # 5. Emotion context
        if emotion_state is None:
            if self._session is None:
                raise RuntimeError("Cannot load emotion_state without a database session.")
            emotion_service = EmotionService(self._session)
            emotion_state = await emotion_service.get_emotion_state(character_id)
            if emotion_state is None:
                raise RuntimeError(f"Emotion state for '{character_id}' not found.")

        emotion_ctx = CharacterEmotionContext.from_state(emotion_state)

        # 6. Memory context
        if memories is None:
            if self._session is not None:
                try:
                    retrieval_service = HybridMemoryRetrievalService(
                        session=self._session,
                        embedding_provider=self._embedding_provider,
                    )
                    retrieval_res = await retrieval_service.retrieve(
                        HybridMemoryRetrievalQuery(text=cleaned_user_input, limit=5)
                    )
                    memories = retrieval_res.memories
                except Exception as exc:
                    logger.warning("Memory retrieval failed during character engine context building: %s", exc)
                    memories = ()
            else:
                memories = ()

        mem_ctx = CharacterMemoryContext.from_memories(memories)

        # 6.5 Life Context
        if life_state is None:
            if self._session is None:
                raise RuntimeError("Cannot load life_state without a database session.")
            life_service = LifeService(self._session)
            life_state = await life_service.get_life_state(character_id)
            if life_state is None:
                raise RuntimeError(f"Life state for '{character_id}' not found.")
                
        if recent_events is None:
            if self._session is not None:
                life_service = LifeService(self._session)
                recent_events = await life_service.list_events(character_id, limit=3)
            else:
                recent_events = ()
                
        life_ctx = LifeContextBuilder.build(life_state, recent_events)

        # 7. Behavior synthesis
        behavior_ctx = CharacterBehaviorContext.synthesize(
            state=state_ctx,
            emotion=emotion_ctx,
        )

        return CharacterResponseContext(
            user_input=cleaned_user_input,
            character=char_ctx,
            character_state=state_ctx,
            relationship=rel_ctx,
            emotion=emotion_ctx,
            memory=mem_ctx,
            behavior=behavior_ctx,
            life=life_ctx,
        )
