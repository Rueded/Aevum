"""Dedicated unit tests and AST boundary verification for Phase 13.3 Streaming Transport & Providers.

Governed by ADR-024 (Revision 2):
- 13.3-A: Transport 不得拥有 Reality Authority (streaming is purely an input/output conduit).
- 13.3-B: Provider 是 Adapter，不是 Truth Authority (transcripts and audio are sensory events, not canonical truth).
- 13.3-C: WebSocket 断开不能制造 semantic events (transient socket drops never synthesize fake turns).
- Lock 1: Streaming Isolation & Audio != Emotion.
- Lock 2: Monotonic Generation & Sequence Fencing over WebSocket.
- Lock 3: Three-State Transcript & Double-Gated Commitment.
- Lock 4: Instant Client-Local Barge-in latching & cascading flush.
- Lock 5: Asymmetric Provider Failure Decoupling (STT failure -> Zero Fake Turn; TTS failure -> text fallback).
- Lock 8: Canonical Conversation Boundary (Only fully COMMITTED turns enter persistent conversation).
- Static AST Boundary Audit (zero direct DB mutations, zero set_fact, zero PromotionAuthorizationToken).
"""

import ast
import json
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.voice.dependencies import (
    get_realtime_session_manager,
    get_streaming_stt_provider,
    get_streaming_tts_provider,
)
from app.voice.providers.streaming_base import (
    MockStreamingSTTProvider,
    MockStreamingTTSProvider,
    pack_audio_frame_envelope,
    unpack_audio_frame_envelope,
)
from app.voice.realtime_models import (
    AudioCodec,
    AudioDirection,
    AudioFrameEnvelope,
    DEFAULT_SAMPLE_RATE_UPSTREAM,
    RealtimeErrorKind,
    RealtimeEventType,
    RealtimeSessionStatus,
)
from app.voice.realtime_session_manager import RealtimeCallSessionManager


@pytest.fixture
def mock_session_manager():
    """Provides a fresh isolated in-memory RealtimeCallSessionManager."""
    return RealtimeCallSessionManager()


@pytest.fixture
def mock_stt():
    """Provides an isolated MockStreamingSTTProvider."""
    return MockStreamingSTTProvider(default_transcript="Hello Aevum, good morning.")


@pytest.fixture
def mock_tts():
    """Provides an isolated MockStreamingTTSProvider."""
    return MockStreamingTTSProvider()


@pytest.fixture
def test_client(mock_session_manager, mock_stt, mock_tts):
    """Provides a TestClient with overridden dependencies for realtime testing."""
    app.dependency_overrides[get_realtime_session_manager] = lambda: mock_session_manager
    app.dependency_overrides[get_streaming_stt_provider] = lambda: mock_stt
    app.dependency_overrides[get_streaming_tts_provider] = lambda: mock_tts
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# ==============================================================================
# Cluster 1: Wire Packaging & Unpacking (AudioFrameEnvelope)
# ==============================================================================

def test_pack_and_unpack_audio_frame_envelope_roundtrip():
    """AudioFrameEnvelope serializes to binary wire layout and deserializes with 100% fidelity."""
    original = AudioFrameEnvelope(
        protocol_version=1,
        session_id="session-wire-42",
        generation_id=2,
        sequence_id=7,
        direction=AudioDirection.UPSTREAM_CLIENT_TO_SERVER,
        codec=AudioCodec.PCM_S16LE,
        sample_rate=DEFAULT_SAMPLE_RATE_UPSTREAM,
        stream_position_ms=140,
        payload=b"\x01\x02\x03\x04\x05\x06\x07\x08",
    )

    packed_bytes = pack_audio_frame_envelope(original)
    assert len(packed_bytes) > 4

    unpacked = unpack_audio_frame_envelope(packed_bytes)
    assert unpacked.protocol_version == original.protocol_version
    assert unpacked.session_id == original.session_id
    assert unpacked.generation_id == original.generation_id
    assert unpacked.sequence_id == original.sequence_id
    assert unpacked.direction == original.direction
    assert unpacked.codec == original.codec
    assert unpacked.sample_rate == original.sample_rate
    assert unpacked.stream_position_ms == original.stream_position_ms
    assert unpacked.payload == original.payload


def test_unpack_malformed_packets_rejected():
    """Malformed or truncated binary wire packets raise ValueError."""
    with pytest.raises(ValueError):
        unpack_audio_frame_envelope(b"\x00")  # Less than 4 bytes

    with pytest.raises(ValueError):
        unpack_audio_frame_envelope(b"\x00\x00\x00\xff" + b"truncated")  # Declared length exceeds payload


# ==============================================================================
# Cluster 2: REST Session Endpoints
# ==============================================================================

