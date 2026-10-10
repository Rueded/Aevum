"""Dedicated unit tests and AST boundary verification for Phase 13.2 Realtime Session Manager & Turn Engine.

Covers all Phase 13.2 Mandatory Locks:
- 13.2-LOCK-A: Exact Lease Boundary (29.999s valid, 30.000s & 30.001s expired) under monotonic clock.
- 13.2-LOCK-B: Generation Everywhere (callbacks, stream completion, stale drop).
- 13.2-LOCK-C: Commit Idempotency (turn_id idempotency key; duplicate commit produces at most 1 turn).
- 13.2-LOCK-D: Active-Turn Reconnect (deterministic transitions for partial input & streaming output).
- 13.2-LOCK-E: Canonical Text != Playback Cursor (INTERRUPTED preserves full assistant text; played prefix is presentation).
- Lock 4: Instant Client-Local Barge-In Latch & cascading cancellation.
- Lock 5: Asymmetric Provider Failure Decoupling (STT failure -> Zero Fake Turn; TTS failure -> text fallback).
- Lock 8: Canonical Conversation Boundary (Only fully COMMITTED turns enter conversation).
- Static AST Boundary Audit (zero DB, zero network, zero LLM, zero mutation tokens).
"""

import ast
from pathlib import Path
import pytest

from app.voice.realtime_models import (
    AssistantOutputState,
    RealtimeErrorKind,
    RealtimeEventType,
    RealtimeSessionStatus,
    TranscriptEvent,
    TranscriptLifecycleState,
    UserInputState,
)
from app.voice.realtime_session_manager import (
    GenerationFenceError,
    LeaseExpiredError,
    RealtimeCallSessionManager,
    SessionClosedError,
    SessionNotFoundError,
)


class MockMonotonicClock:
    """Controllable monotonic clock for microsecond-precise boundary testing."""

    def __init__(self, initial_time: float = 1000.0) -> None:
        self._current_time = initial_time

    def __call__(self) -> float:
        return self._current_time

    def advance(self, seconds: float) -> None:
        self._current_time += seconds

    def set_time(self, exact_time: float) -> None:
        self._current_time = exact_time


# ==============================================================================
# Cluster 1: 13.2-LOCK-A Exact Lease Boundary (30.000s Monotonic Window)
# ==============================================================================

def test_reconnect_lease_valid_at_29_999s():
    """13.2-LOCK-A: Reconnection at elapsed 29.999s is valid and resumes session to ACTIVE."""
    clock = MockMonotonicClock(100.0)
    manager = RealtimeCallSessionManager(clock_fn=clock)

    session = manager.create_session(conversation_id="conv-001")
    sid = session.session_id

    # Disconnect at t = 110.0s
    clock.advance(10.0)
    event = manager.disconnect_session(sid)
    assert event.status == RealtimeSessionStatus.RECONNECTING

    # Advance clock by exactly 29.999s (t = 139.999s)
    clock.advance(29.999)
    reconnected_session = manager.reconnect_session(sid)
    assert reconnected_session.status == RealtimeSessionStatus.ACTIVE
    assert reconnected_session.disconnected_monotonic_at is None
    assert reconnected_session.lease_expires_monotonic_at is None


def test_reconnect_lease_expired_at_30_000s():
    """13.2-LOCK-A: Reconnection at exactly elapsed 30.000s deterministically expires and terminates."""
    clock = MockMonotonicClock(100.0)
    manager = RealtimeCallSessionManager(clock_fn=clock)

    session = manager.create_session(conversation_id="conv-001")
    sid = session.session_id

    # Disconnect at t = 105.0s
    clock.advance(5.0)
    manager.disconnect_session(sid)

    # Advance clock by exactly 30.000s (boundary: elapsed >= 30.0)
    clock.advance(30.000)

    with pytest.raises(LeaseExpiredError) as exc_info:
        manager.reconnect_session(sid)
    assert "lease expired" in str(exc_info.value).lower()

    # Session transitions to TERMINATED
    assert session.status == RealtimeSessionStatus.TERMINATED


