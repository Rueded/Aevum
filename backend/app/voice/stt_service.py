"""Speech-to-text coordinator service with Rule 18 consent governance (Phase 10.4).

Governed by ADR-021:
- Voice Lock 1 & North Star: STT is purely an input interface ("the body");
  transcribed speech is user input (User Statement), NOT verified reality or ground truth.
- Evidence Before Truth: User statements from voice never directly call set_fact() or mutate Biography.
- Lock B: Decoupled Failure Resilience:
  - If STT fails, it produces TranscriptionResult(status=FAILED/UNAVAILABLE, transcribed_text=None).
  - STT failure creates ZERO fake/empty conversation turns.
- Rule 18: Unconsented audio capture attempts are rejected cleanly before processing.
"""

from datetime import datetime, timezone
import logging
from typing import Optional
import uuid

from app.voice.providers.base import (
    STTProvider,
    STTProviderError,
    VoiceConsentRequiredError,
)
from app.voice.voice_consent_guard import VoiceConsentGuard
from app.voice.voice_models import (
    AudioData,
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptionStatus,
    VoiceInputMode,
)

logger = logging.getLogger(__name__)


class STTService:
    """Coordinator for speech-to-text transcription with consent enforcement."""

    def __init__(
        self,
        provider: STTProvider,
        consent_guard: Optional[VoiceConsentGuard] = None,
    ) -> None:
        self._provider = provider
        self._consent_guard = consent_guard if consent_guard is not None else VoiceConsentGuard()

    @property
    def provider(self) -> STTProvider:
        """Return the active underlying STT provider adapter."""
        return self._provider

    @property
    def consent_guard(self) -> VoiceConsentGuard:
        """Return the active consent guard validator."""
        return self._consent_guard

    async def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        """Transcribe speech audio into text with consent and error isolation.

        Guarantees:
        - Unconsented requests fail closed without audio processing (Rule 18).
        - Provider exceptions are safely absorbed into TranscriptionResult(status=FAILED/UNAVAILABLE).
        - Failed transcriptions NEVER yield non-empty text (Lock B).
        """
        # 1. Enforce Rule 18 Consent and PTT-only input mode
        try:
            self._consent_guard.validate_transcription_request(request)
        except VoiceConsentRequiredError as exc:
            logger.warning("Voice input consent violation for request '%s': %s", request.request_id, exc)
            return TranscriptionResult(
                request_id=request.request_id,
                status=TranscriptionStatus.FAILED,
                transcribed_text=None,
                provider_id=self._provider.provider_id,
                provider_version=self._provider.provider_version,
                error_message=str(exc),
            )
        except ValueError as exc:
            logger.warning("Voice input mode violation for request '%s': %s", request.request_id, exc)
            return TranscriptionResult(
                request_id=request.request_id,
                status=TranscriptionStatus.FAILED,
                transcribed_text=None,
                provider_id=self._provider.provider_id,
                provider_version=self._provider.provider_version,
                error_message=str(exc),
            )

        # 2. Invoke provider with defensive fault isolation (Lock B)
        try:
            result = await self._provider.transcribe(request)
        except STTProviderError as exc:
            logger.warning("STT Provider error for request '%s': %s", request.request_id, exc)
            return TranscriptionResult(
                request_id=request.request_id,
                status=TranscriptionStatus.FAILED,
                transcribed_text=None,
                provider_id=self._provider.provider_id,
                provider_version=self._provider.provider_version,
                error_message=str(exc),
            )
        except Exception as exc:
            logger.error("Unexpected STT failure for request '%s': %s", request.request_id, exc)
            return TranscriptionResult(
                request_id=request.request_id,
                status=TranscriptionStatus.UNAVAILABLE,
                transcribed_text=None,
                provider_id=self._provider.provider_id,
                provider_version=self._provider.provider_version,
                error_message=f"STT service unavailable: {exc}",
            )

        return result

    async def transcribe_audio(
        self,
        audio: AudioData,
        user_consent_granted: bool,
        language: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> TranscriptionResult:
        """Convenience method wrapping raw audio and parameters into TranscriptionRequest."""
        req = TranscriptionRequest(
            request_id=f"trans-{uuid.uuid4()}",
            audio=audio,
            language=language,
            input_mode=VoiceInputMode.PTT,
            user_consent_granted=user_consent_granted,
            conversation_id=conversation_id,
            created_at=datetime.now(timezone.utc),
        )
        return await self.transcribe(req)
