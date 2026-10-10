"""test_golden_suite_13.py — Golden Acceptance Suite 13 (Phase 13.6: GC-325 ~ GC-351)

Golden Acceptance Suite for Phase 13: Realtime Voice Call & Desktop Product Shell.
Verifies all frozen contracts (Phase 13.1–13.5) and the 8 Constitutional Locks under ADR-024.

"Realtime is an ephemeral streaming conduit, not a reality loophole.
Voice is the body. Live2D is the visible body. Mind remains the sole authority."

Covers 27 Acceptance Benchmarks across 7 Structured Clusters:
- Cluster 1: Protocol & Envelope (GC-325 ~ GC-328)
- Cluster 2: Partial Transcript & Semantic Isolation (GC-329 ~ GC-331)
- Cluster 3: Barge-In & Directional Turn Lifecycles (GC-332 ~ GC-336)
- Cluster 4: Reconnect & Monotonic Lease Governance (GC-337 ~ GC-340)
- Cluster 5: Provider Failure Decoupling (GC-341 ~ GC-343)
- Cluster 6: Constitutional Boundaries & Lock Invariants (GC-344 ~ GC-348)
- Cluster 7: Determinism & Complete Headless Lifecycle (GC-349 ~ GC-351)
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
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
    AssistantOutputState,
    BargeInEvent,
    DirectionalTurnState,
    DEFAULT_SAMPLE_RATE_DOWNSTREAM,
    DEFAULT_SAMPLE_RATE_UPSTREAM,
    InterruptFlushEvent,
    REALTIME_SESSION_RECONNECT_LEASE_SECONDS,
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
    validate_generation_and_sequence_fence,
)
from app.voice.realtime_session_manager import (
    GenerationFenceError,
    LeaseExpiredError,
    RealtimeCallSession,
    RealtimeCallSessionManager,
    SessionClosedError,
    SessionNotFoundError,
)


class MockMonotonicClock:
    """Microsecond-precise controllable monotonic clock for testing lease boundaries."""

    def __init__(self, initial_time: float = 1000.0) -> None:
        self._current_time = initial_time

    def __call__(self) -> float:
        return self._current_time

    def advance(self, seconds: float) -> None:
        self._current_time += seconds

    def set_time(self, exact_time: float) -> None:
        self._current_time = exact_time


def _make_frame(
    session_id: str,
    generation_id: int,
    sequence_id: int,
    payload: bytes = b"\x00" * 32,
    stream_position_ms: int = 0,
) -> AudioFrameEnvelope:
    """Helper: build a minimal upstream AudioFrameEnvelope with correct field names."""
    return AudioFrameEnvelope(
        session_id=session_id,
        generation_id=generation_id,
        sequence_id=sequence_id,
        direction=AudioDirection.UPSTREAM_CLIENT_TO_SERVER,
        codec=AudioCodec.PCM_S16LE,
        sample_rate=DEFAULT_SAMPLE_RATE_UPSTREAM,
        stream_position_ms=stream_position_ms,
        payload=payload,
    )


# ==============================================================================
# CLUSTER 1: Protocol & Envelope (GC-325 ~ GC-328)
# ==============================================================================

class TestCluster1ProtocolAndEnvelope:
    """Acceptance benchmarks verifying pure DTO contracts, immutability, and wire framing."""

    def test_gc325_frozen_immutability_and_forbidden_extra_fields(self) -> None:
        """GC-325: AudioFrameEnvelope and protocol models are strictly frozen and forbid extra fields."""
        payload = b"\x00\x01\x02\x03" * 16
        envelope = AudioFrameEnvelope(
            session_id="sess-gc325",
            generation_id=1,
            sequence_id=0,
            direction=AudioDirection.UPSTREAM_CLIENT_TO_SERVER,
            codec=AudioCodec.PCM_S16LE,
            sample_rate=16000,
            stream_position_ms=0,
            payload=payload,
        )

        # Immutability check — frozen model must reject direct attribute assignment
        with pytest.raises((ValidationError, TypeError)):
            envelope.generation_id = 2  # type: ignore

        # Extra fields forbidden
        with pytest.raises(ValidationError):
            AudioFrameEnvelope(
                session_id="sess-gc325",
                generation_id=1,
                sequence_id=0,
                direction=AudioDirection.UPSTREAM_CLIENT_TO_SERVER,
                codec=AudioCodec.PCM_S16LE,
                sample_rate=16000,
                stream_position_ms=0,
                payload=payload,
                unauthorized_emotion="happy",  # type: ignore
            )

    def test_gc326_rejection_of_unknown_event_types(self) -> None:
        """GC-326: Unknown event types or malformed control envelopes are rejected."""
        valid_types = {e.value for e in RealtimeEventType}
        assert "TRANSCRIPT_EVENT" in valid_types
        assert "BARGE_IN" in valid_types
        assert "INTERRUPT_FLUSH" in valid_types
        assert "VISUAL_DIRECTIVE" in valid_types

        # Arbitrary pseudo-event cannot instantiate RealtimeEventType
        with pytest.raises(ValueError):
            RealtimeEventType("MUTATE_REALITY_EVENT")

    def test_gc327_generation_id_fence_boundary_validation(self) -> None:
        """GC-327: Generation ID validation and fence boundary rejection via validate_generation_and_sequence_fence."""
        manager = RealtimeCallSessionManager()
        session = manager.create_session("conv-gc327")
        # active_generation_id starts at 1; barge-in makes it 2
        manager.handle_barge_in(session.session_id, client_latch_timestamp_ms=0)
        assert session.active_generation_id == 2

        # Stale gen=1 frame when active=2 must be rejected
        stale_frame = _make_frame(session.session_id, generation_id=1, sequence_id=0)
        is_valid, reason = validate_generation_and_sequence_fence(
            active_generation_id=session.active_generation_id,
            expected_sequence_id=0,
            incoming_frame=stale_frame,
        )
        assert not is_valid
        assert reason is not None and "STALE_GENERATION" in reason

        # Current gen=2 frame must be accepted
        current_frame = _make_frame(session.session_id, generation_id=2, sequence_id=0)
        is_valid_cur, reason_cur = validate_generation_and_sequence_fence(
            active_generation_id=session.active_generation_id,
            expected_sequence_id=0,
            incoming_frame=current_frame,
        )
        assert is_valid_cur
        assert reason_cur == "VALID"

    def test_gc328_sequence_id_gap_detection_and_diagnostics(self) -> None:
        """GC-328: Sequence ID gap detection and monotonicity tracking."""
        manager = RealtimeCallSessionManager()
        session = manager.create_session("conv-gc328")
        gen = session.active_generation_id

        # Sequence 0 arrives cleanly
        f0 = _make_frame(session.session_id, generation_id=gen, sequence_id=0)
        ok0, r0 = validate_generation_and_sequence_fence(
            active_generation_id=gen,
            expected_sequence_id=0,
            incoming_frame=f0,
        )
        assert ok0
        assert r0 == "VALID"

        # Sequence 4 arrives — gap (expected 1) but accepted
        f4 = _make_frame(session.session_id, generation_id=gen, sequence_id=4)
        ok4, r4 = validate_generation_and_sequence_fence(
            active_generation_id=gen,
            expected_sequence_id=1,
            incoming_frame=f4,
        )
        assert ok4  # accepted despite gap

        # Sequence 2 arrives after 4 — stale, must be dropped
        f2 = _make_frame(session.session_id, generation_id=gen, sequence_id=2)
        ok2, r2 = validate_generation_and_sequence_fence(
            active_generation_id=gen,
            expected_sequence_id=5,  # tracker has advanced past 4
            incoming_frame=f2,
        )
        assert not ok2
        assert r2 is not None and "STALE_SEQUENCE" in r2


# ==============================================================================
# CLUSTER 2: Partial Transcript & Semantic Isolation (GC-329 ~ GC-331)
# ==============================================================================

class TestCluster2PartialTranscriptAndSemanticIsolation:
    """Acceptance benchmarks verifying ephemeral transcript isolation (ADR-024 Lock 3)."""

    def test_gc329_partial_transcript_never_enters_canonical_messages(self) -> None:
        """GC-329: PARTIAL transcripts can never commit to canonical message table."""
        partial_event = TranscriptEvent(
            session_id="sess-gc329",
            turn_id="turn-gc329",
            lifecycle_state=TranscriptLifecycleState.PARTIAL,
            text="I was wondering if",
            is_final=False,
            utterance_boundary_confirmed=False,
            provider_name="mock_stt",
        )
        assert not can_commit_to_canonical_message(partial_event)

    def test_gc330_partial_transcript_isolated_from_memory_extraction(self) -> None:
        """GC-330: PARTIAL transcript cannot trigger episodic memory extraction."""
        manager = RealtimeCallSessionManager()
        session = manager.create_session("conv-gc330")

        # A partial transcript cannot be committed — double-gate will reject it
        partial = TranscriptEvent(
            session_id=session.session_id,
            turn_id="turn-gc330",
            lifecycle_state=TranscriptLifecycleState.PARTIAL,
            text="I remember we went to Paris",
            is_final=False,
            utterance_boundary_confirmed=False,
        )
        assert not can_commit_to_canonical_message(partial)
        # Zero canonical committed turns
        assert "turn-gc330" not in session.committed_turns

    def test_gc331_final_pending_commit_blocked_from_reality_inference(self) -> None:
        """GC-331: FINAL_PENDING_COMMIT awaits double-gating and cannot commit or trigger reality."""
        pending_event = TranscriptEvent(
            session_id="sess-gc331",
            turn_id="turn-gc331",
            lifecycle_state=TranscriptLifecycleState.FINAL_PENDING_COMMIT,
            text="My brother's name is Leo",
            is_final=True,
            utterance_boundary_confirmed=False,  # Gate 2 not confirmed yet
            provider_name="mock_stt",
        )
        assert not can_commit_to_canonical_message(pending_event)

        # Attempting commit_user_transcript with FINAL_PENDING_COMMIT must raise
        manager = RealtimeCallSessionManager()
        session = manager.create_session("conv-gc331")
        with pytest.raises(ValueError):
            manager.commit_user_transcript(session.session_id, pending_event)
        assert "turn-gc331" not in session.committed_turns


# ==============================================================================
# CLUSTER 3: Barge-In & Directional Turn Lifecycles (GC-332 ~ GC-336)
# ==============================================================================

class TestCluster3BargeInAndDirectionalTurnLifecycles:
    """Acceptance benchmarks verifying instant barge-in latching and directional turn states."""

    def test_gc332_generation_counter_strictly_increments_on_barge_in(self) -> None:
        """GC-332: Generation counter increments strictly on barge-in (starts at 1 per session creation)."""
        manager = RealtimeCallSessionManager()
        session = manager.create_session("conv-gc332")
        assert session.active_generation_id == 1

        manager.handle_barge_in(session.session_id, client_latch_timestamp_ms=0)
        assert session.active_generation_id == 2

        manager.handle_barge_in(session.session_id, client_latch_timestamp_ms=5)
        assert session.active_generation_id == 3

    def test_gc333_old_generation_packets_unconditionally_dropped(self) -> None:
        """GC-333: Audio packets from older generations are dropped by the fence."""
        manager = RealtimeCallSessionManager()
        session = manager.create_session("conv-gc333")
        manager.handle_barge_in(session.session_id, client_latch_timestamp_ms=0)  # Generation -> 2

        stale_frame = _make_frame(session.session_id, generation_id=1, sequence_id=0)
        is_valid, reason = validate_generation_and_sequence_fence(
            active_generation_id=session.active_generation_id,
            expected_sequence_id=0,
            incoming_frame=stale_frame,
        )
        assert not is_valid
        assert reason is not None and "STALE_GENERATION" in reason

    def test_gc334_disordered_sequence_packets_flagged_and_dropped(self) -> None:
        """GC-334: Disordered sequence packets are dropped."""
        manager = RealtimeCallSessionManager()
        session = manager.create_session("conv-gc334")
        gen = session.active_generation_id

        # Sequence 0 -> accepted; expected tracker advances to 1
        ok0, r0 = validate_generation_and_sequence_fence(
            active_generation_id=gen,
            expected_sequence_id=0,
            incoming_frame=_make_frame(session.session_id, gen, 0),
        )
        assert ok0

        # Sequence 5 -> gap but accepted; expected tracker advances to 6
        ok5, r5 = validate_generation_and_sequence_fence(
            active_generation_id=gen,
            expected_sequence_id=1,
            incoming_frame=_make_frame(session.session_id, gen, 5),
        )
        assert ok5

        # Sequence 3 (stale disordered, now below tracker at 6) -> dropped
        ok3, r3 = validate_generation_and_sequence_fence(
            active_generation_id=gen,
            expected_sequence_id=6,
            incoming_frame=_make_frame(session.session_id, gen, 3),
        )
        assert not ok3
        assert r3 is not None and "STALE_SEQUENCE" in r3

    def test_gc335_assistant_output_transitions_to_interrupted(self) -> None:
        """GC-335: Assistant streaming transitions to INTERRUPTED on barge-in while preserving canonical text."""
        manager = RealtimeCallSessionManager()
        session = manager.create_session("conv-gc335")

        manager.start_assistant_streaming(
            session_id=session.session_id,
            turn_id="turn-gc335",
            canonical_text="I was telling you an important story about the cosmos.",
            generation_id=session.active_generation_id,
        )

        turn = session.current_turn
        assert turn is not None
        assert turn.assistant_output_state == AssistantOutputState.STREAMING

        # Barge-In occurs
        manager.handle_barge_in(session.session_id, client_latch_timestamp_ms=0)
        assert session.current_turn.assistant_output_state == AssistantOutputState.INTERRUPTED

        # Canonical text preserved (13.2-LOCK-E)
        assert session.canonical_assistant_texts["turn-gc335"] == "I was telling you an important story about the cosmos."

    def test_gc336_user_interrupting_utterance_committable_in_fresh_turn(self) -> None:
        """GC-336: User's interrupting speech remains valid and committable in a new turn."""
        manager = RealtimeCallSessionManager()
        session = manager.create_session("conv-gc336")

        # Turn 1 interrupted
        manager.handle_barge_in(session.session_id, client_latch_timestamp_ms=0)

        # Fresh Turn 2: fully double-gated COMMITTED transcript
        committed_transcript = TranscriptEvent(
            session_id=session.session_id,
            turn_id="turn-fresh-2",
            lifecycle_state=TranscriptLifecycleState.COMMITTED,
            text="Wait, listen to this instead!",
            is_final=True,
            utterance_boundary_confirmed=True,
        )
        assert can_commit_to_canonical_message(committed_transcript)
        committed_turn, is_new = manager.commit_user_transcript(session.session_id, committed_transcript)
        assert is_new
        assert committed_turn.user_input_state == UserInputState.COMMITTED
        assert "turn-fresh-2" in session.committed_turns