def test_reconnect_lease_expired_at_30_001s():
    """13.2-LOCK-A: Reconnection at elapsed 30.001s deterministically expires and terminates."""
    clock = MockMonotonicClock(100.0)
    manager = RealtimeCallSessionManager(clock_fn=clock)

    session = manager.create_session(conversation_id="conv-001")
    sid = session.session_id

    # Disconnect at t = 100.0s
    manager.disconnect_session(sid)

    # Advance clock by 30.001s
    clock.advance(30.001)

    with pytest.raises(LeaseExpiredError):
        manager.reconnect_session(sid)

    assert session.status == RealtimeSessionStatus.TERMINATED


def test_reconnect_on_closed_or_nonexistent_session():
    """Operating on missing or closed session raises appropriate typed domain errors."""
    clock = MockMonotonicClock(100.0)
    manager = RealtimeCallSessionManager(clock_fn=clock)

    with pytest.raises(SessionNotFoundError):
        manager.reconnect_session("non-existent-session")

    session = manager.create_session(conversation_id="conv-001")
    manager.close_session(session.session_id)

    with pytest.raises(SessionClosedError):
        manager.reconnect_session(session.session_id)


# ==============================================================================
# Cluster 2: 13.2-LOCK-B Generation Everywhere & Stale Drop
# ==============================================================================

def test_generation_fence_drops_stale_completion():
    """13.2-LOCK-B: Completion callback from older generation is dropped without mutating state."""
    clock = MockMonotonicClock(100.0)
    manager = RealtimeCallSessionManager(clock_fn=clock)

    session = manager.create_session(conversation_id="conv-001")
    sid = session.session_id

    turn = manager.start_turn(sid, turn_id="turn-001")
    manager.start_assistant_streaming(sid, turn_id="turn-001", canonical_text="Hello user", generation_id=1)

    # User barges in -> active_generation_id becomes 2
    manager.handle_barge_in(sid, client_latch_timestamp_ms=101000)
    assert session.active_generation_id == 2

    # Delayed completion callback arrives from generation 1!
    success, reason = manager.complete_assistant_streaming(sid, turn_id="turn-001", generation_id=1)
    assert not success
    assert "STALE_GENERATION_DROPPED" in reason

    # Current turn remains INTERRUPTED, not COMPLETED!
    assert session.current_turn.assistant_output_state == AssistantOutputState.INTERRUPTED


def test_generation_fence_guards_async_callbacks():
    """13.2-LOCK-B: Universal async callback handler drops stale results across all provider types."""
    clock = MockMonotonicClock(100.0)
    manager = RealtimeCallSessionManager(clock_fn=clock)

    session = manager.create_session(conversation_id="conv-001")
    sid = session.session_id

    # Active generation is 1
    applied, msg = manager.handle_async_result(sid, generation_id=1, result_type="LLM_CHUNK", payload="Hi")
    assert applied
    assert msg == "APPLIED"

    # Generation advances to 2
    manager.handle_barge_in(sid, client_latch_timestamp_ms=105000)

    # Late-arriving LLM or TTS callback from generation 1 is blocked
    applied, msg = manager.handle_async_result(sid, generation_id=1, result_type="TTS_AUDIO_BUFFER", payload=b"wav")
    assert not applied
    assert "STALE_GENERATION_DROPPED" in msg


def test_starting_streaming_with_stale_generation_rejected():
    """13.2-LOCK-B: Attempting to start streaming with an older generation raises GenerationFenceError."""
    clock = MockMonotonicClock(100.0)
    manager = RealtimeCallSessionManager(clock_fn=clock)

    session = manager.create_session(conversation_id="conv-001")
    sid = session.session_id
    manager.start_turn(sid, turn_id="turn-001")

    # Advance generation to 3
    manager.handle_barge_in(sid, 100)
    manager.handle_barge_in(sid, 200)
    assert session.active_generation_id == 3

    # Attempting to start streaming with target generation 2 raises GenerationFenceError
    with pytest.raises(GenerationFenceError):
        manager.start_assistant_streaming(sid, turn_id="turn-001", canonical_text="Hi", generation_id=2)


# ==============================================================================
# Cluster 3: 13.2-LOCK-C Commit Idempotency
# ==============================================================================

