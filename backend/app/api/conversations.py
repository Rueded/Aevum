import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete as sql_delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.schemas import (
    ConversationDetailRead,
    ConversationListItem,
    ConversationRead,
    MessageCreate,
    MessageCreateResponse,
    MessageRead,
    VoiceMessageCreate,
    VoiceMessageResponse,
)
from app.character.state_service import CharacterStateService
from app.db.models import Conversation, Message, MessageRole
from app.db.session import get_db_session
from app.emotion.service import EmotionService
from app.voice import (
    AudioChannel,
    AudioData,
    AudioFormat,
    EpistemicCue,
    ProsodyConfig,
    ProsodyMapper,
    STTService,
    TTSService,
    SynthesisStatus,
    TranscriptionStatus,
    VoiceInputMode,
)
from app.voice.dependencies import get_stt_service, get_tts_service
from app.llm import (
    ChatMessage,
    LLMContext,
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
    "",
    response_model=list[ConversationListItem],
    status_code=status.HTTP_200_OK,
    summary="List all conversations ordered by recent activity",
)
async def list_conversations(
    limit: int = 50,
    db: AsyncSession = Depends(get_db_session),
) -> list[ConversationListItem]:
    """Retrieve all conversations with message count and preview snippet."""
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    conversations = result.scalars().all()

    items: list[ConversationListItem] = []
    for conv in conversations:
        msgs = conv.messages or []
        last_preview = msgs[-1].content[:60] if msgs else None
        items.append(
            ConversationListItem(
                id=conv.id,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=len(msgs),
                last_message_preview=last_preview,
            )
        )
    return items


