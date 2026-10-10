"""Mock TTS provider implementation for deterministic offline testing (Phase 10.3).

Governed by ADR-021:
- Provider Abstraction as Implementation Detail: MockTTSProvider implements TTSProvider.
- Zero Live Leaks in Tests: Unit tests and Golden benchmarks use MockTTSProvider exclusively.
- Lock B: Decoupled Failure Resilience: Configurable failure modes to test decoupled error handling.
"""

import struct
from typing import Optional

from app.voice.providers.base import TTSProvider, TTSProviderError
from app.voice.voice_models import (
    AudioChannel,
    AudioData,
    AudioFormat,
    SynthesisRequest,
    SynthesisResult,
    SynthesisStatus,
    compute_canonical_audio_cache_key,
)


def _build_synthetic_wav_bytes(text: str, sample_rate: int = 24000) -> bytes:
    """Generate deterministic, structurally valid 16-bit mono PCM WAV bytes.

    Derived directly from text length to guarantee determinism without audio hardware.
    """
    # Duration proportional to text length: approx 60ms per character, minimum 200ms
    duration_ms = max(200, min(5000, len(text) * 60))
    num_samples = int(sample_rate * (duration_ms / 1000.0))

    # Generate synthetic silent/sine-like PCM 16-bit samples
    pcm_samples = bytearray(num_samples * 2)
    # Fill with deterministic subtle pattern
    for i in range(num_samples):
        val = int(500 * ((i % 100) / 100.0 - 0.5))
        struct.pack_into("<h", pcm_samples, i * 2, val)

    pcm_data = bytes(pcm_samples)
    data_size = len(pcm_data)
    channels = 1
    bits_per_sample = 16
    byte_rate = sample_rate * channels * (bits_per_sample // 8)
    block_align = channels * (bits_per_sample // 8)

    # 44-byte standard RIFF WAV header
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,  # PCM subchunk size
        1,   # Audio format (PCM)
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    return header + pcm_data


class MockTTSProvider(TTSProvider):
    """Deterministic, offline mock text-to-speech provider for automated test suites."""

    def __init__(
        self,
        provider_id: str = "mock_tts",
        provider_version: str = "1.0.0",
        simulate_failure: bool = False,
        simulate_unavailable: bool = False,
        failure_message: str = "Simulated TTS provider error",
    ) -> None:
        self._provider_id = provider_id
        self._provider_version = provider_version
        self._simulate_failure = simulate_failure
        self._simulate_unavailable = simulate_unavailable
        self._failure_message = failure_message
        self.invocation_count = 0

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def provider_version(self) -> str:
        return self._provider_version

    async def is_available(self) -> bool:
        return not self._simulate_unavailable

    async def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        """Synthesize text into deterministic audio payload."""
        self.invocation_count += 1

        if self._simulate_unavailable:
            return SynthesisResult(
                request_id=request.request_id,
                status=SynthesisStatus.UNAVAILABLE,
                audio=None,
                cache_key=None,
                provider_id=self.provider_id,
                provider_version=self.provider_version,
                error_message="TTS provider is currently unavailable.",
            )

        if self._simulate_failure:
            return SynthesisResult(
                request_id=request.request_id,
                status=SynthesisStatus.FAILED,
                audio=None,
                cache_key=None,
                provider_id=self.provider_id,
                provider_version=self.provider_version,
                error_message=self._failure_message,
            )

        # Generate deterministic synthetic WAV bytes
        sample_rate = 24000
        raw_bytes = _build_synthetic_wav_bytes(request.text, sample_rate=sample_rate)
        duration_ms = max(200, min(5000, len(request.text) * 60))

        audio = AudioData.create(
            data=raw_bytes,
            format=request.desired_format,
            sample_rate_hz=sample_rate,
            channels=AudioChannel.MONO,
            duration_ms=duration_ms,
        )

        cache_key = compute_canonical_audio_cache_key(
            text=request.text,
            voice_id=request.voice_id,
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