def test_commit_idempotency_prevents_duplicate_messages():
    """13.2-LOCK-C: Submitting identical turn_id multiple times produces exactly one semantic turn."""
    clock = MockMonotonicClock(100.0)
    manager = RealtimeCallSessionManager(clock_fn=clock)

    session = manager.create_session(conversation_id="conv-001")
    sid = session.session_id

    turn_id = "turn-idempotent-42"
    transcript = TranscriptEvent(
        session_id=sid,
        turn_id=turn_id,
        lifecycle_state=TranscriptLifecycleState.COMMITTED,
        text="What are your favorite teas, Aevum?",
        is_final=True,
        utterance_boundary_confirmed=True,
    )

    # First commit: returns is_new_commit=True
    committed_turn_1, is_new_1 = manager.commit_user_transcript(sid, transcript)
    assert is_new_1
    assert committed_turn_1.user_input_state == UserInputState.COMMITTED
    assert len(session.committed_turns) == 1

    # Second commit (e.g. duplicate reconnect packet or duplicate callback):
    committed_turn_2, is_new_2 = manager.commit_user_transcript(sid, transcript)
    assert not is_new_2  # Idempotent no-op!
    assert committed_turn_2.turn_id == turn_id
    assert len(session.committed_turns) == 1  # Strictly 1 entry, zero duplication!


def test_commit_fails_if_double_gate_unmet():
    """Unconfirmed or partial transcript fails double gate and does not commit."""
    clock = MockMonotonicClock(100.0)
    manager = RealtimeCallSessionManager(clock_fn=clock)

    session = manager.create_session(conversation_id="conv-001")
    sid = session.session_id

    partial_transcript = TranscriptEvent(
        session_id=sid,
        turn_id="turn-incomplete-1",
        lifecycle_state=TranscriptLifecycleState.PARTIAL,
        text="I am thinking about",
        is_final=False,
        utterance_boundary_confirmed=False,
    )

    with pytest.raises(ValueError) as exc_info:
        manager.commit_user_transcript(sid, partial_transcript)
    assert "double-gate failed" in str(exc_info.value)
    assert len(session.committed_turns) == 0


# ==============================================================================
# Cluster 4: 13.2-LOCK-D Active-Turn Reconnect Determinism
# ==============================================================================

def test_active_turn_reconnect_with_partial_user_speech():
    """13.2-LOCK-D: Disconnection during user speaking does not commit partial speech to conversation."""
    clock = MockMonotonicClock(100.0)
    manager = RealtimeCallSessionManager(clock_fn=clock)

    session = manager.create_session(conversation_id="conv-001")
    sid = session.session_id

    manager.start_turn(sid, turn_id="turn-cut-off")
    assert session.current_turn.user_input_state == UserInputState.PARTIAL

    # Disconnect while user speaking
    manager.disconnect_session(sid)
    assert len(session.committed_turns) == 0

    # Reconnect within lease
    clock.advance(2.0)
    manager.reconnect_session(sid)
    assert len(session.committed_turns) == 0  # Still zero fake commit!


def test_active_turn_reconnect_with_assistant_streaming():
    """13.2-LOCK-D: Disconnection during assistant streaming transitions assistant to INTERRUPTED."""
    clock = MockMonotonicClock(100.0)
    manager = RealtimeCallSessionManager(clock_fn=clock)

    session = manager.create_session(conversation_id="conv-001")
    sid = session.session_id

    manager.start_turn(sid, turn_id="turn-streaming")
    manager.start_assistant_streaming(sid, turn_id="turn-streaming", canonical_text="I was telling a story...")

    # Disconnect while assistant streaming
    manager.disconnect_session(sid)
    assert session.current_turn.assistant_output_state == AssistantOutputState.INTERRUPTED

    # Reconnect
    clock.advance(5.0)
    manager.reconnect_session(sid)
    assert session.status == RealtimeSessionStatus.ACTIVE
    assert session.current_turn.assistant_output_state == AssistantOutputState.INTERRUPTED


# ==============================================================================
# Cluster 5: 13.2-LOCK-E Canonical Text != Playback Cursor
# ==============================================================================

