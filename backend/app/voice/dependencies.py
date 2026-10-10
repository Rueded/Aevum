"""FastAPI dependency injection providers for the Voice subsystem (Phase 10.5).

Governed by ADR-021:
- Provider Abstraction: Services depend exclusively on TTSProvider and STTProvider protocols.
- Mock-for-tests: Default provider factories instantiate deterministic mock providers,
  guaranteeing zero network or live audio engine leakage during automated tests.
"""

from functools import lru_cache
from typing import Optional

from fastapi import Depends

from app.core.config import settings
from app.voice.audio_cache import AudioCache
from app.voice.providers.base import STTProvider, TTSProvider
from app.voice.providers.edge_tts_provider import EdgeTTSProvider
from app.voice.providers.gemini_stt_provider import GeminiSTTProvider
from app.voice.providers.mock_stt import MockSTTProvider
from app.voice.providers.mock_tts import MockTTSProvider
from app.voice.providers.streaming_base import (
    MockStreamingSTTProvider,
    MockStreamingTTSProvider,
    StreamingSTTProvider,
    StreamingTTSProvider,
)
from app.voice.realtime_session_manager import RealtimeCallSessionManager
from app.voice.stt_service import STTService
from app.voice.tts_service import TTSService
from app.voice.voice_consent_guard import VoiceConsentGuard

# Global in-memory singleton cache for the lifetime of the application
_GLOBAL_AUDIO_CACHE: Optional[AudioCache] = None


def get_audio_cache() -> AudioCache:
    """Provide singleton AudioCache instance."""
    global _GLOBAL_AUDIO_CACHE
    if _GLOBAL_AUDIO_CACHE is None:
        _GLOBAL_AUDIO_CACHE = AudioCache(max_entries=256, default_ttl_seconds=3600)
    return _GLOBAL_AUDIO_CACHE


def get_tts_provider() -> TTSProvider:
    """Provide active TTSProvider (defaults to EdgeTTSProvider outside test environments)."""
    if settings.environment == "test":
        return MockTTSProvider()
    return EdgeTTSProvider()


def get_stt_provider() -> STTProvider:
    """Provide active STTProvider (defaults to GeminiSTTProvider outside test environments)."""
    if settings.environment == "test":
        return MockSTTProvider()
    if settings.gemini_api_key:
        return GeminiSTTProvider()
    return MockSTTProvider()


def get_voice_consent_guard() -> VoiceConsentGuard:
    """Provide VoiceConsentGuard validator."""
    return VoiceConsentGuard()


def get_tts_service(
    provider: TTSProvider = Depends(get_tts_provider),
    cache: AudioCache = Depends(get_audio_cache),
) -> TTSService:
    """Provide configured TTSService instance."""
    return TTSService(provider=provider, cache=cache)


def get_stt_service(
    provider: STTProvider = Depends(get_stt_provider),
    guard: VoiceConsentGuard = Depends(get_voice_consent_guard),
) -> STTService:
    """Provide configured STTService instance."""
    return STTService(provider=provider, consent_guard=guard)


# Global in-memory singleton for the realtime call session manager
_GLOBAL_SESSION_MANAGER: Optional[RealtimeCallSessionManager] = None


def get_realtime_session_manager() -> RealtimeCallSessionManager:
    """Provide singleton RealtimeCallSessionManager instance."""
    global _GLOBAL_SESSION_MANAGER
    if _GLOBAL_SESSION_MANAGER is None:
        _GLOBAL_SESSION_MANAGER = RealtimeCallSessionManager()
    return _GLOBAL_SESSION_MANAGER


def get_streaming_stt_provider() -> StreamingSTTProvider:
    """Provide active StreamingSTTProvider (defaults to deterministic MockStreamingSTTProvider)."""
    return MockStreamingSTTProvider()


def get_streaming_tts_provider() -> StreamingTTSProvider:
    """Provide active StreamingTTSProvider (defaults to deterministic MockStreamingTTSProvider)."""
    return MockStreamingTTSProvider()

