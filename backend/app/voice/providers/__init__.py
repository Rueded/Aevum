"""Voice providers package for Project Aevum (Phase 10)."""

from app.voice.providers.base import (
    STTProvider,
    STTProviderError,
    TTSProvider,
    TTSProviderError,
    VoiceConsentRequiredError,
    VoiceProviderError,
)
from app.voice.providers.edge_tts_provider import EdgeTTSProvider
from app.voice.providers.gemini_stt_provider import GeminiSTTProvider
from app.voice.providers.mock_tts import MockTTSProvider
from app.voice.providers.mock_stt import MockSTTProvider
from app.voice.providers.streaming_base import (
    MockStreamingSTTProvider,
    MockStreamingTTSProvider,
    StreamingSTTProvider,
    StreamingTTSProvider,
    pack_audio_frame_envelope,
    unpack_audio_frame_envelope,
)

__all__ = [
    "EdgeTTSProvider",
    "GeminiSTTProvider",
    "MockSTTProvider",
    "MockStreamingSTTProvider",
    "MockStreamingTTSProvider",
    "MockTTSProvider",
    "STTProvider",
    "STTProviderError",
    "StreamingSTTProvider",
    "StreamingTTSProvider",
    "TTSProvider",
    "TTSProviderError",
    "VoiceConsentRequiredError",
    "VoiceProviderError",
    "pack_audio_frame_envelope",
    "unpack_audio_frame_envelope",
]

