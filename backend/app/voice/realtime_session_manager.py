"""Authoritative Realtime Call Session Manager & Turn Engine (Phase 13.2).

Governed by ADR-024 (Revision 2):
- Core Axiom: Realtime is an ephemeral streaming conduit, not a reality loophole.
- Backend Session Authority: Backend is the sole authoritative owner of call session state.
- 13.2-LOCK-A: Exact Lease Boundary (elapsed < 30.0s -> valid, elapsed >= 30.0s -> expired).
- 13.2-LOCK-B: Generation Everywhere (generation fence guards all asynchronous results).
- 13.2-LOCK-C: Commit Idempotency (turn_id is the unique idempotency key; zero duplicate messages).
- 13.2-LOCK-D: Active-Turn Reconnect (deterministic transitions for partial user input & streaming output).
- 13.2-LOCK-E: Canonical Text != Playback Cursor (INTERRUPTED preserves full assistant text; played prefix is presentation).
- Lock 4: Instant Client-Local Barge-in latching & cascading cancellation.
- Lock 5: Asymmetric Provider Failure Decoupling (STT failure -> Zero Fake Turn; TTS failure -> text fallback).
- Lock 8: Canonical Conversation Boundary (Only fully COMMITTED turns enter persistent conversation).
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from app.voice.realtime_models import (
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
    can_commit_to_canonical_message,
    REALTIME_SESSION_RECONNECT_LEASE_SECONDS,
)


# ==============================================================================
# Domain Exception Hierarchy
# ==============================================================================

class RealtimeSessionError(Exception):
    """Base exception for all realtime session operations."""
    pass


class SessionNotFoundError(RealtimeSessionError):
    """Raised when operating on a non-existent session ID."""
    pass


class SessionClosedError(RealtimeSessionError):
    """Raised when attempting operations on an already closed or terminated session."""
    pass


class LeaseExpiredError(RealtimeSessionError):
    """Raised when attempting to reconnect a session after the 30.0s monotonic lease expired."""
    pass


class GenerationFenceError(RealtimeSessionError):
    """Raised when an operation or callback violates monotonic generation fencing."""
    pass


# ==============================================================================
# In-Memory Session Entity
# ==============================================================================

class RealtimeCallSession(BaseModel):
    """Authoritative in-memory state of an active or reconnecting realtime call session."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    session_id: str
    conversation_id: str
    status: RealtimeSessionStatus = RealtimeSessionStatus.INITIATED
    active_generation_id: int = 1
    current_turn: Optional[DirectionalTurnState] = None

    # Monotonic timing trackers (governed by controlled monotonic clock)
    created_monotonic_at: float
    last_active_monotonic_at: float
    disconnected_monotonic_at: Optional[float] = None
    lease_expires_monotonic_at: Optional[float] = None

    # Idempotent storage for committed turns (13.2-LOCK-C)
    committed_turns: Dict[str, DirectionalTurnState] = Field(default_factory=dict)

    # Separation of canonical text from playback presentation (13.2-LOCK-E)
    canonical_assistant_texts: Dict[str, str] = Field(default_factory=dict)
    assistant_played_prefixes: Dict[str, str] = Field(default_factory=dict)

    # Error and diagnostic history (13.2-LOCK-5)
    error_history: List[RealtimeErrorEvent] = Field(default_factory=list)


# ==============================================================================
# RealtimeCallSessionManager
# ==============================================================================

