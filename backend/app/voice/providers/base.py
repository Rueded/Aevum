"""Abstract provider interfaces and base protocols for the Voice subsystem (Phase 10.1).

Governed by ADR-021:
- Provider Abstraction as Implementation Detail: Domain services depend exclusively on
  these protocols. Concrete engines (Edge-TTS, Whisper, OpenAI, Mock, etc.) are
  swappable adapters.
- Zero Live Leaks in Tests: Test environments use MockTTSProvider and MockSTTProvider.
"""

import abc
from app.voice.voice_models import (
    SynthesisRequest,
    SynthesisResult,
    TranscriptionRequest,
    TranscriptionResult,
)


class VoiceProviderError(Exception):
    """Base exception for all voice provider errors."""


class TTSProviderError(VoiceProviderError):
    """Exception raised by TTS providers during synthesis failure."""


class STTProviderError(VoiceProviderError):
    """Exception raised by STT providers during transcription failure."""


class VoiceConsentRequiredError(VoiceProviderError):
    """Exception raised when an audio action is attempted without explicit user consent (Rule 18)."""


class TTSProvider(abc.ABC):
    """Abstract interface protocol for text-to-speech providers."""

    @property
    @abc.abstractmethod
    def provider_id(self) -> str:
        """Unique provider identifier (e.g. 'mock_tts', 'edge_tts', 'openai_tts')."""

    @property
    @abc.abstractmethod
    def provider_version(self) -> str:
        """Provider implementation or engine version string."""

    @abc.abstractmethod
    async def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        """Synthesize text into speech according to request parameters."""

    @abc.abstractmethod
    async def is_available(self) -> bool:
        """Check whether the provider is currently operational and available."""


class STTProvider(abc.ABC):
    """Abstract interface protocol for speech-to-text providers."""

    @property
    @abc.abstractmethod
    def provider_id(self) -> str:
        """Unique provider identifier (e.g. 'mock_stt', 'whisper_local', 'groq_stt')."""

    @property
    @abc.abstractmethod
    def provider_version(self) -> str:
        """Provider implementation or engine version string."""

    @abc.abstractmethod
    async def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        """Transcribe speech audio into text according to request parameters."""

    @abc.abstractmethod
    async def is_available(self) -> bool:
        """Check whether the provider is currently operational and available."""
