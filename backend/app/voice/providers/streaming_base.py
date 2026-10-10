"""Streaming voice provider abstractions and hermetic mock implementations (Phase 13.3).

Governed by ADR-024 (Revision 2):
- 13.3-A: Transport 不得拥有 Reality Authority (streaming is purely an input/output conduit).
- 13.3-B: Provider 是 Adapter，不是 Truth Authority (transcripts and audio are sensory events, not canonical truth).
- 13.3-C: WebSocket 断开不能制造 semantic events (transient socket drops never synthesize fake turns).
- Provider Abstraction: Domain services depend exclusively on StreamingSTTProvider and StreamingTTSProvider.
- Mock-for-tests: Hermetic CI testability without requiring live microphone, speaker, or external speech APIs.
"""

from __future__ import annotations

import abc
import json
import struct
from typing import AsyncGenerator, Dict, List, Optional

from app.voice.providers.base import STTProviderError, TTSProviderError
from app.voice.realtime_models import (
    AudioCodec,
    AudioDirection,
    AudioFrameEnvelope,
    DEFAULT_SAMPLE_RATE_DOWNSTREAM,
    TranscriptEvent,
    TranscriptLifecycleState,
)


# ==============================================================================
# Wire Framing Utilities for Binary Media Plane
# ==============================================================================

def pack_audio_frame_envelope(envelope: AudioFrameEnvelope) -> bytes:
    """Serializes an AudioFrameEnvelope into a framed binary packet for WebSocket transmission.

    Wire Layout:
    [4 bytes: unsigned int32 big-endian header length N]
    [N bytes: UTF-8 JSON header containing metadata]
    [Remaining bytes: raw audio payload]
    """
    header_data = {
        "protocol_version": envelope.protocol_version,
        "session_id": envelope.session_id,
        "generation_id": envelope.generation_id,
        "sequence_id": envelope.sequence_id,
        "direction": envelope.direction.value,
        "codec": envelope.codec.value,
        "sample_rate": envelope.sample_rate,
        "stream_position_ms": envelope.stream_position_ms,
    }
    header_bytes = json.dumps(header_data, separators=(",", ":")).encode("utf-8")
    header_len = len(header_bytes)
    prefix = struct.pack(">I", header_len)
    return prefix + header_bytes + envelope.payload


def unpack_audio_frame_envelope(raw_bytes: bytes) -> AudioFrameEnvelope:
    """Deserializes a framed binary packet from the wire into a strictly typed AudioFrameEnvelope."""
    if len(raw_bytes) < 4:
        raise ValueError("Packet too short to contain header length prefix")

    header_len = struct.unpack(">I", raw_bytes[:4])[0]
    if len(raw_bytes) < 4 + header_len:
        raise ValueError("Packet truncated: declared header length exceeds buffer")

    header_bytes = raw_bytes[4 : 4 + header_len]
    payload = raw_bytes[4 + header_len :]

    header_data = json.loads(header_bytes.decode("utf-8"))
    return AudioFrameEnvelope(
        protocol_version=header_data.get("protocol_version", 1),
        session_id=header_data["session_id"],
        generation_id=header_data["generation_id"],
        sequence_id=header_data["sequence_id"],
        direction=AudioDirection(header_data["direction"]),
        codec=AudioCodec(header_data["codec"]),
        sample_rate=header_data["sample_rate"],
        stream_position_ms=header_data.get("stream_position_ms", 0),
        payload=payload,
    )


# ==============================================================================
# Abstract Streaming Provider Protocols
# ==============================================================================

class StreamingSTTProvider(abc.ABC):
    """Protocol for streaming speech-to-text providers."""

    @property
    @abc.abstractmethod
    def provider_id(self) -> str:
        """Unique provider identifier."""

    @abc.abstractmethod
    async def feed_audio_chunk(
        self,
        chunk: AudioFrameEnvelope,
    ) -> AsyncGenerator[TranscriptEvent, None]:
        """Processes incoming audio frame and yields progressive transcript hypotheses."""

    @abc.abstractmethod
    async def end_utterance(
        self,
        session_id: str,
        turn_id: str,
    ) -> Optional[TranscriptEvent]:
        """Signals end-of-utterance, triggering final boundary confirmation if text exists."""

    @abc.abstractmethod
    async def reset(self) -> None:
        """Resets internal buffer state."""