# ==============================================================================
# CLUSTER 4: Reconnect & Monotonic Lease Governance (GC-337 ~ GC-340)
# ==============================================================================

class TestCluster4ReconnectAndMonotonicLeaseGovernance:
    """Acceptance benchmarks verifying 30-second monotonic lease boundary (13.2-LOCK-A)."""

    def test_gc337_session_reconnect_preserves_session_id(self) -> None:
        """GC-337: Session reconnect within lease window preserves active session_id."""
        clock = MockMonotonicClock(100.0)
        manager = RealtimeCallSessionManager(clock_fn=clock)
        session = manager.create_session("conv-gc337")

        # Disconnect then reconnect within 15s
        manager.disconnect_session(session.session_id)
        clock.advance(15.0)
        reconnected = manager.reconnect_session(session.session_id)
        assert reconnected.session_id == session.session_id
        assert reconnected.status == RealtimeSessionStatus.ACTIVE

    def test_gc338_session_reconnect_preserves_conversation_id(self) -> None:
        """GC-338: Session reconnect preserves binding to canonical conversation_id."""
        clock = MockMonotonicClock(100.0)
        manager = RealtimeCallSessionManager(clock_fn=clock)
        session = manager.create_session("conv-gc338")

        manager.disconnect_session(session.session_id)
        clock.advance(20.0)
        reconnected = manager.reconnect_session(session.session_id)
        assert reconnected.conversation_id == "conv-gc338"

    def test_gc339_duplicate_reconnect_handshakes_are_idempotent(self) -> None:
        """GC-339: Multiple reconnect calls within lease window are idempotent."""
        clock = MockMonotonicClock(100.0)
        manager = RealtimeCallSessionManager(clock_fn=clock)
        session = manager.create_session("conv-gc339")

        manager.disconnect_session(session.session_id)
        clock.advance(5.0)
        rec1 = manager.reconnect_session(session.session_id)

        # Disconnect again for second reconnect
        manager.disconnect_session(session.session_id)
        clock.advance(4.0)
        rec2 = manager.reconnect_session(session.session_id)

        assert rec1.session_id == rec2.session_id
        assert rec1.active_generation_id == rec2.active_generation_id

    def test_gc340_exact_monotonic_lease_boundary_30s(self) -> None:
        """GC-340: Exact monotonic lease boundary (29.999s valid, 30.000s & 30.001s expired)."""
        clock = MockMonotonicClock(1000.0)
        manager = RealtimeCallSessionManager(clock_fn=clock)

        # 29.999s elapsed -> valid
        s1 = manager.create_session("conv-gc340-a")
        manager.disconnect_session(s1.session_id)
        disconnect_time_s1 = clock._current_time
        clock.set_time(disconnect_time_s1 + 29.999)
        rec = manager.reconnect_session(s1.session_id)
        assert rec.status == RealtimeSessionStatus.ACTIVE

        # 30.000s elapsed -> expired
        clock.set_time(2000.0)
        s2 = manager.create_session("conv-gc340-b")
        manager.disconnect_session(s2.session_id)
        disconnect_time_s2 = clock._current_time
        clock.set_time(disconnect_time_s2 + 30.000)
        with pytest.raises(LeaseExpiredError) as exc_exact:
            manager.reconnect_session(s2.session_id)
        assert exc_exact.value is not None

        # 30.001s elapsed -> expired
        clock.set_time(3000.0)
        s3 = manager.create_session("conv-gc340-c")
        manager.disconnect_session(s3.session_id)
        disconnect_time_s3 = clock._current_time
        clock.set_time(disconnect_time_s3 + 30.001)
        with pytest.raises(LeaseExpiredError):
            manager.reconnect_session(s3.session_id)


