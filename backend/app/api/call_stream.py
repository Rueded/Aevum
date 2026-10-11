"""FastAPI WebSocket Streaming Gateway for Realtime Voice Call (Phase 13.3).

Governed by ADR-024 (Revision 2):
- 13.3-A: Transport 不得拥有 Reality Authority (streaming is purely an input/output conduit).
- 13.3-B: Provider 是 Adapter，不是 Truth Authority (transcripts and audio are sensory events, not canonical truth).
- 13.3-C: WebSocket 断开不能制造 semantic events (transient socket drops never synthesize fake turns).
- Lock 1: Streaming Isolation & Audio != Emotion.
- Lock 2: Monotonic Generation & Sequence Fencing.
- Lock 3: Three-State Transcript & Double-Gated Commitment.
- Lock 4: Instant Client-Local Barge-in latching & cascading cancellation.
- Lock 5: Asymmetric Provider Failure Decoupling (STT failure -> Zero Fake Turn; TTS failure -> text fallback).
- Lock 8: Canonical Conversation Boundary (Only fully COMMITTED turns enter persistent conversation).
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, ConfigDict, Field

from app.voice.dependencies import (
    get_realtime_session_manager,
    get_streaming_stt_provider,
    get_streaming_tts_provider,
)
from app.voice.providers.streaming_base import (
    StreamingSTTProvider,
    StreamingTTSProvider,
    pack_audio_frame_envelope,
    unpack_audio_frame_envelope,
)
from app.voice.realtime_models import (
    AudioCodec,
    AudioDirection,
    AudioFrameEnvelope,
    DEFAULT_SAMPLE_RATE_DOWNSTREAM,
    RealtimeErrorKind,
    RealtimeEventType,
    RealtimeErrorEvent,
    RealtimeSessionStatus,
    SessionEvent,
    TranscriptEvent,
    TranscriptLifecycleState,
    VisualDirectiveEvent,
    can_commit_to_canonical_message,
    validate_generation_and_sequence_fence,
)
from app.voice.realtime_session_manager import (
    LeaseExpiredError,
    RealtimeCallSessionManager,
    SessionClosedError,
    SessionNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/call", tags=["Call"])


class CreateCallSessionRequest(BaseModel):
    """Request DTO to initiate a realtime call session."""
    model_config = ConfigDict(extra="forbid")
    conversation_id: str = Field(..., min_length=1, description="Associated persistent conversation UUID")
    session_id: Optional[str] = Field(default=None, description="Optional client-suggested session UUID")


class CallSessionResponse(BaseModel):
    """Response DTO with active call session metadata."""
    model_config = ConfigDict(extra="forbid")
    session_id: str
    conversation_id: str
    status: RealtimeSessionStatus
    active_generation_id: int
    created_monotonic_at: float


@router.post("/sessions", response_model=CallSessionResponse)
async def create_call_session(
    payload: CreateCallSessionRequest,
    manager: RealtimeCallSessionManager = Depends(get_realtime_session_manager),
) -> CallSessionResponse:
    """Creates a new realtime call session bound to an existing persistent conversation."""
    session = manager.create_session(
        conversation_id=payload.conversation_id,
        session_id=payload.session_id,
    )

    # Wake up character if currently sleeping (incoming ringtone wakes her up)
    try:
        from app.db.session import async_session_factory
        from app.character.state_service import CharacterStateService
        async with async_session_factory() as db:
            state_svc = CharacterStateService(db)
            st = await state_svc.get_state("aevum")
            cur_act = (st.current_activity or "").lower()
            if any(k in cur_act for k in ("sleep", "night_sleep", "deep_sleep", "睡觉", "睡眠")):
                await state_svc.update_state("aevum", current_activity="接听夜间电话 (迷迷糊糊醒来)")
    except Exception as wake_err:
        logger.debug("Voice call wake transition skipped: %s", wake_err)

    return CallSessionResponse(
        session_id=session.session_id,
        conversation_id=session.conversation_id,
        status=session.status,
        active_generation_id=session.active_generation_id,
        created_monotonic_at=session.created_monotonic_at,
    )


@router.get("/sessions/{session_id}", response_model=CallSessionResponse)
async def get_call_session(
    session_id: str,
    manager: RealtimeCallSessionManager = Depends(get_realtime_session_manager),
) -> CallSessionResponse:
    """Retrieves metadata of an active or reconnecting call session."""
    session = manager.get_session(session_id)
    if not session:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Call session not found")
    return CallSessionResponse(
        session_id=session.session_id,
        conversation_id=session.conversation_id,
        status=session.status,
        active_generation_id=session.active_generation_id,
        created_monotonic_at=session.created_monotonic_at,
    )


@router.websocket("/stream/{session_id}")
async def call_stream_endpoint(
    websocket: WebSocket,
    session_id: str,
    conversation_id: Optional[str] = None,
    manager: RealtimeCallSessionManager = Depends(get_realtime_session_manager),
    stt_provider: StreamingSTTProvider = Depends(get_streaming_stt_provider),
    tts_provider: StreamingTTSProvider = Depends(get_streaming_tts_provider),
) -> None:
    """Full-duplex WebSocket stream gateway for realtime call control and media planes.

    Handles:
    - Control Plane: JSON signaling (Session lifecycle, barge-in, transcripts, visual directives).
    - Media Plane: Binary AudioFrameEnvelope packets with generation/sequence fencing.
    - Double-gated commitment into canonical conversation.
    """
    await websocket.accept()

    # Session Handshake & Identity Verification
    session = manager.get_session(session_id)
    if not session:
        if conversation_id:
            try:
                session = manager.create_session(conversation_id=conversation_id, session_id=session_id)
            except ValueError as e:
                await websocket.send_text(
                    RealtimeErrorEvent(
                        session_id=session_id,
                        error_kind=RealtimeErrorKind.INVALID_FRAME,
                        message=str(e),
                    ).model_dump_json()
                )
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
        else:
            await websocket.send_text(
                RealtimeErrorEvent(
                    session_id=session_id,
                    error_kind=RealtimeErrorKind.SESSION_EXPIRED,
                    message="Session not found and conversation_id not provided",
                ).model_dump_json()
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    # Check for reconnect vs new session
    if session.status == RealtimeSessionStatus.RECONNECTING:
        try:
            session = manager.reconnect_session(session_id)
            await websocket.send_text(
                SessionEvent(
                    event_type=RealtimeEventType.SESSION_RECONNECT,
                    session_id=session.session_id,
                    conversation_id=session.conversation_id,
                    status=session.status,
                    active_generation_id=session.active_generation_id,
                ).model_dump_json()
            )
        except LeaseExpiredError as e:
            await websocket.send_text(
                RealtimeErrorEvent(
                    session_id=session_id,
                    error_kind=RealtimeErrorKind.SESSION_EXPIRED,
                    message=str(e),
                    recoverable=False,
                ).model_dump_json()
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        except SessionClosedError as e:
            await websocket.send_text(
                RealtimeErrorEvent(
                    session_id=session_id,
                    error_kind=RealtimeErrorKind.SESSION_EXPIRED,
                    message=str(e),
                    recoverable=False,
                ).model_dump_json()
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    else:
        await websocket.send_text(
            SessionEvent(
                event_type=RealtimeEventType.SESSION_STARTED,
                session_id=session.session_id,
                conversation_id=session.conversation_id,
                status=session.status,
                active_generation_id=session.active_generation_id,
            ).model_dump_json()
        )

    expected_upstream_sequence_id = 0
    active_turn_id = f"turn-{session.active_generation_id}-0"

    try:
        while True:
            message = await websocket.receive()
            msg_type = message.get("type")

            if msg_type == "websocket.disconnect":
                break

            # ------------------------------------------------------------------
            # 1. Control Plane: Text Frames (JSON)
            # ------------------------------------------------------------------
            if "text" in message and message["text"]:
                raw_text = message["text"]
                try:
                    payload = json.loads(raw_text)
                    event_type = payload.get("event_type")

                    if event_type == RealtimeEventType.BARGE_IN.value:
                        client_ts = payload.get("client_latch_timestamp_ms", 0)
                        played_prefix = payload.get("played_prefix")
                        barge_evt, flush_evt = manager.handle_barge_in(
                            session_id=session_id,
                            client_latch_timestamp_ms=client_ts,
                            played_prefix=played_prefix,
                        )
                        # Reset sequence expectation for the new generation
                        expected_upstream_sequence_id = 0
                        # Send flush and mouth-clamp visual directive to client
                        await websocket.send_text(flush_evt.model_dump_json())
                        await websocket.send_text(
                            VisualDirectiveEvent(
                                session_id=session_id,
                                expression_archetype="listening_attentive",
                                intensity=100,
                                transition_duration_ms=50,
                                mouth_open_override=0.0,
                                is_speaking=False,
                            ).model_dump_json()
                        )

                    elif event_type == "END_UTTERANCE":
                        # Client indicates end-of-speech (e.g. manual PTT release or local VAD silence)
                        final_transcript = await stt_provider.end_utterance(session_id, active_turn_id)
                        if final_transcript:
                            await websocket.send_text(final_transcript.model_dump_json())
                            if can_commit_to_canonical_message(final_transcript):
                                manager.commit_user_transcript(session_id, final_transcript)

                    elif event_type == RealtimeEventType.SESSION_CLOSED.value:
                        manager.close_session(session_id)
                        await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
                        return

                    elif event_type == RealtimeEventType.HEARTBEAT.value:
                        await websocket.send_text(
                            json.dumps({"event_type": "HEARTBEAT_ACK", "session_id": session_id})
                        )

                except Exception as e:
                    logger.warning(f"Error parsing control frame: {e}")
                    await websocket.send_text(
                        RealtimeErrorEvent(
                            session_id=session_id,
                            error_kind=RealtimeErrorKind.INVALID_FRAME,
                            message=f"Invalid control frame: {e}",
                        ).model_dump_json()
                    )

            # ------------------------------------------------------------------
            # 2. Media Plane: Binary Audio Packets (AudioFrameEnvelope)
            # ------------------------------------------------------------------
            elif "bytes" in message and message["bytes"]:
                raw_bytes = message["bytes"]
                try:
                    envelope = unpack_audio_frame_envelope(raw_bytes)
                except Exception as e:
                    await websocket.send_text(
                        RealtimeErrorEvent(
                            session_id=session_id,
                            error_kind=RealtimeErrorKind.INVALID_FRAME,
                            message=f"Failed to unpack audio frame envelope: {e}",
                        ).model_dump_json()
                    )
                    continue

                # Lock 2: Generation & Sequence Fence
                is_valid, fence_reason = validate_generation_and_sequence_fence(
                    active_generation_id=session.active_generation_id,
                    expected_sequence_id=expected_upstream_sequence_id,
                    incoming_frame=envelope,
                )

                if not is_valid:
                    # Drop stale packet immediately without crash
                    if "STALE_GENERATION" in fence_reason or "STALE_SEQUENCE" in fence_reason:
                        await websocket.send_text(
                            RealtimeErrorEvent(
                                session_id=session_id,
                                error_kind=RealtimeErrorKind.GENERATION_FENCE_VIOLATION,
                                message=fence_reason,
                                affected_generation_id=envelope.generation_id,
                            ).model_dump_json()
                        )
                        continue

                # Advance sequence tracker; handle application-level sequence gap diagnostics
                if envelope.sequence_id > expected_upstream_sequence_id:
                    expected_upstream_sequence_id = envelope.sequence_id + 1
                    # Sequence gap detected in reliable stream (logged, not dropped)
                    await websocket.send_text(
                        RealtimeErrorEvent(
                            session_id=session_id,
                            error_kind=RealtimeErrorKind.SEQUENCE_GAP_DETECTED,
                            message=f"Sequence gap detected: got {envelope.sequence_id}, expected {expected_upstream_sequence_id - 1}",
                        ).model_dump_json()
                    )
                else:
                    expected_upstream_sequence_id = envelope.sequence_id + 1

                # Feed audio chunk to Streaming STT
                try:
                    async for transcript in stt_provider.feed_audio_chunk(envelope):
                        await websocket.send_text(transcript.model_dump_json())
                        # If transcript reaches COMMITTED, commit it idempotently
                        if can_commit_to_canonical_message(transcript):
                            manager.commit_user_transcript(session_id, transcript)
                except Exception as e:
                    # Lock 5: STT Failure -> Zero Fake Turn
                    error_evt = manager.handle_provider_error(
                        session_id=session_id,
                        error_kind=RealtimeErrorKind.STT_FAILURE,
                        message=f"Streaming STT engine error: {e}",
                    )
                    await websocket.send_text(error_evt.model_dump_json())

    except WebSocketDisconnect:
        # 13.3-C: Disconnection is a transport event, never manufacturing fake turns
        manager.disconnect_session(session_id, reason="client_disconnect")
    except Exception as e:
        logger.error(f"Unexpected streaming exception in call_stream: {e}")
        manager.disconnect_session(session_id, reason="stream_exception")