def test_canonical_text_preserved_on_barge_in():
    """13.2-LOCK-E: Barge-in records played prefix for presentation, preserving 100% of canonical text."""
    clock = MockMonotonicClock(100.0)
    manager = RealtimeCallSessionManager(clock_fn=clock)

    session = manager.create_session(conversation_id="conv-001")
    sid = session.session_id

    turn_id = "turn-barge-canonical"
    full_generated_text = (
        "I really love making matcha in the morning. The gentle whisking sound "
        "and the rich green froth bring a sense of quiet clarity before the day starts."
    )
    played_prefix = "I really love making matcha in the morning. The gentle"

    manager.start_turn(sid, turn_id=turn_id)
    manager.start_assistant_streaming(sid, turn_id=turn_id, canonical_text=full_generated_text)

    # User barges in after hearing only the first sentence
    barge_evt, flush_evt = manager.handle_barge_in(
        session_id=sid,
        client_latch_timestamp_ms=102500,
        played_prefix=played_prefix,
    )

    # 1. Active generation incremented
    assert barge_evt.new_generation_id == 2
    assert flush_evt.generation_id == 2

    # 2. Realtime presentation output state is INTERRUPTED
    assert session.current_turn.assistant_output_state == AssistantOutputState.INTERRUPTED

    # 3. 13.2-LOCK-E: Canonical assistant text is NOT truncated or modified!
    assert session.canonical_assistant_texts[turn_id] == full_generated_text

    # 4. Played prefix is stored in presentation map
    assert session.assistant_played_prefixes[turn_id] == played_prefix


# ==============================================================================
# Cluster 6: Lock 5 Asymmetric Provider Failure Decoupling (Zero Fake Turn)
# ==============================================================================

def test_stt_failure_enforces_zero_fake_turn():
    """Lock 5: STT provider failure aborts uncommitted turn; zero fake turns entered in committed_turns."""
    clock = MockMonotonicClock(100.0)
    manager = RealtimeCallSessionManager(clock_fn=clock)

    session = manager.create_session(conversation_id="conv-001")
    sid = session.session_id

    manager.start_turn(sid, turn_id="turn-stt-fail")

    # STT fails mid-turn
    error_evt = manager.handle_provider_error(
        session_id=sid,
        error_kind=RealtimeErrorKind.STT_FAILURE,
        message="STT provider connection closed unexpectedly",
    )
    assert error_evt.error_kind == RealtimeErrorKind.STT_FAILURE

    # Zero Fake Turn verified:
    assert len(session.committed_turns) == 0
    assert session.current_turn is None  # Aborted uncommitted turn


def test_tts_failure_preserves_text_and_session_health():
    """Lock 5: TTS failure preserves canonical text; allows text fallback without session crash."""
    clock = MockMonotonicClock(100.0)
    manager = RealtimeCallSessionManager(clock_fn=clock)

    session = manager.create_session(conversation_id="conv-001")
    sid = session.session_id

    turn_id = "turn-tts-fail"
    canonical_text = "Here is my response text, even if speech synthesis fails."

    manager.start_turn(sid, turn_id=turn_id)
    manager.start_assistant_streaming(sid, turn_id=turn_id, canonical_text=canonical_text)

    # TTS fails during synthesis
    error_evt = manager.handle_provider_error(
        session_id=sid,
        error_kind=RealtimeErrorKind.TTS_FAILURE,
        message="TTS synthesis timed out after 3000ms",
    )
    assert error_evt.error_kind == RealtimeErrorKind.TTS_FAILURE

    # Text fallback: canonical text remains intact
    assert session.canonical_assistant_texts[turn_id] == canonical_text
    assert session.current_turn.assistant_output_state == AssistantOutputState.COMPLETED
    assert session.status == RealtimeSessionStatus.ACTIVE


# ==============================================================================
# Cluster 7: Static AST Boundary Audit
# ==============================================================================

def test_ast_boundary_audit_realtime_session_manager():
    """Static AST Audit verifying architectural purity of realtime_session_manager.py.

    Mandates:
    - 0 Database imports (SQLAlchemy, SQLite, Session)
    - 0 LLM provider imports (openai, anthropic, google)
    - 0 Network libraries (requests, httpx, aiohttp)
    - 0 Mutation authority tokens (PromotionAuthorizationToken, set_fact)
    """
    manager_path = Path(__file__).parent.parent / "app" / "voice" / "realtime_session_manager.py"
    assert manager_path.exists(), f"File not found: {manager_path}"

    with open(manager_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=str(manager_path))

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

    assert not found_violations, f"AST boundary violations detected in realtime_session_manager.py: {found_violations}"
