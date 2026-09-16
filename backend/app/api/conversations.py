from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import logging
from app.api.schemas import (
    ConversationDetailRead,
    ConversationRead,
    MessageCreate,
    MessageCreateResponse,
    MessageRead,
)
from app.db.models import Conversation, Message, MessageRole
from app.db.session import get_db_session
from app.llm import (
    ChatMessage,
    LLMGenerationError,
    LLMProvider,
    LLMProviderNotConfiguredError,
    build_context,
    get_llm_provider,
)
from app.character.engine import CharacterEngine
from app.character.response_generator import ResponseGenerator
from app.memory import (
    EmbeddingProvider,
    HybridMemoryRetrievalQuery,
    HybridMemoryRetrievalService,
    build_memory_context,
    get_embedding_provider,
)
from app.relationship import (
    RelationshipExperienceService,
    RelationshipService,
    RelationshipSignalExtractionService,
    apply_relationship_signals,
    build_relationship_context,
)

logger = logging.getLogger(__name__)




router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.post(
    "",
    response_model=ConversationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation",
)
async def create_conversation(
    db: AsyncSession = Depends(get_db_session),
) -> ConversationRead:
    """Create and persist a new conversation session."""
    conversation = Conversation()
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetailRead,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a conversation and its messages",
)
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> ConversationDetailRead:
    """Retrieve conversation metadata and all associated messages in chronological order."""
    query = (
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages))
    )
    result = await db.execute(query)
    conversation = result.scalar_one_or_none()

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found.",
        )

    return conversation


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a message to an existing conversation and generate assistant reply",
)
async def create_message(
    conversation_id: str,
    payload: MessageCreate,
    db: AsyncSession = Depends(get_db_session),
    llm_provider: LLMProvider = Depends(get_llm_provider),
    embedding_provider: EmbeddingProvider | None = Depends(get_embedding_provider),
) -> MessageCreateResponse:
    """Persist the message and generate an assistant response through the configured LLM provider.

    Behavior:
      1. Validates the conversation exists (404 if missing).
      2. Persists the incoming message immediately so user input is never lost.
      3. Loads all conversation history in chronological order.
      4. Grounding: Retrieves relevant long-term memories and injects them into system instructions.
      5. Invokes the LLM provider to generate a grounded assistant response.
      6. Persists the generated assistant message upon success.
      7. Analyzes interaction for relationship signals and applies deterministic policy.
      8. If generation fails, returns appropriate HTTP error (503 if not configured, 502 if upstream fails);
         the user message remains persisted without an assistant message.
    """
    # 1. Validate non-empty input
    if not payload.content or not payload.content.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message content cannot be empty or whitespace.",
        )

    # 1b. Validate conversation exists
    query = select(Conversation).where(Conversation.id == conversation_id)
    result = await db.execute(query)
    conversation = result.scalar_one_or_none()

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found.",
        )

    # 2. Persist the incoming user message immediately
    user_msg = Message(
        conversation_id=conversation_id,
        role=MessageRole.USER.value,
        content=payload.content,
    )
    db.add(user_msg)
    conversation.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user_msg)

    # 3. Load full conversation history in chronological order
    history_query = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    history_result = await db.execute(history_query)
    stored_messages = history_result.scalars().all()

    # 4. Build CharacterResponseContext using CharacterEngine (Phase 6.3)
    try:
        char_engine = CharacterEngine(session=db, embedding_provider=embedding_provider)
        response_context = await char_engine.build_response_context(
            user_input=payload.content,
            character_id="aevum",
            user_id="user",
        )
    except Exception as exc:
        logger.error("CharacterEngine failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal character engine failure.",
        ) from exc

    # 5. Convert into provider-neutral ChatMessage format
    chat_messages = [
        ChatMessage(role=m.role, content=m.content)
        for m in stored_messages
    ]

    # 6. Call the LLM provider through ResponseGenerator (Phase 6.3)
    try:
        response_generator = ResponseGenerator(provider=llm_provider)
        llm_response = await response_generator.generate_response(
            context=response_context,
            conversation_history=chat_messages,
        )
    except LLMProviderNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except LLMGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    # 8. Persist assistant response
    assistant_msg = Message(
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT.value,
        content=llm_response.content.strip(),
    )
    db.add(assistant_msg)
    conversation.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(assistant_msg)

    # 9. Analyze interaction for relationship signals and apply deterministic policy (Phase 4.2)
    try:
        extraction_service = RelationshipSignalExtractionService(llm_provider=llm_provider)
        interaction_context = chat_messages + [
            ChatMessage(role=assistant_msg.role, content=assistant_msg.content)
        ]
        extraction_result = await extraction_service.extract_signals(interaction_context)
        if extraction_result.is_success and extraction_result.signals:
            rel_service = RelationshipService(db)
            current_rel = await rel_service.get_relationship_state()
            rel_update = apply_relationship_signals(
                state=current_rel,
                signals=extraction_result.signals,
            )
            if rel_update is not None:
                await rel_service.apply_update(
                    update_data=rel_update,
                    expected_version=current_rel.version,
                )

            # Record accepted relationship experiences (Phase 4.4)
            exp_service = RelationshipExperienceService(db)
            await exp_service.record_signals(
                signals=extraction_result.signals,
                relationship_id=current_rel.id,
            )
    except Exception as exc:
        logger.warning(
            "Relationship signal and experience processing failed for conversation '%s': %s",
            conversation_id,
            exc,
        )

    # 10. Return both persisted messages
    return MessageCreateResponse(
        message=MessageRead.model_validate(user_msg),
        assistant_response=MessageRead.model_validate(assistant_msg),
        assistant_status="generated",
    )



