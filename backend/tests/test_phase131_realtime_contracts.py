"""Unit tests and AST boundary verification for Phase 13.1 Realtime Protocol & State Contracts.

Validates ADR-024 (Revision 2):
- AudioFrameEnvelope encapsulation, generation/sequence fencing, and watchpoint compliance.
- DirectionalTurnState identity decoupling and asymmetric state progression.
- Three-state transcript lifecycle and double-gated commitment guards (Lock 3 & Lock 8).
- Instant Client-Local Barge-in and InterruptFlush contracts (Lock 4).
- Asymmetric provider failure decoupling and Zero Fake Turn guard (Lock 5).
- Presentation VisualDirective boundary isolation (Lock 1 & Lock 6).
- Strict static AST boundary compliance (zero DB, zero network, zero LLM, zero mutation tokens).
"""

import ast
from pathlib import Path
import pytest
from pydantic import ValidationError

from app.voice.realtime_models import (
    AudioCodec,
    AudioDirection,
    AudioFrameEnvelope,
    AssistantOutputState,
    BargeInEvent,
    DirectionalTurnState,
    InterruptFlushEvent,
    RealtimeErrorKind,
    RealtimeEventType,
    RealtimeErrorEvent,
    RealtimeSessionStatus,
    SessionEvent,
    TranscriptEvent,
    TranscriptLifecycleState,
    TurnEvent,
    UserInputState,
    VisualDirectiveEvent,
    can_commit_to_canonical_message,
    can_trigger_reality_construction,
    is_stt_failure_zero_fake_turn,
    validate_generation_and_sequence_fence,
    REALTIME_PROTOCOL_VERSION,
    REALTIME_SESSION_RECONNECT_LEASE_SECONDS,
    DEFAULT_SAMPLE_RATE_UPSTREAM,
    DEFAULT_SAMPLE_RATE_DOWNSTREAM,
    VAD_SILENCE_COMMIT_THRESHOLD_MS,
    BARGE_IN_ACCEPTANCE_TARGET_MS,
)


# ==============================================================================
# Cluster 1: AudioFrameEnvelope & Watchpoint Compliance (ADR-024 Lock 2 & Watchpoint)
# ==============================================================================

def test_audio_frame_envelope_valid_creation():
    """AudioFrameEnvelope instantiates cleanly with valid parameters."""
    env = AudioFrameEnvelope(
        session_id="session-101",
        generation_id=1,
        sequence_id=0,
        direction=AudioDirection.UPSTREAM_CLIENT_TO_SERVER,
        codec=AudioCodec.PCM_S16LE,
        sample_rate=DEFAULT_SAMPLE_RATE_UPSTREAM,
        stream_position_ms=0,
        payload=b"\x00\x01\x02\x03",
    )
    assert env.protocol_version == REALTIME_PROTOCOL_VERSION
    assert env.session_id == "session-101"
    assert env.generation_id == 1
    assert env.sequence_id == 0
    assert env.payload == b"\x00\x01\x02\x03"


def test_audio_frame_envelope_is_frozen():
    """AudioFrameEnvelope is immutable (frozen=True)."""
    env = AudioFrameEnvelope(
        session_id="session-101",
        generation_id=1,
        sequence_id=0,
        direction=AudioDirection.DOWNSTREAM_SERVER_TO_CLIENT,
        codec=AudioCodec.PCM_S16LE,
        sample_rate=DEFAULT_SAMPLE_RATE_DOWNSTREAM,
        payload=b"test",
    )
    with pytest.raises(ValidationError):
        env.generation_id = 2  # type: ignore


def test_audio_frame_envelope_forbids_extra_fields():
    """Watchpoint Compliance: AudioFrameEnvelope strictly forbids emotion, mood, or mind attributes."""
    with pytest.raises(ValidationError) as exc_info:
        AudioFrameEnvelope(
            session_id="session-101",
            generation_id=1,
            sequence_id=0,
            direction=AudioDirection.DOWNSTREAM_SERVER_TO_CLIENT,
            codec=AudioCodec.PCM_S16LE,
            sample_rate=24000,
            payload=b"test",
            emotion="HAPPY",  # Forbidden!
        )
    assert "extra_forbidden" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        AudioFrameEnvelope(
            session_id="session-101",
            generation_id=1,
            sequence_id=0,
            direction=AudioDirection.DOWNSTREAM_SERVER_TO_CLIENT,
            codec=AudioCodec.PCM_S16LE,
            sample_rate=24000,
            payload=b"test",
            character_state={"mood": "cheerful"},  # Forbidden!
        )
    assert "extra_forbidden" in str(exc_info.value)


