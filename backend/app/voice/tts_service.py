"""High-level text-to-speech service and cache coordinator (Phase 10.3).

Governed by ADR-021:
- Voice Lock 1 & North Star: TTS is purely an expressive output layer ("the body");
  it possesses zero authority to mutate conversation records, biography facts, or reality state.
- Lock B: Decoupled Failure Resilience:
  - TTS failure != Conversation failure: synthesis errors or provider timeouts are caught
    and returned as structured SynthesisResult(status=FAILED/UNAVAILABLE).
  - Audio failure never raises unhandled exceptions into the conversational pipeline.
- Lock E: Canonical Audio Cache Identity:
  - Cache lookup uses compute_canonical_audio_cache_key() to guarantee 100% collision-free reuse.
- Lock F: Ephemeral Media Lifecycle Isolation:
  - Audio artifacts follow independent transient caching; cache eviction strictly never deletes domain records.
"""

from datetime import datetime, timezone
import logging
from typing import Optional
import uuid

from app.voice.audio_cache import AudioCache
from app.voice.providers.base import TTSProvider, TTSProviderError
from app.voice.voice_models import (
    AudioFormat,
    EpistemicCue,
    ProsodyConfig,
    SynthesisRequest,
    SynthesisResult,
    SynthesisStatus,
    compute_canonical_audio_cache_key,
)

logger = logging.getLogger(__name__)

DEFAULT_VOICE_ID: str = "aevum_default"


class TTSService:
    """Orchestrator for text-to-speech synthesis with canonical caching.

    Enforces decoupled failure resilience (Lock B) and zero reality mutation (Lock 1).
    """

    def __init__(
        self,
        provider: TTSProvider,
        cache: Optional[AudioCache] = None,
        default_voice_id: str = DEFAULT_VOICE_ID,
    ) -> None:
        self._provider = provider
        self._cache = cache if cache is not None else AudioCache()
        self._default_voice_id = default_voice_id

    @property
    def provider(self) -> TTSProvider:
        """Return the active underlying TTS provider adapter."""
        return self._provider

    @property
    def cache(self) -> AudioCache:
        """Return the active ephemeral audio cache."""
        return self._cache

    async def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        """Synthesize text into speech with canonical cache-aside lookups.

        Guarantees:
        - Cache hit bypasses provider synthesis entirely.
        - Provider exceptions are safely absorbed into SynthesisResult(status=FAILED/UNAVAILABLE).
        - Zero unhandled exceptions leak to conversational caller (Lock B).
        """
        # 1. Compute canonical cache key
        cache_key = compute_canonical_audio_cache_key(
            text=request.text,
            voice_id=request.voice_id,
            audio_format=request.desired_format,
            prosody=request.prosody,
            provider_id=self._provider.provider_id,
            provider_version=self._provider.provider_version,
        )

        # 2. Check cache (Lock E)
        cached_audio = self._cache.get(cache_key)
        if cached_audio is not None:
            logger.debug("TTS Cache HIT for key '%s'", cache_key)
            return SynthesisResult(
                request_id=request.request_id,
                status=SynthesisStatus.SUCCESS,
                audio=cached_audio,
                cache_key=cache_key,
                provider_id=self._provider.provider_id,
                provider_version=self._provider.provider_version,
                error_message=None,
            )

        logger.debug("TTS Cache MISS for key '%s'; invoking provider", cache_key)

        # 3. Provider invocation with defensive fault isolation (Lock B)
        try:
            result = await self._provider.synthesize(request)
        except TTSProviderError as exc:
            logger.warning("TTS Provider error for request '%s': %s", request.request_id, exc)
            return SynthesisResult(
                request_id=request.request_id,
                status=SynthesisStatus.FAILED,
                audio=None,
                cache_key=None,
                provider_id=self._provider.provider_id,
                provider_version=self._provider.provider_version,
                error_message=str(exc),
            )
        except Exception as exc:
            logger.error("Unexpected TTS failure for request '%s': %s", request.request_id, exc)
            return SynthesisResult(
                request_id=request.request_id,
                status=SynthesisStatus.UNAVAILABLE,
                audio=None,
                cache_key=None,
                provider_id=self._provider.provider_id,
                provider_version=self._provider.provider_version,
                error_message=f"TTS service unavailable: {exc}",
            )

        # 4. Cache successful result
        if result.status == SynthesisStatus.SUCCESS and result.audio is not None:
            self._cache.put(cache_key, result.audio)

        return result

    async def synthesize_text(
        self,
        text: str,
        voice_id: Optional[str] = None,
        desired_format: AudioFormat = AudioFormat.WAV,
        prosody: Optional[ProsodyConfig] = None,
        epistemic_cue: EpistemicCue = EpistemicCue.CERTAIN,
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> SynthesisResult:
        """Convenience method wrapping raw text and parameters into SynthesisRequest."""
        req = SynthesisRequest(
            request_id=f"synth-{uuid.uuid4()}",
            text=text,
            voice_id=voice_id or self._default_voice_id,
            desired_format=desired_format,
            prosody=prosody or ProsodyConfig(),
            epistemic_cue=epistemic_cue,
            conversation_id=conversation_id,
            message_id=message_id,
            created_at=datetime.now(timezone.utc),
        )
        return await self.synthesize(req)