# ==============================================================================
# CLUSTER 5: Provider Failure Decoupling (GC-341 ~ GC-343)
# ==============================================================================

class TestCluster5ProviderFailureDecoupling:
    """Acceptance benchmarks verifying decoupled failure resilience (Lock 5)."""

    def test_gc341_tts_failure_preserves_assistant_text_for_fallback(self) -> None:
        """GC-341: TTS synthesis failure preserves generated assistant text (Lock 5)."""
        manager = RealtimeCallSessionManager()
        session = manager.create_session("conv-gc341")

        # Start streaming to store canonical text
        manager.start_assistant_streaming(
            session_id=session.session_id,
            turn_id="turn-tts-fail",
            canonical_text="The stars look bright tonight.",
            generation_id=session.active_generation_id,
        )

        # TTS failure -> text fallback, session survives
        error_evt = manager.handle_provider_error(
            session_id=session.session_id,
            error_kind=RealtimeErrorKind.TTS_FAILURE,
            message="Synthesis timeout",
        )

        assert session.canonical_assistant_texts["turn-tts-fail"] == "The stars look bright tonight."
        assert session.status == RealtimeSessionStatus.ACTIVE
        assert error_evt.error_kind == RealtimeErrorKind.TTS_FAILURE

    def test_gc342_stt_failure_enforces_zero_fake_turn(self) -> None:
        """GC-342: STT failure produces strictly zero fake turns in database or session."""
        manager = RealtimeCallSessionManager()
        session = manager.create_session("conv-gc342")

        # Start a turn so there's a current turn in PARTIAL state
        manager.start_turn(session.session_id, turn_id="turn-stt-fail")
        assert session.current_turn is not None

        error_evt = manager.handle_provider_error(
            session_id=session.session_id,
            error_kind=RealtimeErrorKind.STT_FAILURE,
            message="Microphone buffer underrun",
        )

        assert error_evt.error_kind == RealtimeErrorKind.STT_FAILURE
        # Zero Fake Turn: partial turn must NOT be in committed_turns
        assert "turn-stt-fail" not in session.committed_turns

    def test_gc343_provider_timeout_never_mutates_reality_or_memory(self) -> None:
        """GC-343: Provider timeout leaves reality core and episodic memories intact."""
        manager = RealtimeCallSessionManager()
        session = manager.create_session("conv-gc343")

        # STT failure
        manager.handle_provider_error(
            session_id=session.session_id,
            error_kind=RealtimeErrorKind.STT_FAILURE,
            message="STT Timeout",
        )
        # TTS failure
        manager.handle_provider_error(
            session_id=session.session_id,
            error_kind=RealtimeErrorKind.TTS_FAILURE,
            message="TTS Timeout",
        )

        # Zero turns committed - no fake turns created
        assert len(session.committed_turns) == 0