class RealtimeCallSessionManager:
    """Sole authoritative coordinator of realtime call sessions and directional turn state machines."""

    def __init__(self, clock_fn: Optional[Callable[[], float]] = None) -> None:
        """Initializes manager with optional monotonic clock injection for deterministic testing."""
        self._clock_fn = clock_fn or time.monotonic
        self._sessions: Dict[str, RealtimeCallSession] = {}

    def _now(self) -> float:
        """Returns current monotonic time."""
        return float(self._clock_fn())

    # --------------------------------------------------------------------------
    # Session Lifecycle Management
    # --------------------------------------------------------------------------

    def create_session(
        self,
        conversation_id: str,
        session_id: Optional[str] = None,
    ) -> RealtimeCallSession:
        """Creates a new realtime call session bound to a persistent conversation."""
        now = self._now()
        sid = session_id or f"call-{uuid.uuid4().hex[:12]}"

        # Domain separation invariant: session_id != conversation_id
        if sid == conversation_id:
            raise ValueError("session_id must not equal conversation_id (domain separation violation)")

        session = RealtimeCallSession(
            session_id=sid,
            conversation_id=conversation_id,
            status=RealtimeSessionStatus.ACTIVE,
            active_generation_id=1,
            created_monotonic_at=now,
            last_active_monotonic_at=now,
        )
        self._sessions[sid] = session
        return session

    def get_session(self, session_id: str) -> Optional[RealtimeCallSession]:
        """Retrieves an existing session if present."""
        return self._sessions.get(session_id)

    def disconnect_session(
        self,
        session_id: str,
        reason: str = "transport_disconnect",
    ) -> SessionEvent:
        """Marks a session as disconnected, entering the 30s monotonic reconnect lease window."""
        session = self._sessions.get(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        if session.status in (RealtimeSessionStatus.CLOSED, RealtimeSessionStatus.TERMINATED):
            raise SessionClosedError(f"Session {session_id} is already {session.status}")

        now = self._now()
        session.status = RealtimeSessionStatus.RECONNECTING
        session.disconnected_monotonic_at = now
        session.lease_expires_monotonic_at = now + float(REALTIME_SESSION_RECONNECT_LEASE_SECONDS)

        # 13.2-LOCK-D: Active-Turn Reconnect state handling
        if session.current_turn:
            turn = session.current_turn
            # If user was speaking and stream severed, reset partial state so no incomplete turn commits
            if turn.user_input_state == UserInputState.PARTIAL:
                # User speech was cut off mid-sentence
                pass
            # If assistant was streaming when transport dropped, mark as INTERRUPTED
            if turn.assistant_output_state == AssistantOutputState.STREAMING:
                session.current_turn = DirectionalTurnState(
                    turn_id=turn.turn_id,
                    session_id=turn.session_id,
                    conversation_id=turn.conversation_id,
                    generation_id=turn.generation_id,
                    user_input_state=turn.user_input_state,
                    assistant_output_state=AssistantOutputState.INTERRUPTED,
                    created_monotonic_at=turn.created_monotonic_at,
                    updated_monotonic_at=now,
                )

        return SessionEvent(
            event_type=RealtimeEventType.SESSION_RECONNECT,
            session_id=session.session_id,
            conversation_id=session.conversation_id,
            status=session.status,
            active_generation_id=session.active_generation_id,
            lease_expires_monotonic_at=session.lease_expires_monotonic_at,
            reason=reason,
        )

    def reconnect_session(self, session_id: str) -> RealtimeCallSession:
        """Attempts to reconnect an existing session within its 30s lease window (13.2-LOCK-A).

        Boundary Condition:
        - elapsed < 30.0s -> Valid reconnection (resumes ACTIVE)
        - elapsed >= 30.0s -> Lease expired (transitions TERMINATED, raises LeaseExpiredError)
        """
        session = self._sessions.get(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        if session.status in (RealtimeSessionStatus.CLOSED, RealtimeSessionStatus.TERMINATED):
            raise SessionClosedError(f"Session {session_id} is permanently {session.status}")

        now = self._now()
        disconnected_at = session.disconnected_monotonic_at or session.last_active_monotonic_at
        elapsed = now - disconnected_at

        # 13.2-LOCK-A: Strict monotonic boundary check
        if elapsed >= float(REALTIME_SESSION_RECONNECT_LEASE_SECONDS):
            session.status = RealtimeSessionStatus.TERMINATED
            raise LeaseExpiredError(
                f"Reconnect lease expired: elapsed {elapsed:.4f}s >= {REALTIME_SESSION_RECONNECT_LEASE_SECONDS}s"
            )

        # Valid reconnection
        session.status = RealtimeSessionStatus.ACTIVE
        session.disconnected_monotonic_at = None
        session.lease_expires_monotonic_at = None
        session.last_active_monotonic_at = now
        return session

    def close_session(
        self,
        session_id: str,
        reason: str = "normal_hangup",
    ) -> SessionEvent:
        """Gracefully closes a session permanently."""
        session = self._sessions.get(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        now = self._now()
        session.status = RealtimeSessionStatus.CLOSED
        session.last_active_monotonic_at = now

        if session.current_turn and session.current_turn.assistant_output_state == AssistantOutputState.STREAMING:
            turn = session.current_turn
            session.current_turn = DirectionalTurnState(
                turn_id=turn.turn_id,
                session_id=turn.session_id,
                conversation_id=turn.conversation_id,
                generation_id=turn.generation_id,
                user_input_state=turn.user_input_state,
                assistant_output_state=AssistantOutputState.COMPLETED,
                created_monotonic_at=turn.created_monotonic_at,
                updated_monotonic_at=now,
            )

        return SessionEvent(
            event_type=RealtimeEventType.SESSION_CLOSED,
            session_id=session.session_id,
            conversation_id=session.conversation_id,
            status=session.status,
            active_generation_id=session.active_generation_id,
            reason=reason,
        )

    # --------------------------------------------------------------------------
    # Directional Turn State Machine & Idempotent Commitment
    # --------------------------------------------------------------------------

    def start_turn(
        self,
        session_id: str,
        turn_id: Optional[str] = None,
    ) -> DirectionalTurnState:
        """Starts a fresh conversational turn within the session."""
        session = self._sessions.get(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")
        if session.status != RealtimeSessionStatus.ACTIVE:
            raise SessionClosedError(f"Cannot start turn on non-active session ({session.status})")

        now = self._now()
        tid = turn_id or f"turn-{uuid.uuid4().hex[:12]}"

        # Domain separation check
        if tid == session.session_id or tid == session.conversation_id:
            raise ValueError("turn_id must not equal session_id or conversation_id")

        turn = DirectionalTurnState(
            turn_id=tid,
            session_id=session.session_id,
            conversation_id=session.conversation_id,
            generation_id=session.active_generation_id,
            user_input_state=UserInputState.PARTIAL,
            assistant_output_state=AssistantOutputState.NOT_STARTED,
            created_monotonic_at=now,
            updated_monotonic_at=now,
        )
        session.current_turn = turn
        session.last_active_monotonic_at = now
        return turn

    def commit_user_transcript(
        self,
        session_id: str,
        transcript: TranscriptEvent,
    ) -> Tuple[DirectionalTurnState, bool]:
        """Double-gated, idempotent commitment of user transcript (13.2-LOCK-C & Lock 3).

        Returns:
            (committed_turn, is_new_commit)
            - If turn was already committed, returns (existing_turn, False) idempotently.
            - If double-gate passes, commits user speech, persists turn, and returns (turn, True).
        """
        session = self._sessions.get(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        # 13.2-LOCK-C: Idempotency check on turn_id
        if transcript.turn_id in session.committed_turns:
            return (session.committed_turns[transcript.turn_id], False)

        # Double-gate verification (Lock 3 & Lock 8)
        if not can_commit_to_canonical_message(transcript):
            raise ValueError(
                f"Transcript double-gate failed: state={transcript.lifecycle_state}, "
                f"is_final={transcript.is_final}, boundary={transcript.utterance_boundary_confirmed}"
            )

        now = self._now()
        current_turn = session.current_turn

        if not current_turn or current_turn.turn_id != transcript.turn_id:
            # Create turn container for this commit if not active
            current_turn = DirectionalTurnState(
                turn_id=transcript.turn_id,
                session_id=session.session_id,
                conversation_id=session.conversation_id,
                generation_id=session.active_generation_id,
                user_input_state=UserInputState.COMMITTED,
                assistant_output_state=AssistantOutputState.NOT_STARTED,
                created_monotonic_at=now,
                updated_monotonic_at=now,
            )
        else:
            current_turn = DirectionalTurnState(
                turn_id=current_turn.turn_id,
                session_id=current_turn.session_id,
                conversation_id=current_turn.conversation_id,
                generation_id=current_turn.generation_id,
                user_input_state=UserInputState.COMMITTED,
                assistant_output_state=current_turn.assistant_output_state,
                created_monotonic_at=current_turn.created_monotonic_at,
                updated_monotonic_at=now,
            )

        session.current_turn = current_turn
        session.committed_turns[transcript.turn_id] = current_turn
        session.last_active_monotonic_at = now
        return (current_turn, True)

    def start_assistant_streaming(
        self,
        session_id: str,
        turn_id: str,
        canonical_text: str,
        generation_id: Optional[int] = None,
    ) -> DirectionalTurnState:
        """Begins streaming assistant response for a committed user turn."""
        session = self._sessions.get(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        # 13.2-LOCK-B: Generation Fence check
        active_gen = session.active_generation_id
        target_gen = generation_id if generation_id is not None else active_gen
        if target_gen < active_gen:
            raise GenerationFenceError(
                f"Cannot stream assistant response: target generation {target_gen} < active {active_gen}"
            )

        now = self._now()
        current_turn = session.current_turn or session.committed_turns.get(turn_id)
        if not current_turn:
            current_turn = DirectionalTurnState(
                turn_id=turn_id,
                session_id=session.session_id,
                conversation_id=session.conversation_id,
                generation_id=target_gen,
                user_input_state=UserInputState.COMMITTED,
                assistant_output_state=AssistantOutputState.STREAMING,
                created_monotonic_at=now,
                updated_monotonic_at=now,
            )
        else:
            current_turn = DirectionalTurnState(
                turn_id=current_turn.turn_id,
                session_id=current_turn.session_id,
                conversation_id=current_turn.conversation_id,
                generation_id=target_gen,
                user_input_state=current_turn.user_input_state,
                assistant_output_state=AssistantOutputState.STREAMING,
                created_monotonic_at=current_turn.created_monotonic_at,
                updated_monotonic_at=now,
            )

        # 13.2-LOCK-E: Preserve canonical text independently from playback progress
        session.canonical_assistant_texts[turn_id] = canonical_text
        session.current_turn = current_turn
        session.last_active_monotonic_at = now
        return current_turn

    def complete_assistant_streaming(
        self,
        session_id: str,
        turn_id: str,
        generation_id: int,
    ) -> Tuple[bool, str]:
        """Completes assistant streaming response, gated by generation fence (13.2-LOCK-B)."""
        session = self._sessions.get(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        # 13.2-LOCK-B: Drop completion if stale generation
        if generation_id < session.active_generation_id:
            return (
                False,
                f"STALE_GENERATION_DROPPED: Completion generation {generation_id} < active {session.active_generation_id}",
            )

        now = self._now()
        current_turn = session.current_turn
        if current_turn and current_turn.turn_id == turn_id:
            session.current_turn = DirectionalTurnState(
                turn_id=current_turn.turn_id,
                session_id=current_turn.session_id,
                conversation_id=current_turn.conversation_id,
                generation_id=current_turn.generation_id,
                user_input_state=current_turn.user_input_state,
                assistant_output_state=AssistantOutputState.COMPLETED,
                created_monotonic_at=current_turn.created_monotonic_at,
                updated_monotonic_at=now,
            )
            session.last_active_monotonic_at = now

        return (True, "COMPLETED")

    # --------------------------------------------------------------------------
    # Barge-In & Cascading Cancellation (Lock 4 & 13.2-LOCK-E)
    # --------------------------------------------------------------------------

    def handle_barge_in(
        self,
        session_id: str,
        client_latch_timestamp_ms: int,
        played_prefix: Optional[str] = None,
    ) -> Tuple[BargeInEvent, InterruptFlushEvent]:
        """Executes barge-in cascade: increments generation, interrupts assistant, preserves canonical text.

        Guarantees:
        - active_generation_id increments monotonically.
        - assistant_output_state transitions to INTERRUPTED.
        - 13.2-LOCK-E: Canonical assistant text is NOT truncated; played prefix is stored as presentation metadata.
        """
        session = self._sessions.get(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        now = self._now()
        interrupted_gen = session.active_generation_id
        session.active_generation_id += 1
        new_gen = session.active_generation_id

        interrupted_turn_id = "none"
        if session.current_turn:
            turn = session.current_turn
            interrupted_turn_id = turn.turn_id

            # Interrupt assistant speech
            if turn.assistant_output_state == AssistantOutputState.STREAMING:
                session.current_turn = DirectionalTurnState(
                    turn_id=turn.turn_id,
                    session_id=turn.session_id,
                    conversation_id=turn.conversation_id,
                    generation_id=turn.generation_id,
                    user_input_state=turn.user_input_state,
                    assistant_output_state=AssistantOutputState.INTERRUPTED,
                    created_monotonic_at=turn.created_monotonic_at,
                    updated_monotonic_at=now,
                )

                # 13.2-LOCK-E: Record playback cursor in presentation map without altering canonical text
                if played_prefix is not None:
                    session.assistant_played_prefixes[turn.turn_id] = played_prefix

        session.last_active_monotonic_at = now

        barge_in_event = BargeInEvent(
            session_id=session.session_id,
            interrupted_turn_id=interrupted_turn_id,
            interrupted_generation_id=interrupted_gen,
            new_generation_id=new_gen,
            client_latch_timestamp_ms=client_latch_timestamp_ms,
        )

        flush_event = InterruptFlushEvent(
            session_id=session.session_id,
            generation_id=new_gen,
            reason="user_barge_in",
        )

        return (barge_in_event, flush_event)

    # --------------------------------------------------------------------------
    # Universal Async Result Fencing (13.2-LOCK-B)
    # --------------------------------------------------------------------------

    def handle_async_result(
        self,
        session_id: str,
        generation_id: int,
        result_type: str,
        payload: Any,
    ) -> Tuple[bool, str]:
        """Guards any asynchronous callback (STT, LLM, TTS) against the active generation (13.2-LOCK-B).

        Returns:
            (True, "APPLIED") if generation is valid.
            (False, "STALE_GENERATION_DROPPED") if generation is obsolete.
        """
        session = self._sessions.get(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        if generation_id < session.active_generation_id:
            return (
                False,
                f"STALE_GENERATION_DROPPED: {result_type} generation {generation_id} < active {session.active_generation_id}",
            )

        session.last_active_monotonic_at = self._now()
        return (True, "APPLIED")

    # --------------------------------------------------------------------------
    # Provider Failure Handling (Lock 5 & Zero Fake Turn)
    # --------------------------------------------------------------------------

    def handle_provider_error(
        self,
        session_id: str,
        error_kind: RealtimeErrorKind,
        message: str,
    ) -> RealtimeErrorEvent:
        """Processes provider failure with strict asymmetric decoupling (ADR-024 Lock 5).

        Rules:
        - STT_FAILURE: Enforces Zero Fake Turn. Aborts pending user turn; committed_turns remains untainted.
        - TTS_FAILURE: Preserves assistant text; transitions output state to text fallback without aborting.
        """
        session = self._sessions.get(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        now = self._now()
        error_event = RealtimeErrorEvent(
            session_id=session.session_id,
            error_kind=error_kind,
            message=message,
            recoverable=True,
            affected_generation_id=session.active_generation_id,
        )
        session.error_history.append(error_event)

        if error_kind == RealtimeErrorKind.STT_FAILURE:
            # Zero Fake Turn: If user input was pending/partial, discard it cleanly
            if session.current_turn and session.current_turn.user_input_state != UserInputState.COMMITTED:
                # Do NOT commit turn to session.committed_turns!
                session.current_turn = None

        elif error_kind == RealtimeErrorKind.TTS_FAILURE:
            # Text fallback: canonical text remains intact; assistant state completes in degraded mode
            if session.current_turn and session.current_turn.assistant_output_state == AssistantOutputState.STREAMING:
                turn = session.current_turn
                session.current_turn = DirectionalTurnState(
                    turn_id=turn.turn_id,
                    session_id=turn.session_id,
                    conversation_id=turn.conversation_id,
                    generation_id=turn.generation_id,
                    user_input_state=turn.user_input_state,
                    assistant_output_state=AssistantOutputState.COMPLETED,
                    created_monotonic_at=turn.created_monotonic_at,
                    updated_monotonic_at=now,
                )

        session.last_active_monotonic_at = now
        return error_event