def test_audio_frame_envelope_sample_rate_validation():
    """AudioFrameEnvelope validates standard audio sample rates."""
    with pytest.raises(ValidationError):
        AudioFrameEnvelope(
            session_id="session-101",
            generation_id=1,
            sequence_id=0,
            direction=AudioDirection.UPSTREAM_CLIENT_TO_SERVER,
            codec=AudioCodec.PCM_S16LE,
            sample_rate=12345,  # Unsupported rate
            payload=b"test",
        )


# ==============================================================================
# Cluster 2: Monotonic Generation & Sequence Fencing (ADR-024 Lock 2)
# ==============================================================================

def test_generation_fence_drops_stale_generation():
    """Audio chunks with generation_id < active_generation_id are unconditionally rejected."""
    incoming = AudioFrameEnvelope(
        session_id="session-101",
        generation_id=2,  # Stale!
        sequence_id=10,
        direction=AudioDirection.DOWNSTREAM_SERVER_TO_CLIENT,
        codec=AudioCodec.PCM_S16LE,
        sample_rate=24000,
        payload=b"audio",
    )
    is_valid, reason = validate_generation_and_sequence_fence(
        active_generation_id=3,
        expected_sequence_id=0,
        incoming_frame=incoming,
    )
    assert not is_valid
    assert "STALE_GENERATION" in reason


def test_sequence_fence_drops_stale_sequence():
    """Audio chunks with sequence_id < expected_sequence_id in current generation are dropped."""
    incoming = AudioFrameEnvelope(
        session_id="session-101",
        generation_id=3,
        sequence_id=4,  # Stale sequence!
        direction=AudioDirection.DOWNSTREAM_SERVER_TO_CLIENT,
        codec=AudioCodec.PCM_S16LE,
        sample_rate=24000,
        payload=b"audio",
    )
    is_valid, reason = validate_generation_and_sequence_fence(
        active_generation_id=3,
        expected_sequence_id=5,
        incoming_frame=incoming,
    )
    assert not is_valid
    assert "STALE_SEQUENCE" in reason


def test_fence_accepts_valid_current_or_future_frames():
    """Frames meeting or exceeding current generation and sequence are valid."""
    frame_in_seq = AudioFrameEnvelope(
        session_id="session-101",
        generation_id=3,
        sequence_id=5,
        direction=AudioDirection.DOWNSTREAM_SERVER_TO_CLIENT,
        codec=AudioCodec.PCM_S16LE,
        sample_rate=24000,
        payload=b"audio",
    )
    valid, reason = validate_generation_and_sequence_fence(3, 5, frame_in_seq)
    assert valid
    assert reason == "VALID"

    frame_new_gen = AudioFrameEnvelope(
        session_id="session-101",
        generation_id=4,
        sequence_id=0,
        direction=AudioDirection.DOWNSTREAM_SERVER_TO_CLIENT,
        codec=AudioCodec.PCM_S16LE,
        sample_rate=24000,
        payload=b"audio",
    )
    valid, reason = validate_generation_and_sequence_fence(3, 5, frame_new_gen)
    assert valid
    assert reason == "VALID"


# ==============================================================================
# Cluster 3: DirectionalTurnState & Domain Decoupling (ADR-024 Section 2.4)
# ==============================================================================

def test_directional_turn_state_valid():
    """DirectionalTurnState correctly stores decoupled user and assistant progress."""
    turn = DirectionalTurnState(
        turn_id="turn-001",
        session_id="session-101",
        conversation_id="conv-202",
        generation_id=1,
        user_input_state=UserInputState.COMMITTED,
        assistant_output_state=AssistantOutputState.STREAMING,
        created_monotonic_at=100.0,
        updated_monotonic_at=101.5,
    )
    assert turn.turn_id == "turn-001"
    assert turn.user_input_state == UserInputState.COMMITTED
    assert turn.assistant_output_state == AssistantOutputState.STREAMING


