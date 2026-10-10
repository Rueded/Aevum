"""Gemini-powered Multimodal Speech-to-Text provider implementation (Phase 10.5).

Governed by ADR-021:
- Provider Abstraction: Implements STTProvider protocol.
- Sensory Boundary: Audio transcription is sensory input only, never direct reality mutation.
- Lock B: Decoupled Failure Resilience: Failure returns TranscriptionStatus.FAILED without throwing to caller.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from google import genai
from google.genai import types

from app.core.config import settings
from app.voice.providers.base import STTProvider
from app.voice.voice_models import (
    AudioFormat,
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptionStatus,
)

logger = logging.getLogger(__name__)


def detect_audio_mime_type(data: bytes, default_format: Optional[AudioFormat] = None) -> str:
    """Detect MIME type by sniffing header magic bytes or falling back to AudioFormat."""
    if len(data) >= 4:
        # WebM / EBML container: 1A 45 DF A3
        if data[:4] == b"\x1a\x45\xdf\xa3":
            return "audio/webm"
        # RIFF WAV container: RIFF....WAVE
        if data[:4] == b"RIFF":
            return "audio/wav"
        # OGG container: OggS
        if data[:4] == b"OggS":
            return "audio/ogg"

    if len(data) >= 3 and data[:3] == b"ID3":
        return "audio/mp3"

    if len(data) >= 2 and data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio/mp3"

    # Fallback to requested AudioFormat
    if default_format == AudioFormat.MP3:
        return "audio/mp3"
    if default_format == AudioFormat.WEBM:
        return "audio/webm"
    if default_format == AudioFormat.OGG_OPUS:
        return "audio/ogg"

    return "audio/wav"


class GeminiSTTProvider(STTProvider):
    """Production speech-to-text provider utilizing Gemini multimodal audio understanding."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        client: Optional[Any] = None,
    ) -> None:
        self._api_key = api_key or settings.gemini_api_key
        self._model_name = model_name or settings.gemini_model or "gemini-2.5-flash"
        self._client = client
        if self._client is None and self._api_key:
            self._client = genai.Client(api_key=self._api_key)

    @property
    def provider_id(self) -> str:
        return "gemini_stt"

    @property
    def provider_version(self) -> str:
        return "1.0.0"

    async def is_available(self) -> bool:
        """Check whether the Gemini STT provider is configured and available."""
        return bool(self._api_key and self._client)

    async def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        """Transcribe speech audio into verbatim text via Gemini multimodal recognition."""
        if not await self.is_available():
            return TranscriptionResult(
                request_id=request.request_id,
                status=TranscriptionStatus.UNAVAILABLE,
                transcribed_text=None,
                provider_id=self.provider_id,
                provider_version=self.provider_version,
                error_message="Gemini STT provider is not configured (missing GEMINI_API_KEY).",
            )

        if not request.audio or not request.audio.data:
            return TranscriptionResult(
                request_id=request.request_id,
                status=TranscriptionStatus.FAILED,
                transcribed_text=None,
                provider_id=self.provider_id,
                provider_version=self.provider_version,
                error_message="Audio payload is empty.",
            )

        try:
            mime_type = detect_audio_mime_type(
                request.audio.data,
                default_format=request.audio.format,
            )

            prompt = (
                "Please transcribe the speech in this audio verbatim into text. "
                "Do not include any introductory remarks, explanations, speaker tags, timestamps, "
                "or commentary. Output ONLY the exact transcribed words. "
                "If the audio is completely silent or contains only non-speech noise, return an empty string."
            )

            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=[
                    types.Part.from_bytes(data=request.audio.data, mime_type=mime_type),
                    prompt,
                ],
            )

            transcribed = response.text.strip() if response.text else ""

            return TranscriptionResult(
                request_id=request.request_id,
                status=TranscriptionStatus.SUCCESS,
                transcribed_text=transcribed,
                provider_id=self.provider_id,
                provider_version=self.provider_version,
                error_message=None,
            )
        except Exception as exc:
            logger.warning("Gemini STT transcription failed: %s", exc)
            return TranscriptionResult(
                request_id=request.request_id,
                status=TranscriptionStatus.FAILED,
                transcribed_text=None,
                provider_id=self.provider_id,
                provider_version=self.provider_version,
                error_message=str(exc),
            )