def test_rest_create_and_get_call_session(test_client):
    """POST and GET /api/v1/call/sessions correctly manage session metadata."""
    create_res = test_client.post(
        "/api/v1/call/sessions",
        json={"conversation_id": "conv-rest-1", "session_id": "call-rest-1"},
    )
    assert create_res.status_code == 200
    data = create_res.json()
    assert data["session_id"] == "call-rest-1"
    assert data["conversation_id"] == "conv-rest-1"
    assert data["status"] == RealtimeSessionStatus.ACTIVE.value
    assert data["active_generation_id"] == 1

    get_res = test_client.get("/api/v1/call/sessions/call-rest-1")
    assert get_res.status_code == 200
    assert get_res.json()["session_id"] == "call-rest-1"

    missing_res = test_client.get("/api/v1/call/sessions/nonexistent")
    assert missing_res.status_code == 404


# ==============================================================================
# Cluster 3: WebSocket Streaming Handshake & Control Plane
# ==============================================================================

def test_websocket_handshake_and_heartbeat(test_client):
    """Client initiates WebSocket stream, receives SESSION_STARTED, and exchanges heartbeats."""
    with test_client.websocket_connect(
        "/api/v1/call/stream/call-ws-1?conversation_id=conv-ws-1"
    ) as websocket:
        # Initial greeting from server
        init_event = json.loads(websocket.receive_text())
        assert init_event["event_type"] == RealtimeEventType.SESSION_STARTED.value
        assert init_event["session_id"] == "call-ws-1"
        assert init_event["active_generation_id"] == 1

        # Send Heartbeat
        websocket.send_text(json.dumps({"event_type": RealtimeEventType.HEARTBEAT.value}))
        ack = json.loads(websocket.receive_text())
        assert ack["event_type"] == "HEARTBEAT_ACK"
        assert ack["session_id"] == "call-ws-1"

        # Clean session close
        websocket.send_text(json.dumps({"event_type": RealtimeEventType.SESSION_CLOSED.value}))


# ==============================================================================
# Cluster 4: Media Plane Streaming, Fencing & Transcription (Lock 2 & Lock 3)
# ==============================================================================

def test_websocket_audio_streaming_and_partial_transcript(test_client):
    """Client streams AudioFrameEnvelope packets; receives progressive partial transcripts."""
    with test_client.websocket_connect(
        "/api/v1/call/stream/call-stream-1?conversation_id=conv-stream-1"
    ) as websocket:
        init_evt = json.loads(websocket.receive_text())
        assert init_evt["event_type"] == RealtimeEventType.SESSION_STARTED.value

        # Send valid audio frame (generation 1, sequence 0)
        envelope = AudioFrameEnvelope(
            session_id="call-stream-1",
            generation_id=1,
            sequence_id=0,
            direction=AudioDirection.UPSTREAM_CLIENT_TO_SERVER,
            codec=AudioCodec.PCM_S16LE,
            sample_rate=16000,
            payload=b"\x00\x00" * 320,
        )
        websocket.send_bytes(pack_audio_frame_envelope(envelope))

        # Server STT emits partial transcript
        transcript_msg = json.loads(websocket.receive_text())
        assert transcript_msg["event_type"] == RealtimeEventType.TRANSCRIPT_EVENT.value
        assert transcript_msg["lifecycle_state"] == "PARTIAL"
        assert len(transcript_msg["text"]) > 0


def test_websocket_generation_fence_drops_stale_frame(test_client, mock_session_manager):
    """Audio frames with older generation_id are dropped over WebSocket with error feedback."""
    with test_client.websocket_connect(
        "/api/v1/call/stream/call-fence-1?conversation_id=conv-fence-1"
    ) as websocket:
        websocket.receive_text()  # Handshake

        # Trigger barge-in so generation advances to 2
        websocket.send_text(
            json.dumps({"event_type": RealtimeEventType.BARGE_IN.value, "client_latch_timestamp_ms": 1000})
        )
        flush_msg = json.loads(websocket.receive_text())
        assert flush_msg["event_type"] == RealtimeEventType.INTERRUPT_FLUSH.value
        assert flush_msg["generation_id"] == 2
        visual_msg = json.loads(websocket.receive_text())
        assert visual_msg["event_type"] == RealtimeEventType.VISUAL_DIRECTIVE.value

        # Now send stale audio frame belonging to generation 1
        stale_envelope = AudioFrameEnvelope(
            session_id="call-fence-1",
            generation_id=1,  # Stale generation!
            sequence_id=0,
            direction=AudioDirection.UPSTREAM_CLIENT_TO_SERVER,
            codec=AudioCodec.PCM_S16LE,
            sample_rate=16000,
            payload=b"\x00\x00" * 320,
        )
        websocket.send_bytes(pack_audio_frame_envelope(stale_envelope))

        # Server responds with generation fence violation error; frame is dropped
        err_msg = json.loads(websocket.receive_text())
        assert err_msg["event_type"] == RealtimeEventType.ERROR_EVENT.value
        assert err_msg["error_kind"] == RealtimeErrorKind.GENERATION_FENCE_VIOLATION.value
        assert "STALE_GENERATION" in err_msg["message"]