def test_directional_turn_state_asymmetric_barge_in():
    """Assistant output can be INTERRUPTED while user speech commits independently."""
    interrupted_turn = DirectionalTurnState(
        turn_id="turn-001",
        session_id="session-101",
        conversation_id="conv-202",
        generation_id=1,
        user_input_state=UserInputState.COMMITTED,
        assistant_output_state=AssistantOutputState.INTERRUPTED,
        created_monotonic_at=100.0,
        updated_monotonic_at=102.0,
    )
    assert interrupted_turn.assistant_output_state == AssistantOutputState.INTERRUPTED
    assert interrupted_turn.user_input_state == UserInputState.COMMITTED


def test_domain_identity_separation_enforced():
    """session_id != conversation_id != turn_id is strictly validated."""
    # session_id == conversation_id violation
    with pytest.raises(ValidationError) as exc:
        DirectionalTurnState(
            turn_id="turn-001",
            session_id="shared-id",
            conversation_id="shared-id",
            generation_id=1,
            created_monotonic_at=10.0,
            updated_monotonic_at=10.0,
        )
    assert "session_id must not equal conversation_id" in str(exc.value)

    # turn_id == conversation_id violation
    with pytest.raises(ValidationError) as exc:
        DirectionalTurnState(
            turn_id="shared-id",
            session_id="session-101",
            conversation_id="shared-id",
            generation_id=1,
            created_monotonic_at=10.0,
            updated_monotonic_at=10.0,
        )
    assert "turn_id must not equal conversation_id" in str(exc.value)

    # turn_id == session_id violation
    with pytest.raises(ValidationError) as exc:
        DirectionalTurnState(
            turn_id="shared-id",
            session_id="shared-id",
            conversation_id="conv-202",
            generation_id=1,
            created_monotonic_at=10.0,
            updated_monotonic_at=10.0,
        )
    assert "turn_id must not equal session_id" in str(exc.value)


# ==============================================================================
# Cluster 4: Transcript Lifecycle & Double-Gated Commitment (Lock 3 & Lock 8)
# ==============================================================================

def test_partial_transcript_cannot_commit_to_canonical_message():
    """PARTIAL transcript cannot be committed to Message (Lock 3)."""
    partial = TranscriptEvent(
        session_id="session-101",
        turn_id="turn-001",
        lifecycle_state=TranscriptLifecycleState.PARTIAL,
        text="Hello Aevum",
        is_final=False,
        utterance_boundary_confirmed=False,
    )
    assert not can_commit_to_canonical_message(partial)
    assert not can_trigger_reality_construction(partial)


def test_final_pending_commit_awaits_utterance_boundary():
    """FINAL_PENDING_COMMIT cannot commit without confirmed utterance boundary."""
    pending = TranscriptEvent(
        session_id="session-101",
        turn_id="turn-001",
        lifecycle_state=TranscriptLifecycleState.FINAL_PENDING_COMMIT,
        text="Hello Aevum, I think",
        is_final=True,
        utterance_boundary_confirmed=False,
    )
    assert not can_commit_to_canonical_message(pending)
    assert not can_trigger_reality_construction(pending)


def test_double_gated_committed_transcript_can_commit():
    """Transcript in COMMITTED state with confirmed boundary passes double gate."""
    committed = TranscriptEvent(
        session_id="session-101",
        turn_id="turn-001",
        lifecycle_state=TranscriptLifecycleState.COMMITTED,
        text="Hello Aevum, I have a question.",
        is_final=True,
        utterance_boundary_confirmed=True,
    )
    assert can_commit_to_canonical_message(committed)
    assert can_trigger_reality_construction(committed)


def test_empty_or_whitespace_transcript_cannot_commit():
    """Empty or whitespace-only transcript is rejected by commitment gate."""
    empty_transcript = TranscriptEvent(
        session_id="session-101",
        turn_id="turn-001",
        lifecycle_state=TranscriptLifecycleState.COMMITTED,
        text="   \n\t  ",
        is_final=True,
        utterance_boundary_confirmed=True,
    )
    assert not can_commit_to_canonical_message(empty_transcript)
    assert not can_trigger_reality_construction(empty_transcript)


# ==============================================================================
# Cluster 5: Barge-In, Reconnect Lease & Provider Decoupling (Locks 4 & 5)
# ==============================================================================