class StreamingTTSProvider(abc.ABC):
    """Protocol for streaming text-to-speech providers."""

    @property
    @abc.abstractmethod
    def provider_id(self) -> str:
        """Unique provider identifier."""

    @abc.abstractmethod
    async def stream_synthesize(
        self,
        text: str,
        session_id: str,
        generation_id: int,
        start_sequence_id: int = 0,
    ) -> AsyncGenerator[AudioFrameEnvelope, None]:
        """Synthesizes text into a stream of audio frame envelopes tagged with generation and sequence."""


# ==============================================================================
# Hermetic Mock Implementations for Headless Testing
# ==============================================================================

class MockStreamingSTTProvider(StreamingSTTProvider):
    """Deterministic, offline mock streaming STT provider for CI and tests."""

    def __init__(
        self,
        default_transcript: str = "Hello Aevum, how are you?",
        simulate_failure: bool = False,
    ) -> None:
        self._default_transcript = default_transcript
        self._simulate_failure = simulate_failure
        self._feed_count = 0
        self._accumulated_bytes = 0

    @property
    def provider_id(self) -> str:
        return "mock_streaming_stt"

    def set_planned_transcript(self, transcript: str) -> None:
        self._default_transcript = transcript

    def set_simulate_failure(self, failure: bool) -> None:
        self._simulate_failure = failure

    async def feed_audio_chunk(
        self,
        chunk: AudioFrameEnvelope,
    ) -> AsyncGenerator[TranscriptEvent, None]:
        if self._simulate_failure:
            raise STTProviderError("Simulated streaming STT engine crash")

        self._feed_count += 1
        self._accumulated_bytes += len(chunk.payload)

        # Emit partial hypothesis progressively based on feed count
        words = self._default_transcript.split()
        visible_word_count = min(len(words), max(1, self._feed_count))
        partial_text = " ".join(words[:visible_word_count])

        yield TranscriptEvent(
            session_id=chunk.session_id,
            turn_id=f"turn-{chunk.generation_id}",
            lifecycle_state=TranscriptLifecycleState.PARTIAL,
            text=partial_text,
            is_final=False,
            utterance_boundary_confirmed=False,
            provider_name=self.provider_id,
        )

    async def end_utterance(
        self,
        session_id: str,
        turn_id: str,
    ) -> Optional[TranscriptEvent]:
        if self._simulate_failure:
            raise STTProviderError("Simulated streaming STT failure on end_utterance")

        if not self._default_transcript.strip():
            return None

        # Yield double-gated COMMITTED transcript
        return TranscriptEvent(
            session_id=session_id,
            turn_id=turn_id,
            lifecycle_state=TranscriptLifecycleState.COMMITTED,
            text=self._default_transcript,
            is_final=True,
            utterance_boundary_confirmed=True,
            provider_name=self.provider_id,
        )

    async def reset(self) -> None:
        self._feed_count = 0
        self._accumulated_bytes = 0


class MockStreamingTTSProvider(StreamingTTSProvider):
    """Deterministic, offline mock streaming TTS provider generating synthetic PCM chunks."""

    def __init__(
        self,
        chunk_size_bytes: int = 480,
        simulate_failure: bool = False,
    ) -> None:
        self._chunk_size_bytes = chunk_size_bytes
        self._simulate_failure = simulate_failure

    @property
    def provider_id(self) -> str:
        return "mock_streaming_tts"

    def set_simulate_failure(self, failure: bool) -> None:
        self._simulate_failure = failure

    async def stream_synthesize(
        self,
        text: str,
        session_id: str,
        generation_id: int,
        start_sequence_id: int = 0,
    ) -> AsyncGenerator[AudioFrameEnvelope, None]:
        if self._simulate_failure:
            raise TTSProviderError("Simulated streaming TTS synthesis failure")

        words = text.split()
        total_chunks = max(1, len(words))

        for idx in range(total_chunks):
            seq = start_sequence_id + idx
            # Synthetic 24kHz 16-bit mono PCM sine-like placeholder bytes
            sample_payload = b"\x00\x10" * (self._chunk_size_bytes // 2)

            yield AudioFrameEnvelope(
                protocol_version=1,
                session_id=session_id,
                generation_id=generation_id,
                sequence_id=seq,
                direction=AudioDirection.DOWNSTREAM_SERVER_TO_CLIENT,
                codec=AudioCodec.PCM_S16LE,
                sample_rate=DEFAULT_SAMPLE_RATE_DOWNSTREAM,
                stream_position_ms=idx * 20,
                payload=sample_payload,
            )