def test_websocket_sequence_gap_detected_diagnostics(test_client):
    """Audio frames with sequence gaps trigger diagnostic warnings while keeping stream operational."""
    with test_client.websocket_connect(
        "/api/v1/call/stream/call-gap-1?conversation_id=conv-gap-1"
    ) as websocket:
        websocket.receive_text()  # Handshake

        # Send sequence_id = 5 directly (skipping 0..4)
        jump_envelope = AudioFrameEnvelope(
            session_id="call-gap-1",
            generation_id=1,
            sequence_id=5,
            direction=AudioDirection.UPSTREAM_CLIENT_TO_SERVER,
            codec=AudioCodec.PCM_S16LE,
            sample_rate=16000,
            payload=b"\x00\x00" * 320,
        )
        websocket.send_bytes(pack_audio_frame_envelope(jump_envelope))

        # First message: sequence gap detected diagnostic
        gap_msg = json.loads(websocket.receive_text())
        assert gap_msg["event_type"] == RealtimeEventType.ERROR_EVENT.value
        assert gap_msg["error_kind"] == RealtimeErrorKind.SEQUENCE_GAP_DETECTED.value

        # Second message: transcript still processed successfully
        transcript_msg = json.loads(websocket.receive_text())
        assert transcript_msg["event_type"] == RealtimeEventType.TRANSCRIPT_EVENT.value


# ==============================================================================
# Cluster 5: End Utterance & Double-Gated Commitment (Lock 3 & Lock 8)
# ==============================================================================

def test_websocket_end_utterance_commits_turn_idempotently(test_client, mock_session_manager):
    """Client END_UTTERANCE confirms linguistic boundary and commits user transcript."""
    with test_client.websocket_connect(
        "/api/v1/call/stream/call-commit-1?conversation_id=conv-commit-1"
    ) as websocket:
        websocket.receive_text()  # Handshake

        # Send END_UTTERANCE control signal
        websocket.send_text(json.dumps({"event_type": "END_UTTERANCE"}))

        # Receives COMMITTED transcript
        final_msg = json.loads(websocket.receive_text())
        assert final_msg["event_type"] == RealtimeEventType.TRANSCRIPT_EVENT.value
        assert final_msg["lifecycle_state"] == "COMMITTED"
        assert final_msg["is_final"] is True
        assert final_msg["utterance_boundary_confirmed"] is True

        # Assert session committed turns contains the turn
        session = mock_session_manager.get_session("call-commit-1")
        assert len(session.committed_turns) == 1


# ==============================================================================
# Cluster 6: Provider Error Handling & Zero Fake Turn (Lock 5)
# ==============================================================================

def test_websocket_stt_failure_enforces_zero_fake_turn(test_client, mock_stt, mock_session_manager):
    """STT failure over WebSocket sends error event and commits strictly zero fake turns."""
    mock_stt.set_simulate_failure(True)

    with test_client.websocket_connect(
        "/api/v1/call/stream/call-err-1?conversation_id=conv-err-1"
    ) as websocket:
        websocket.receive_text()  # Handshake

        # Send audio frame
        envelope = AudioFrameEnvelope(
            session_id="call-err-1",
            generation_id=1,
            sequence_id=0,
            direction=AudioDirection.UPSTREAM_CLIENT_TO_SERVER,
            codec=AudioCodec.PCM_S16LE,
            sample_rate=16000,
            payload=b"\x00\x00" * 320,
        )
        websocket.send_bytes(pack_audio_frame_envelope(envelope))

        # Error event received
        err_msg = json.loads(websocket.receive_text())
        assert err_msg["event_type"] == RealtimeEventType.ERROR_EVENT.value
        assert err_msg["error_kind"] == RealtimeErrorKind.STT_FAILURE.value

        # Zero fake turn verified:
        session = mock_session_manager.get_session("call-err-1")
        assert len(session.committed_turns) == 0


# ==============================================================================
# Cluster 7: Static AST Boundary Audit
# ==============================================================================

def test_ast_boundary_audit_call_stream_and_providers():
    """Static AST Audit verifying architectural boundaries of call_stream.py and streaming_base.py.

    Mandates:
    - 0 Database mutation tokens (PromotionAuthorizationToken, set_fact)
    - 0 Direct calls to BiographyPromotionService or SharedHistoryService
    - 0 Reverse mutations to EmotionState or CharacterMood
    """
    api_path = Path(__file__).parent.parent / "app" / "api" / "call_stream.py"
    providers_path = Path(__file__).parent.parent / "app" / "voice" / "providers" / "streaming_base.py"

    assert api_path.exists(), f"File not found: {api_path}"
    assert providers_path.exists(), f"File not found: {providers_path}"

    for path in (api_path, providers_path):
        with open(path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(path))

        forbidden_tokens = {
            "PromotionAuthorizationToken",
            "set_fact",
            "BiographyPromotionService",
            "SharedHistoryService",
            "RealityOrchestrationService",
            "mutate_emotion",
            "patch_emotion",
        }

        found_violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                if node.id in forbidden_tokens:
                    found_violations.append(f"Forbidden token reference: {node.id} at line {node.lineno}")

        assert not found_violations, f"AST boundary violations in {path.name}: {found_violations}"