def test_barge_in_event_increments_generation():
    """BargeInEvent contains valid new and interrupted generation IDs."""
    barge = BargeInEvent(
        session_id="session-101",
        interrupted_turn_id="turn-001",
        interrupted_generation_id=1,
        new_generation_id=2,
        client_latch_timestamp_ms=172000000,
    )
    assert barge.new_generation_id > barge.interrupted_generation_id
    assert barge.event_type == RealtimeEventType.BARGE_IN


def test_interrupt_flush_event_structure():
    """InterruptFlushEvent specifies active generation to purge stale buffers."""
    flush = InterruptFlushEvent(
        session_id="session-101",
        generation_id=2,
        reason="user_barge_in",
    )
    assert flush.generation_id == 2
    assert flush.event_type == RealtimeEventType.INTERRUPT_FLUSH


def test_session_event_reconnection_lease_constant():
    """SessionEvent accommodates 30-second reconnect lease constant."""
    assert REALTIME_SESSION_RECONNECT_LEASE_SECONDS == 30
    session_evt = SessionEvent(
        event_type=RealtimeEventType.SESSION_RECONNECT,
        session_id="session-101",
        conversation_id="conv-202",
        status=RealtimeSessionStatus.RECONNECTING,
        active_generation_id=1,
        lease_expires_monotonic_at=130.0,
    )
    assert session_evt.status == RealtimeSessionStatus.RECONNECTING


def test_asymmetric_provider_failure_zero_fake_turn():
    """STT failure enforces Zero Fake Turn; TTS failure is distinct (Lock 5)."""
    stt_err = RealtimeErrorEvent(
        session_id="session-101",
        error_kind=RealtimeErrorKind.STT_FAILURE,
        message="STT provider stream disconnected",
    )
    assert is_stt_failure_zero_fake_turn(stt_err)

    tts_err = RealtimeErrorEvent(
        session_id="session-101",
        error_kind=RealtimeErrorKind.TTS_FAILURE,
        message="TTS synthesis timed out",
    )
    assert not is_stt_failure_zero_fake_turn(tts_err)


# ==============================================================================
# Cluster 6: VisualDirective & AST Boundary Audit (ADR-024 Lock 1, 6 & Rule 19)
# ==============================================================================

def test_visual_directive_presentation_only():
    """VisualDirectiveEvent carries only presentation parameters and clamps."""
    directive = VisualDirectiveEvent(
        session_id="session-101",
        expression_archetype="listening_attentive",
        intensity=90,
        transition_duration_ms=250,
        mouth_open_override=0.0,
        is_speaking=False,
    )
    assert directive.mouth_open_override == 0.0
    assert directive.intensity == 90
    assert directive.event_type == RealtimeEventType.VISUAL_DIRECTIVE


def test_ast_boundary_audit_realtime_models():
    """Static AST Audit verifying architectural isolation of realtime_models.py.

    Mandates:
    - 0 Database imports (SQLAlchemy, SQLite, Session)
    - 0 LLM provider imports (openai, anthropic, google)
    - 0 Network request imports (requests, httpx, aiohttp)
    - 0 Mutation authority tokens (PromotionAuthorizationToken, set_fact)
    """
    models_path = Path(__file__).parent.parent / "app" / "voice" / "realtime_models.py"
    assert models_path.exists(), f"File not found: {models_path}"

    with open(models_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=str(models_path))

    forbidden_imports = {
        "sqlalchemy",
        "sqlite3",
        "openai",
        "anthropic",
        "google.genai",
        "requests",
        "httpx",
        "aiohttp",
        "socket",
    }
    forbidden_tokens = {
        "PromotionAuthorizationToken",
        "set_fact",
        "BiographyPromotionService",
        "SharedHistoryService",
        "RealityOrchestrationService",
    }

    found_violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for forbidden in forbidden_imports:
                    if alias.name == forbidden or alias.name.startswith(f"{forbidden}."):
                        found_violations.append(f"Forbidden import: {alias.name} at line {node.lineno}")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for forbidden in forbidden_imports:
                    if node.module == forbidden or node.module.startswith(f"{forbidden}."):
                        found_violations.append(f"Forbidden from-import: {node.module} at line {node.lineno}")
        elif isinstance(node, ast.Name):
            if node.id in forbidden_tokens:
                found_violations.append(f"Forbidden token reference: {node.id} at line {node.lineno}")

    assert not found_violations, f"AST boundary violations detected: {found_violations}"
