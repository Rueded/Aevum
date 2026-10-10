"""Voice consent guard for microphone input governance (Phase 10.4).

Governed by ADR-021 & Rule 18:
- Rule 18: Explicit, transparent user consent is mandatory before accessing microphone or voice input.
- PTT-Only Enforcement: Push-To-Talk is the only permitted input mode in Phase 10; continuous VAD is deferred.
- Failure Isolation: Unconsented audio capture attempts are rejected cleanly without recording.
"""

from typing import Optional
from app.voice.providers.base import VoiceConsentRequiredError
from app.voice.voice_models import TranscriptionRequest, VoiceInputMode


class VoiceConsentGuard:
    """Validator enforcing Rule 18 privacy consent and PTT input mode."""

    def __init__(self, allow_unconsented_bypass_for_tests: bool = False) -> None:
        self._bypass_for_tests = allow_unconsented_bypass_for_tests

    def validate_transcription_request(self, request: TranscriptionRequest) -> None:
        """Validate that request satisfies Rule 18 consent and PTT-only constraints.

        Raises:
            VoiceConsentRequiredError: If user consent has not been explicitly granted.
            ValueError: If input mode is not VoiceInputMode.PTT.
        """
        # 1. Enforce Rule 18 privacy consent
        if not request.user_consent_granted and not self._bypass_for_tests:
            raise VoiceConsentRequiredError(
                "Voice input rejected: Rule 18 requires explicit user consent before processing microphone audio."
            )

        # 2. Enforce ADR-021 Decision 3: PTT-only
        if request.input_mode != VoiceInputMode.PTT:
            raise ValueError(
                f"Unsupported voice input mode '{request.input_mode}'. Only PTT is permitted in Phase 10."
            )