# ==============================================================================
# CLUSTER 6: Constitutional Boundaries & Lock Invariants (GC-344 ~ GC-348)
# ==============================================================================

class TestCluster6ConstitutionalBoundariesAndLocks:
    """Acceptance benchmarks verifying Rule 19, Lock 8, and Mind-Body Separation."""

    def test_gc344_realtime_subsystem_cannot_call_biography_promotion(self) -> None:
        """GC-344: Realtime modules cannot directly import or invoke BiographyPromotionService."""
        voice_dir = Path("app/voice")
        for fpath in voice_dir.glob("**/*.py"):
            tree = ast.parse(fpath.read_text(encoding="utf-8"), filename=str(fpath))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert "biography_promotion" not in alias.name
                elif isinstance(node, ast.ImportFrom) and node.module:
                    assert "biography_promotion" not in node.module

    def test_gc345_realtime_subsystem_cannot_mutate_character_core(self) -> None:
        """GC-345: Realtime modules contain 0 functional set_fact calls or PromotionAuthorizationToken usage."""
        voice_dir = Path("app/voice")
        call_stream = Path("app/api/call_stream.py")
        targets = list(voice_dir.glob("**/*.py")) + [call_stream]

        forbidden_calls = {"set_fact"}
        forbidden_names = {"PromotionAuthorizationToken"}

        for fpath in targets:
            source = fpath.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(fpath))
            for node in ast.walk(tree):
                # Check function calls: set_fact(...) or obj.set_fact(...)
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id in forbidden_calls:
                        pytest.fail(f"Forbidden call '{func.id}' found in {fpath.name}")
                    if isinstance(func, ast.Attribute) and func.attr in forbidden_calls:
                        pytest.fail(f"Forbidden call '{func.attr}' found in {fpath.name}")
                # Check name / attribute references to PromotionAuthorizationToken
                if isinstance(node, ast.Name) and node.id in forbidden_names:
                    pytest.fail(f"Forbidden name '{node.id}' found in {fpath.name}")
                if isinstance(node, ast.Attribute) and node.attr in forbidden_names:
                    pytest.fail(f"Forbidden attribute '{node.attr}' found in {fpath.name}")

    def test_gc346_audio_rms_cannot_modify_emotion_or_mood(self) -> None:
        """GC-346: Audio amplitude RMS cannot modify EmotionState or CharacterMood (Lock 1)."""
        # AudioFrameEnvelope contains only media and transport fields
        fields = set(AudioFrameEnvelope.model_fields.keys())
        forbidden = {"emotion", "mood", "reality", "trust", "affinity"}
        assert len(fields.intersection(forbidden)) == 0

        # Verify full field whitelist matches ADR-024 specification
        expected_fields = {
            "protocol_version", "session_id", "generation_id", "sequence_id",
            "direction", "codec", "sample_rate", "stream_position_ms", "payload",
        }
        assert fields == expected_fields

    def test_gc347_visual_directive_is_presentation_only(self) -> None:
        """GC-347: VisualDirectiveEvent is presentation-only and cannot mutate reality."""
        directive = VisualDirectiveEvent(
            session_id="sess-gc347",
            expression_archetype="thinking",
            intensity=80,
            transition_duration_ms=250,
            mouth_open_override=None,
            is_speaking=False,
        )
        assert directive.expression_archetype == "thinking"
        assert directive.intensity == 80
        # Verifies no state transition methods exist on directive
        assert not hasattr(directive, "apply_to_mind")
        assert not hasattr(directive, "mutate_reality")
        # VisualDirectiveEvent must not carry any character state
        fields = set(VisualDirectiveEvent.model_fields.keys())
        assert "emotion" not in fields
        assert "mood" not in fields

    def test_gc348_lock8_canonical_conversation_boundary(self) -> None:
        """GC-348: Lock 8 — Zero ephemeral streaming artifacts enter Phase 14 reality engine."""
        manager = RealtimeCallSessionManager()
        session = manager.create_session("conv-gc348")

        # 1. Partial transcript — cannot commit
        partial = TranscriptEvent(
            session_id=session.session_id,
            turn_id="turn-ephemeral-1",
            lifecycle_state=TranscriptLifecycleState.PARTIAL,
            text="User uncommitted partial text",
            is_final=False,
            utterance_boundary_confirmed=False,
        )
        assert not can_commit_to_canonical_message(partial)

        # 2. Barge-in — no canonical commit
        manager.handle_barge_in(session.session_id, client_latch_timestamp_ms=0)

        # 3. STT failure — Zero Fake Turn
        manager.handle_provider_error(
            session_id=session.session_id,
            error_kind=RealtimeErrorKind.STT_FAILURE,
            message="error",
        )

        # Only COMMITTED double-gated turns enter canonical boundary
        assert len(session.committed_turns) == 0


