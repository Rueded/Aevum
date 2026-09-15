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
from app.memory import (
    EmbeddingProvider,
    HybridMemoryRetrievalQuery,
    HybridMemoryRetrievalService,
    build_memory_context,
    get_embedding_provider,
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
      7. If generation fails, returns appropriate HTTP error (503 if not configured, 502 if upstream fails);
         the user message remains persisted without an assistant message.
    """
    # 1. Validate conversation exists
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

    # 4. Retrieve relevant memories for context grounding (Phase 3.7)
    memory_context_str: str | None = None
    try:
        hybrid_service = HybridMemoryRetrievalService(
            session=db,
            embedding_provider=embedding_provider,
        )
        retrieval_query = HybridMemoryRetrievalQuery(
            text=payload.content,
            limit=5,
        )
        retrieval_res = await hybrid_service.retrieve(retrieval_query)
        if retrieval_res.memories:
            memory_context_str = build_memory_context(retrieval_res.memories)
    except Exception as exc:
        logger.warning(
            "Memory context retrieval failed for conversation '%s': %s",
            conversation_id,
            exc,
        )
        memory_context_str = None

    # 5. Convert into provider-neutral ChatMessage format and construct LLMContext
    chat_messages = [
        ChatMessage(role=m.role, content=m.content)
        for m in stored_messages
    ]
    system_instructions = [memory_context_str] if memory_context_str else None
    llm_context = build_context(
        messages=chat_messages,
        system_instructions=system_instructions,
    )

    # 5. Call the LLM provider with provider-neutral LLMContext
    try:
        llm_response = await llm_provider.generate_response(context=llm_context)

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

    # 6. Validate non-empty assistant response
    if not llm_response.content or not llm_response.content.strip():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM provider generated an empty response.",
        )

    # 7. Persist assistant response
    assistant_msg = Message(
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT.value,
        content=llm_response.content.strip(),
    )
    db.add(assistant_msg)
    conversation.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(assistant_msg)

    # 8. Return both persisted messages
    return MessageCreateResponse(
        message=MessageRead.model_validate(user_msg),
        assistant_response=MessageRead.model_validate(assistant_msg),
        assistant_status="generated",
    )


