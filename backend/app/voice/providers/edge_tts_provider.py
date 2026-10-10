"""Edge-TTS provider implementation for natural neural voice synthesis (Phase 10.5).

Governed by ADR-021:
- Provider Abstraction: Implements TTSProvider protocol.
- Emotional Prosody: Incorporates pitch and rate modulation from ProsodyConfig.
- Lock B: Decoupled Failure Resilience: Failure returns SynthesisStatus.FAILED without throwing.
- Lock E: Canonical Audio Cache Identity: Deterministic cache key matching prosody and text.
"""

from __future__ import annotations

import logging
from typing import Optional

import edge_tts

from app.voice.providers.base import TTSProvider
from app.voice.voice_models import (
    AudioChannel,
    AudioData,
    AudioFormat,
    SynthesisRequest,
    SynthesisResult,
    SynthesisStatus,
    compute_canonical_audio_cache_key,
)

logger = logging.getLogger(__name__)

DEFAULT_EDGE_VOICE = "zh-CN-XiaoxiaoNeural"


class EdgeTTSProvider(TTSProvider):
    """Production Text-to-Speech provider powered by Microsoft Edge Neural Speech."""

    def __init__(
        self,
        default_voice: str = DEFAULT_EDGE_VOICE,
        provider_id: str = "edge_tts",
        provider_version: str = "1.0.0",
    ) -> None:
        self._default_voice = default_voice
        self._provider_id = provider_id
        self._provider_version = provider_version

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def provider_version(self) -> str:
        return self._provider_version

    async def is_available(self) -> bool:
        """Edge-TTS is universally available without proprietary API keys."""
        return True

    async def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        """Synthesize natural speech audio with emotional prosody modulation."""
        if not request.text or not request.text.strip():
            return SynthesisResult(
                request_id=request.request_id,
                status=SynthesisStatus.FAILED,
                audio=None,
                cache_key=None,
                provider_id=self.provider_id,
                provider_version=self.provider_version,
                error_message="Synthesis text cannot be empty.",
            )

        voice = request.voice_id or self._default_voice
        # Translate prosody speed & pitch into Edge-TTS formatting
        rate_offset = int((request.prosody.rate_multiplier - 1.0) * 100)
        rate_str = f"{rate_offset:+d}%"

        pitch_offset_hz = int(request.prosody.pitch_shift_semitones * 4)
        pitch_str = f"{pitch_offset_hz:+d}Hz"

        try:
            communicate = edge_tts.Communicate(
                text=request.text,
                voice=voice,
                rate=rate_str,
                pitch=pitch_str,
            )

            audio_buffer = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.extend(chunk["data"])

            raw_bytes = bytes(audio_buffer)
            if not raw_bytes:
                return SynthesisResult(
                    request_id=request.request_id,
                    status=SynthesisStatus.FAILED,
                    audio=None,
                    cache_key=None,
                    provider_id=self.provider_id,
                    provider_version=self.provider_version,
                    error_message="Edge-TTS produced empty audio stream.",
                )

            # Estimate duration based on text length and byte size (approx 220ms / char, min 600ms)
            estimated_duration_ms = max(600, len(request.text) * 220)

            audio = AudioData.create(
                data=raw_bytes,
                format=AudioFormat.MP3,
                sample_rate_hz=24000,
                channels=AudioChannel.MONO,
                duration_ms=estimated_duration_ms,
            )

            cache_key = compute_canonical_audio_cache_key(
                text=request.text,
                voice_id=voice,
                audio_format=request.desired_format,
                prosody=request.prosody,
                provider_id=self.provider_id,
                provider_version=self.provider_version,
            )

            return SynthesisResult(
                request_id=request.request_id,
                status=SynthesisStatus.SUCCESS,
                audio=audio,
                cache_key=cache_key,
                provider_id=self.provider_id,
                provider_version=self.provider_version,
                error_message=None,
            )
        except Exception as exc:
            logger.warning("Edge-TTS synthesis failed: %s", exc)
            return SynthesisResult(
                request_id=request.request_id,
                status=SynthesisStatus.FAILED,
                audio=None,
                cache_key=None,
                provider_id=self.provider_id,
                provider_version=self.provider_version,
                error_message=str(exc),
            )