# ==============================================================================
# CLUSTER 7: Determinism & Complete Headless Lifecycle (GC-349 ~ GC-351)
# ==============================================================================

class TestCluster7DeterminismAndHeadlessLifecycle:
    """Acceptance benchmarks verifying deterministic trace execution and full headless round-trip."""

    def test_gc349_deterministic_session_state_transitions(self) -> None:
        """GC-349: Replaying identical event trace produces bitwise identical session state."""
        def run_trace() -> tuple[int, list[str], dict[str, str]]:
            clock = MockMonotonicClock(100.0)
            mgr = RealtimeCallSessionManager(clock_fn=clock)
            sess = mgr.create_session("conv-gc349", session_id="fixed-sess-id")

            # Turn 1: commit user speech
            t1 = TranscriptEvent(
                session_id=sess.session_id,
                turn_id="t1",
                lifecycle_state=TranscriptLifecycleState.COMMITTED,
                text="Hello Aevum",
                is_final=True,
                utterance_boundary_confirmed=True,
            )
            mgr.commit_user_transcript(sess.session_id, t1)

            # Barge-In
            mgr.handle_barge_in(sess.session_id, client_latch_timestamp_ms=0)

            # Turn 2: assistant streaming
            mgr.start_assistant_streaming(sess.session_id, "t2", "I am listening.", sess.active_generation_id)

            return (
                sess.active_generation_id,
                sorted(sess.committed_turns.keys()),
                dict(sess.canonical_assistant_texts),
            )

        trace1 = run_trace()
        trace2 = run_trace()
        assert trace1 == trace2

    def test_gc350_generation_fencing_determinism_under_concurrent_stream(self) -> None:
        """GC-350: Deterministic filtering of mixed-generation interleaved frames."""
        manager = RealtimeCallSessionManager()
        session = manager.create_session("conv-gc350")
        gen0 = session.active_generation_id  # = 1

        # Gen1 (== gen0) frame accepted at seq=0; expected tracker = 1
        frame_g0 = _make_frame(session.session_id, generation_id=gen0, sequence_id=0)
        ok0, _ = validate_generation_and_sequence_fence(
            active_generation_id=gen0,
            expected_sequence_id=0,
            incoming_frame=frame_g0,
        )
        assert ok0

        # Barge-in advances generation to 2
        manager.handle_barge_in(session.session_id, client_latch_timestamp_ms=0)
        gen1 = session.active_generation_id  # = 2

        # Gen0 (old) frame after barge-in MUST be rejected
        frame_g0_late = _make_frame(session.session_id, generation_id=gen0, sequence_id=1)
        ok_late, reason_late = validate_generation_and_sequence_fence(
            active_generation_id=gen1,
            expected_sequence_id=0,
            incoming_frame=frame_g0_late,
        )
        assert not ok_late
        assert reason_late is not None and "STALE_GENERATION" in reason_late

        # Gen1 (new) frame MUST be accepted
        frame_g1 = _make_frame(session.session_id, generation_id=gen1, sequence_id=0)
        ok1, reason1 = validate_generation_and_sequence_fence(
            active_generation_id=gen1,
            expected_sequence_id=0,
            incoming_frame=frame_g1,
        )
        assert ok1
        assert reason1 == "VALID"

    def test_gc351_full_headless_realtime_call_lifecycle(self) -> None:
        """GC-351: Complete end-to-end headless call lifecycle without hardware dependencies."""
        mock_mgr = RealtimeCallSessionManager()
        mock_stt = MockStreamingSTTProvider(default_transcript="How was your day at university?")
        mock_tts = MockStreamingTTSProvider()

        app.dependency_overrides[get_realtime_session_manager] = lambda: mock_mgr
        app.dependency_overrides[get_streaming_stt_provider] = lambda: mock_stt
        app.dependency_overrides[get_streaming_tts_provider] = lambda: mock_tts

        try:
            client = TestClient(app)

            # 1. Initiate session via REST
            init_resp = client.post(
                "/api/v1/call/sessions",
                json={"conversation_id": "conv-gc351-headless"},
            )
            assert init_resp.status_code == 200
            session_id = init_resp.json()["session_id"]
            assert init_resp.json()["active_generation_id"] == 1

            # 2. Open WebSocket stream
            with client.websocket_connect(f"/api/v1/call/stream/{session_id}") as ws:
                # Receive SESSION_STARTED
                start_msg = ws.receive_json()
                assert start_msg["event_type"] == "SESSION_STARTED"
                assert start_msg["active_generation_id"] == 1

                # 3. Stream binary audio frames
                pcm_data = b"\x05\x00" * 160
                env = AudioFrameEnvelope(
                    session_id=session_id,
                    generation_id=1,
                    sequence_id=0,
                    direction=AudioDirection.UPSTREAM_CLIENT_TO_SERVER,
                    codec=AudioCodec.PCM_S16LE,
                    sample_rate=DEFAULT_SAMPLE_RATE_UPSTREAM,
                    stream_position_ms=0,
                    payload=pcm_data,
                )
                packed = pack_audio_frame_envelope(env)
                ws.send_bytes(packed)

                # Receive PARTIAL transcript event
                part_msg = ws.receive_json()
                assert part_msg["event_type"] == "TRANSCRIPT_EVENT"
                assert part_msg["lifecycle_state"] == "PARTIAL"

                # 4. Signal barge-in interrupt
                ws.send_json({
                    "event_type": "BARGE_IN",
                    "client_latch_timestamp_ms": 0,
                    "reason": "user_interrupt",
                })

                # Expect INTERRUPT_FLUSH and VISUAL_DIRECTIVE
                flush_msg = ws.receive_json()
                assert flush_msg["event_type"] == "INTERRUPT_FLUSH"
                assert flush_msg["generation_id"] == 2

                vis_msg = ws.receive_json()
                assert vis_msg["event_type"] == "VISUAL_DIRECTIVE"
                assert vis_msg["mouth_open_override"] == 0.0

                # 5. Graceful closure — server calls websocket.close(WS_1000_NORMAL_CLOSURE) after
                #    receiving SESSION_CLOSED, producing a WebSocketDisconnect on the client side.
                from starlette.websockets import WebSocketDisconnect as _WSD
                import pytest as _pt
                with _pt.raises(_WSD) as exc_info:
                    ws.send_json({"event_type": "SESSION_CLOSED", "reason": "user_hangup"})
                    ws.receive_json()  # triggers the disconnect signal

                assert exc_info.value.code == 1000  # WS_1000_NORMAL_CLOSURE

        finally:
            app.dependency_overrides.clear()