@router.delete(
    "/{conversation_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Delete a conversation and its messages",
)
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Delete a conversation session and all related messages and notifications."""
    query = (
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages))
    )
    result = await db.execute(query)
    conv = result.scalar_one_or_none()
    if conv:
        msg_ids = [m.id for m in (conv.messages or [])]
        if msg_ids:
            from app.db.models import ProactiveNotificationRecord
            await db.execute(
                sql_delete(ProactiveNotificationRecord).where(
                    ProactiveNotificationRecord.conversation_message_id.in_(msg_ids)
                )
            )
        await db.delete(conv)
        await db.commit()
    return {"status": "deleted", "id": conversation_id}


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

    # 1c. Rapid duplicate submission debounce (prevents mobile double-tap ghost turns)
    recent_dup_query = (
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.role == MessageRole.USER.value,
        )
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    last_user_msg = (await db.scalars(recent_dup_query)).first()
    if last_user_msg and last_user_msg.content == payload.content:
        now_check = datetime.now(timezone.utc)
        l_time = last_user_msg.created_at if last_user_msg.created_at.tzinfo else last_user_msg.created_at.replace(tzinfo=timezone.utc)
        if (now_check - l_time).total_seconds() < 1.5:
            last_ast_query = (
                select(Message)
                .where(
                    Message.conversation_id == conversation_id,
                    Message.role == MessageRole.ASSISTANT.value,
                )
                .order_by(Message.created_at.desc())
                .limit(1)
            )
            last_ast_msg = (await db.scalars(last_ast_query)).first()
            return MessageCreateResponse(
                message=MessageRead.model_validate(last_user_msg),
                assistant_response=MessageRead.model_validate(last_ast_msg) if last_ast_msg else None,
                assistant_status="generated",
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

    # 3.5 Calculate elapsed physical time since previous turn
    elapsed_time_desc = None
    if len(stored_messages) >= 2:
        prev_turn = stored_messages[-2]
        prev_time = prev_turn.created_at if prev_turn.created_at.tzinfo else prev_turn.created_at.replace(tzinfo=timezone.utc)
        curr_time = user_msg.created_at if user_msg.created_at.tzinfo else user_msg.created_at.replace(tzinfo=timezone.utc)
        diff_sec = max(0, int((curr_time - prev_time).total_seconds()))
        if diff_sec < 45:
            elapsed_time_desc = f"即时打字连续交流中（上一条消息仅过去 {diff_sec} 秒）"
        elif diff_sec < 180:
            elapsed_time_desc = f"间隔约 {diff_sec // 60} 分钟，几乎是在同一连续对话节奏内"
        elif diff_sec < 3600:
            mins = diff_sec // 60
            elapsed_time_desc = (
                f"距离上一条消息过去了约 {mins} 分钟。"
                f"（重要真实物理常识：现实世界过去了 {mins} 分钟！"
                f"例如10分钟完全足够女生快速化个淡妆换好衣服，但如果洗澡化妆全部在10分钟内做完就会显得很赶/不可思议；"
                f"如果被用户问到时间，苏棠要具有清晰、真实的人类时间流速感知，符合物理逻辑，不可胡言乱语）"
            )
        elif diff_sec < 86400:
            hrs = round(diff_sec / 3600, 1)
            elapsed_time_desc = f"距离上一条消息过去了约 {hrs} 小时（有足够的时间进行日常生活、上课、练琴、写作业、休息或外出）"
        else:
            days = round(diff_sec / 86400, 1)
            elapsed_time_desc = f"距离上一条消息已经过去约 {days} 天（一段时间未见，各自生活继续）"

    # 4. Build CharacterResponseContext using CharacterEngine (Phase 6.3)
    try:
        from app.life.schedule_engine import LifeScheduleEngine
        await LifeScheduleEngine.reconcile_schedule(db, "aevum")
    except Exception as sched_err:
        logger.warning("Dynamic schedule reconcile in create_message skipped: %s", sched_err)

    try:
        char_engine = CharacterEngine(session=db, embedding_provider=embedding_provider)
        response_context = await char_engine.build_response_context(
            user_input=payload.content,
            character_id="aevum",
            user_id="user",
            elapsed_time_description=elapsed_time_desc,
        )
    except Exception as exc:
        logger.error("CharacterEngine failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal character engine failure.",
        ) from exc

    # 4.5. Sleep Realism & DND Logic (Respects quiet hours & deep sleep)
    is_sound_asleep_suppressed = False
    sleep_response_to_return = None
    try:
        from app.desktop.service import DesktopService
        desktop_service = DesktopService(db)
        desktop_settings = await desktop_service.get_settings("aevum")
        sleep_realism = getattr(desktop_settings, "sleep_realism_enabled", True)

        current_act = (response_context.character_state.current_activity or "").lower()
        is_sleeping = any(k in current_act for k in ("sleep", "night_sleep", "deep_sleep", "睡觉", "睡眠", "小憩", "熟睡"))

        if sleep_realism and is_sleeping:
            now_utc = datetime.now(timezone.utc)
            # Count recent user messages in the last 90 seconds
            recent_user_turns = [
                m for m in stored_messages
                if m.role == MessageRole.USER.value
                and (now_utc - (m.created_at if m.created_at.tzinfo else m.created_at.replace(tzinfo=timezone.utc))).total_seconds() <= 90
            ]

            # If user sent fewer than 3 messages in 90 seconds: she remains sound asleep!
            if len(recent_user_turns) < 3:
                sleep_msg = Message(
                    conversation_id=conversation_id,
                    role=MessageRole.ASSISTANT.value,
                    content="（苏棠正在深度睡眠中……呼吸平稳安静，没有被消息吵醒。若有急事可尝试连续发消息或拨打语音通话）",
                )
                db.add(sleep_msg)
                conversation.updated_at = now_utc
                await db.commit()
                await db.refresh(sleep_msg)

                user_read = MessageRead.model_validate(user_msg)
                assistant_read = MessageRead.model_validate(sleep_msg)
                is_sound_asleep_suppressed = True
                sleep_response_to_return = MessageCreateResponse(
                    message=user_read,
                    assistant_response=assistant_read,
                    assistant_status="generated",
                )
            else:
                # User sent 3+ messages in 90s: phone vibrations wake her up!
                from app.life.dialogue_situation import DialogueSituation, DialogueSituationAppraisalService
                await DialogueSituationAppraisalService.apply_situation(
                    session=db,
                    character_id="aevum",
                    situation=DialogueSituation(
                        activity="被消息吵醒/迷糊赖床中",
                        location="老家-卧室床上",
                        status="REST",
                        duration_minutes=60,
                        idempotency_title="连续消息震动吵醒",
                    ),
                )
                waking_guidance = (
                    "\n【真实作息突发事件】：你本来在深度睡眠中，但对方在短时间内连续发了多条消息，"
                    "手机在床头连续震动把你吵醒了！你揉着眼睛迷迷糊糊从被窝里摸到手机，"
                    "带着浓浓的鼻音、困意和打哈欠，半梦半醒地问对方怎么了，是不是有什么急事。"
                )
                if hasattr(response_context, "arbitration_guidance") and response_context.arbitration_guidance:
                    response_context.arbitration_guidance += waking_guidance
    except Exception as sleep_check_err:
        logger.warning("Sleep realism check skipped with error: %s", sleep_check_err)

    if is_sound_asleep_suppressed and sleep_response_to_return is not None:
        return sleep_response_to_return

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

    # Safely construct response models immediately from committed records
    user_read = MessageRead.model_validate(user_msg)
    assistant_read = MessageRead.model_validate(assistant_msg)
    if llm_response.speech_bubbles:
        assistant_read.speech_bubbles = llm_response.speech_bubbles

    interaction_context = chat_messages + [
        ChatMessage(role=assistant_msg.role, content=assistant_msg.content)
    ]

    # 9. Non-critical post-turn processing: Relationship signals (isolated boundary)
    try:
        extraction_service = RelationshipSignalExtractionService(llm_provider=llm_provider)
        extraction_result = await extraction_service.extract_signals(interaction_context)
        if extraction_result.is_success and extraction_result.signals:
            rel_service = RelationshipService(db)
            current_rel = await rel_service.get_relationship_state(relationship_id="user")
            rel_update = apply_relationship_signals(
                state=current_rel,
                signals=extraction_result.signals,
            )
            if rel_update is not None:
                await rel_service.apply_update(
                    update_data=rel_update,
                    expected_version=current_rel.version,
                    relationship_id="user",
                )

            # Record accepted relationship experiences (Phase 4.4)
            exp_service = RelationshipExperienceService(db)
            await exp_service.record_signals(
                signals=extraction_result.signals,
                relationship_id="user",
            )
    except Exception as exc:
        await db.rollback()
        logger.warning(
            "Relationship signal and experience processing failed for conversation '%s': %s",
            conversation_id,
            exc,
        )

    # 9b. Non-critical post-turn processing: Memory extraction and curation (isolated boundary)
    try:
        from app.memory.curation_service import MemoryCurationService
        from app.memory.extraction_service import MemoryExtractionService

        mem_extraction_service = MemoryExtractionService(
            session=db,
            llm_provider=llm_provider,
        )
        mem_extract_res = await mem_extraction_service.extract_and_create_candidates(
            messages=interaction_context,
        )
        if mem_extract_res.is_success and mem_extract_res.candidate_ids:
            curation_service = MemoryCurationService(session=db)
            for cid in mem_extract_res.candidate_ids:
                try:
                    await curation_service.curate_candidate(cid)
                except Exception as c_err:
                    logger.debug("Immediate candidate curation error for %s: %s", cid, c_err)
            await curation_service.curate_pending_candidates()
    except Exception as exc:
        await db.rollback()
        logger.warning(
            "Memory candidate extraction and curation failed for conversation '%s': %s",
            conversation_id,
            exc,
        )

    # 9c. Non-critical post-turn processing: Emotion & Mood transitions (isolated boundary)
    try:
        from app.emotion.turn_appraisal import TurnEmotionAppraisalService
        turn_emotion_service = TurnEmotionAppraisalService(session=db)
        await turn_emotion_service.process_turn_emotion(
            user_input=payload.content,
            assistant_response=assistant_msg.content,
            response_context=response_context,
            character_id="aevum",
        )
    except Exception as exc:
        await db.rollback()
        logger.warning(
            "Emotion and mood post-turn appraisal failed for conversation '%s': %s",
            conversation_id,
            exc,
        )

    # 9d. Non-critical post-turn processing: Deception & Cognitive Grievance lifecycle (isolated boundary)
    try:
        if response_context.deception_grievance:
            from app.reality.deception_service import DeceptionService
            from app.reality.deception_models import GrievanceStage
            dec_svc = DeceptionService(db)
            dg = response_context.deception_grievance
            if dg.stage == GrievanceStage.VERIFIED_DECEPTION:
                # Assistant has just confronted the user in this generated message
                await dec_svc.mark_confronted(dg.grievance_id)
            elif dg.stage == GrievanceStage.RECONCILING:
                # Assistant has just forgiven and reconciled with the user
                await dec_svc.reconcile_grievance(dg.grievance_id)
    except Exception as exc:
        logger.warning(
            "Deception grievance post-turn progression failed for conversation '%s': %s",
            conversation_id,
            exc,
        )

    # 9e. Non-critical post-turn processing: Situational & Dialogue Commitment Extraction
    try:
        from app.life.dialogue_situation import DialogueSituationAppraisalService
        detected_situation = DialogueSituationAppraisalService.extract_situation(
            user_input=payload.content,
            assistant_response=assistant_msg.content,
        )
        if detected_situation:
            await DialogueSituationAppraisalService.apply_situation(
                session=db,
                character_id="aevum",
                situation=detected_situation,
            )
    except Exception as sit_err:
        await db.rollback()
        logger.warning("Dialogue situational commitment extraction error: %s", sit_err)

    # 10. Return both persisted messages
    return MessageCreateResponse(
        message=user_read,
        assistant_response=assistant_read,
        assistant_status="generated",
    )


@router.post(
    "/{conversation_id}/voice-messages",
    response_model=VoiceMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit spoken audio input, run speech recognition, generate reply, and optionally synthesize audio",
)
async def create_voice_message(
    conversation_id: str,
    payload: VoiceMessageCreate,
    db: AsyncSession = Depends(get_db_session),
    llm_provider: LLMProvider = Depends(get_llm_provider),
    embedding_provider: EmbeddingProvider | None = Depends(get_embedding_provider),
    stt_service: STTService = Depends(get_stt_service),
    tts_service: TTSService = Depends(get_tts_service),
) -> VoiceMessageResponse:
    """Execute a voice-driven conversational turn (Phase 10.5).

    Governed by ADR-021:
    - Rule 18 Consent: Explicit user consent required before invoking STT.
    - PTT-Only Input: Continuous VAD deferred; input_mode must be PTT.
    - Lock A: Audio != Canonical Reality. Voice audio is transient; transcript becomes user turn.
    - Lock B: Decoupled Failure Resilience. STT failure leaves DB untouched (0 turns);
      TTS synthesis failure persists the text turn normally and returns audio_status='failed'.
    """
    # 1. Enforce Rule 18 microphone consent
    if not payload.user_consent_granted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Voice message rejected: Rule 18 requires explicit user consent.",
        )

    # 2. Enforce PTT-only input mode (ADR-021 Decision 3)
    if payload.input_mode.upper() != "PTT":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Voice message rejected: Only PTT input mode is supported in Phase 10.",
        )

    # 3. Validate conversation exists
    conv_query = select(Conversation).where(Conversation.id == conversation_id)
    conv_res = await db.execute(conv_query)
    conversation = conv_res.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found.",
        )

    # 4. Decode base64 audio payload
    try:
        raw_bytes = base64.b64decode(payload.audio_base64)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Malformed audio_base64 payload: {exc}",
        ) from exc

    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Audio payload cannot be empty.",
        )

    try:
        fmt = AudioFormat(payload.format.upper())
        channels = AudioChannel(payload.channels.upper())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid audio format or channel: {exc}",
        ) from exc

    audio = AudioData.create(
        data=raw_bytes,
        format=fmt,
        sample_rate_hz=payload.sample_rate_hz,
        channels=channels,
        duration_ms=payload.duration_ms,
    )

    # 5. Transcribe via STTService (Lock B: failure leaves DB untouched)
    stt_result = await stt_service.transcribe_audio(
        audio=audio,
        user_consent_granted=payload.user_consent_granted,
    )

    if (
        stt_result.status != TranscriptionStatus.SUCCESS
        or not stt_result.transcribed_text
        or not stt_result.transcribed_text.strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Speech transcription failed: {stt_result.error_message or 'No speech detected'}",
        )

    transcribed_text = stt_result.transcribed_text.strip()

    # 6. Persist user message with transcribed speech
    user_msg = Message(
        conversation_id=conversation_id,
        role=MessageRole.USER.value,
        content=transcribed_text,
    )
    db.add(user_msg)
    conversation.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user_msg)

    # 7. Load full conversation history in chronological order
    history_query = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    history_result = await db.execute(history_query)
    stored_messages = history_result.scalars().all()

    # 8. Build CharacterResponseContext using CharacterEngine
    try:
        from app.life.schedule_engine import LifeScheduleEngine
        await LifeScheduleEngine.reconcile_schedule(db, "aevum")
    except Exception as sched_err:
        logger.warning("Dynamic schedule reconcile in create_voice_message skipped: %s", sched_err)

    try:
        char_engine = CharacterEngine(session=db, embedding_provider=embedding_provider)
        response_context = await char_engine.build_response_context(
            user_input=transcribed_text,
            character_id="aevum",
            user_id="user",
        )
    except Exception as exc:
        logger.error("CharacterEngine failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal character engine failure.",
        ) from exc

    # 9. Invoke LLM provider
    chat_messages = [ChatMessage(role=m.role, content=m.content) for m in stored_messages]
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

    # 10. Persist assistant message
    assistant_msg = Message(
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT.value,
        content=llm_response.content.strip(),
    )
    db.add(assistant_msg)
    conversation.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(assistant_msg)

    user_read = MessageRead.model_validate(user_msg)
    assistant_read = MessageRead.model_validate(assistant_msg)
    if llm_response.speech_bubbles:
        assistant_read.speech_bubbles = llm_response.speech_bubbles

    # 11. Post-turn processing (Relationship + Memory, non-critical)
    interaction_context = chat_messages + [
        ChatMessage(role=assistant_msg.role, content=assistant_msg.content)
    ]
    try:
        extraction_service = RelationshipSignalExtractionService(llm_provider=llm_provider)
        extraction_result = await extraction_service.extract_signals(interaction_context)
        if extraction_result.is_success and extraction_result.signals:
            rel_service = RelationshipService(db)
            current_rel = await rel_service.get_relationship_state(relationship_id="user")
            rel_update = apply_relationship_signals(
                state=current_rel,
                signals=extraction_result.signals,
            )
            if rel_update is not None:
                await rel_service.apply_update(
                    update_data=rel_update,
                    expected_version=current_rel.version,
                    relationship_id="user",
                )
            exp_service = RelationshipExperienceService(db)
            await exp_service.record_signals(
                signals=extraction_result.signals,
                relationship_id="user",
            )
    except Exception as exc:
        await db.rollback()
        logger.warning(
            "Relationship processing failed in voice turn for conversation '%s': %s",
            conversation_id,
            exc,
        )

    try:
        from app.memory.curation_service import MemoryCurationService
        from app.memory.extraction_service import MemoryExtractionService

        mem_extraction_service = MemoryExtractionService(
            session=db,
            llm_provider=llm_provider,
        )
        mem_extract_res = await mem_extraction_service.extract_and_create_candidates(
            messages=interaction_context,
        )
        if mem_extract_res.is_success and mem_extract_res.candidate_ids:
            curation_service = MemoryCurationService(session=db)
            for cid in mem_extract_res.candidate_ids:
                try:
                    await curation_service.curate_candidate(cid)
                except Exception as c_err:
                    logger.debug("Immediate candidate curation error for %s: %s", cid, c_err)
            await curation_service.curate_pending_candidates()
    except Exception as exc:
        await db.rollback()
        logger.warning(
            "Memory extraction failed in voice turn for conversation '%s': %s",
            conversation_id,
            exc,
        )

    try:
        from app.emotion.turn_appraisal import TurnEmotionAppraisalService
        turn_emotion_service = TurnEmotionAppraisalService(session=db)
        await turn_emotion_service.process_turn_emotion(
            user_input=transcribed_text,
            assistant_response=assistant_msg.content,
            response_context=response_context,
            character_id="aevum",
        )
    except Exception as exc:
        await db.rollback()
        logger.warning(
            "Emotion and mood voice post-turn appraisal failed for conversation '%s': %s",
            conversation_id,
            exc,
        )

    # 12. Spoken Reply Audio Synthesis (TTS) - Decoupled Fault Resilience (Lock B)
    audio_b64: str | None = None
    audio_cache_key: str | None = None
    audio_status: str = "skipped"

    if payload.synthesize_reply_audio:
        try:
            # Read-only affect mapping (Lock C)
            try:
                emotion_service = EmotionService(db)
                state_service = CharacterStateService(db)
                current_emotion = await emotion_service.get_emotion_state("aevum")
                current_char_state = await state_service.get_state("aevum")
                prosody = ProsodyMapper.from_states(
                    emotion_state=current_emotion,
                    character_state=current_char_state,
                    epistemic_cue=EpistemicCue.CERTAIN,
                )
            except Exception:
                prosody = ProsodyConfig()

            tts_result = await tts_service.synthesize_text(
                text=assistant_msg.content,
                voice_id=payload.voice_id,
                desired_format=fmt,
                prosody=prosody,
                epistemic_cue=EpistemicCue.CERTAIN,
            )

            if tts_result.status == SynthesisStatus.SUCCESS and tts_result.audio is not None:
                audio_b64 = base64.b64encode(tts_result.audio.data).decode("ascii")
                audio_cache_key = tts_result.cache_key
                audio_status = "success"
            else:
                audio_status = "failed"
                logger.warning("TTS reply synthesis failed: %s", tts_result.error_message)
        except Exception as exc:
            audio_status = "failed"
            logger.warning("TTS service exception during voice turn: %s", exc)

    return VoiceMessageResponse(
        message=user_read,
        transcribed_text=transcribed_text,
        assistant_response=assistant_read,
        assistant_status="generated",
        audio_data_base64=audio_b64,
        audio_cache_key=audio_cache_key,
        audio_status=audio_status,
    )


@router.post(
    "/{conversation_id}/check-idle",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Check if user paused replying after companion inquiry, and generate a natural hesitation nudge",
)
async def check_idle_nudge(
    conversation_id: str,
    idle_threshold: int = 75,
    db: AsyncSession = Depends(get_db_session),
    llm: LLMProvider = Depends(get_llm_provider),
) -> dict[str, Any]:
    """Check if the user paused responding after an active inquiry and generate a natural companion nudge."""
    query = (
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages))
    )
    result = await db.execute(query)
    conv = result.scalar_one_or_none()
    if not conv or not conv.messages:
        return {"nudged": False, "reason": "no_messages"}

    last_msg = conv.messages[-1]
    # Only nudge if the last turn was from the assistant
    if last_msg.role != MessageRole.ASSISTANT:
        return {"nudged": False, "reason": "not_assistant_turn"}

    # Avoid double nudging if assistant already sent the last 2 consecutive messages
    if len(conv.messages) >= 2 and conv.messages[-2].role == MessageRole.ASSISTANT:
        return {"nudged": False, "reason": "already_nudged"}

    # Calculate elapsed idle time
    now = datetime.now(timezone.utc)
    msg_time = last_msg.created_at
    if msg_time.tzinfo is None:
        msg_time = msg_time.replace(tzinfo=timezone.utc)
    elapsed = (now - msg_time).total_seconds()

    if elapsed < idle_threshold:
        return {"nudged": False, "reason": "within_threshold", "elapsed_seconds": elapsed}

    # 1. Check for explicit farewell, bedtime, or sign-off in recent messages
    recent_texts = " ".join([m.content for m in conv.messages[-3:]]).lower()
    farewell_keywords = (
        "晚安",
        "好梦",
        "做个好梦",
        "去睡了",
        "睡觉了",
        "先睡了",
        "准备睡了",
        "洗洗睡",
        "拜拜",
        "先下了",
        "明天见",
        "下次聊",
        "改天聊",
        "先去忙",
        "要去忙",
        "先干活",
        "去开会",
        "去洗澡",
        "出门了",
        "回头聊",
        "先不聊",
        "不打扰了",
        "不打扰你",
        "那就这样",
        "明天不见不散",
        "明天见啦",
        "路上小心",
        "你也早点睡",
        "快去睡吧",
        "快去忙吧",
    )
    if any(kw in recent_texts for kw in farewell_keywords):
        return {"nudged": False, "reason": "conversation_farewell_or_closed"}

    # 2. Verify if companion was waiting for a plan, answer, or response
    content = last_msg.content
    is_expecting_reply = any(
        q in content
        for q in (
            "?",
            "？",
            "吗",
            "呢",
            "吧",
            "计划",
            "去哪",
            "想吃",
            "如何",
            "怎样",
            "什么",
            "你觉得",
            "要不要",
            "换一间",
            "哪间",
            "电影",
            "餐厅",
            "行程",
        )
    )

    # If the last message was a statement without active question/proposal, do not nudge
    if not is_expecting_reply:
        return {"nudged": False, "reason": "not_expecting_immediate_reply"}

    # 3. Synthesize natural hesitation nudge with topic closure appraisal
    recent_dialogue_lines = [
        f"{'对方' if m.role == MessageRole.USER else '苏棠'}: {m.content}"
        for m in conv.messages[-6:]
    ]
    eval_user_prompt = (
        "【情境上下文】：\n"
        + "\n".join(recent_dialogue_lines)
        + f"\n\n苏棠最后发的一句是：『{content}』。\n\n"
        + "【当前状况】：对方在即时聊天中停顿超过3分钟没有回应了。\n"
        + "请作为苏棠的情境与心智感知引擎判断是否需要催问。\n\n"
        + "【绝对严禁催问的情况 (必须直接输出 [NO_NUDGE])】：\n"
        + "1. 话题已经自然结束、或者双方已达成共识收尾（例如'好哦'、'那就这样'、'哈哈知道了'、讨论已完毕）；\n"
        + "2. 属于互道晚安、准备睡觉、出门忙事、告别、或者自然舒适的静默休息；\n"
        + "3. 苏棠的最后一句发言属于随口感叹、情绪附和、陈述句，并未真切向对方提出问题或等待对方做决定；\n"
        + "4. 双方正处于需要时间思考、回忆、查资料、做饭、看电影、驾驶或短暂停顿中，属于正常生活节奏，严禁神经质催促对方！\n"
        + "若符合上述任何一种情况，请严格直接输出：`[NO_NUDGE]`，不要输出任何多余字符。\n\n"
        + "【仅在以下情况才输出催问】：\n"
        + "苏棠上一条发言明确提出了待商量的事宜（如挑选餐厅、看什么电影、商量明天计划等），认真在等待对方建议或做决定，但对方毫无征兆长时间停滞。\n"
        + "此时以苏棠真实的傲娇、探究、微怼口吻，输出一条简短生动的催问/调侃（1到2句话，如'人呢？'、'你不会还没查好行程吧'等，严禁机械堆砌表情包或口头禅）。\n"
        + "直接输出对白文本，严禁包含任何AI声明或分析解释。"
    )

    try:
        response = await llm.generate_response(
            LLMContext(
                messages=[ChatMessage(role="user", content=eval_user_prompt)],
                enable_grounding=False,
            )
        )
        nudge_text = response.content.strip() if response and response.content else ""
        if not nudge_text or "[NO_NUDGE]" in nudge_text or "NO_NUDGE" in nudge_text:
            return {"nudged": False, "reason": "topic_naturally_concluded"}

        nudge_msg = Message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=nudge_text,
        )
        db.add(nudge_msg)
        conv.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(nudge_msg)

        return {
            "nudged": True,
            "message": {
                "id": nudge_msg.id,
                "conversation_id": nudge_msg.conversation_id,
                "role": nudge_msg.role.value if hasattr(nudge_msg.role, "value") else str(nudge_msg.role),
                "content": nudge_msg.content,
                "created_at": nudge_msg.created_at.isoformat(),
            },
        }
    except Exception as exc:
        logger.info("Idle hesitation check concluded without nudge: %s", exc)
        return {"nudged": False, "reason": "topic_naturally_concluded"}





