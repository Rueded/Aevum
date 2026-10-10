"""Mock STT provider implementation for deterministic offline testing (Phase 10.4).

Governed by ADR-021:
- Provider Abstraction as Implementation Detail: MockSTTProvider implements STTProvider protocol.
- Zero Live Leaks in Tests: Unit tests use MockSTTProvider exclusively; zero external API or heavy model calls.
- Lock B: Decoupled Failure Resilience:
  - If STT fails, returns TranscriptionResult(status=FAILED, transcribed_text=None).
  - Strictly prevents hallucinated or fake transcripts on failure.
"""

from typing import Optional

from app.voice.providers.base import STTProvider, STTProviderError
from app.voice.voice_models import (
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptionStatus,
)


class MockSTTProvider(STTProvider):
    """Deterministic, offline mock speech-to-text provider for automated test suites."""

    def __init__(
        self,
        provider_id: str = "mock_stt",
        provider_version: str = "1.0.0",
        default_transcript: str = "Hello, Aevum!",
        simulate_failure: bool = False,
        simulate_unavailable: bool = False,
        failure_message: str = "Simulated STT provider error",
    ) -> None:
        self._provider_id = provider_id
        self._provider_version = provider_version
        self._default_transcript = default_transcript
        self._simulate_failure = simulate_failure
        self._simulate_unavailable = simulate_unavailable
        self._failure_message = failure_message
        self.invocation_count = 0
        self._audio_hash_to_text: dict[str, str] = {}

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def provider_version(self) -> str:
        return self._provider_version

    def register_transcript(self, audio_hash: str, transcript: str) -> None:
        """Register specific transcript mapping for an audio payload hash."""
        self._audio_hash_to_text[audio_hash] = transcript

    async def is_available(self) -> bool:
        return not self._simulate_unavailable

    async def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        """Transcribe audio into text deterministically."""
        self.invocation_count += 1

        if self._simulate_unavailable:
            return TranscriptionResult(
                request_id=request.request_id,
                status=TranscriptionStatus.UNAVAILABLE,
                transcribed_text=None,
                provider_id=self.provider_id,
                provider_version=self.provider_version,
                error_message="STT provider is currently unavailable.",
            )

        if self._simulate_failure:
            return TranscriptionResult(
                request_id=request.request_id,
                status=TranscriptionStatus.FAILED,
                transcribed_text=None,
                provider_id=self.provider_id,
                provider_version=self.provider_version,
                error_message=self._failure_message,
            )

        # Lookup registered mapping or fallback to default
        transcript = self._audio_hash_to_text.get(
            request.audio.sha256_hash,
            self._default_transcript,
        )

        return TranscriptionResult(
            request_id=request.request_id,
            status=TranscriptionStatus.SUCCESS,
            transcribed_text=transcript,
            provider_id=self.provider_id,
            provider_version=self.provider_version,
            error_message=None,
        )
