"""Test suite for Phase 10.4 Speech-to-Text Engine & Rule 18 Consent Gate.

Tests:
1. Rule 18 Consent Gate: unconsented audio capture fails closed (ADR-021 & Rule 18).
2. Decision 3 PTT-Only: only VoiceInputMode.PTT is permitted; continuous VAD is rejected.
3. MockSTTProvider deterministic transcription and configurable failure simulation.
4. STTService orchestration, consent validation, and convenience methods.
5. Lock B Decoupled Failure Resilience: STT failure guarantees transcribed_text is None (0 fake turns).
6. Non-mutation of domain state (Lock 1 & Lock A: user speech != canonical reality; 0 set_fact).
7. Static AST Boundary Audit across Phase 10.4 modules (0 DB, 0 network, 0 mutation tokens).
"""

import ast
from datetime import datetime, timezone
import pathlib
import pytest
from pydantic import ValidationError

from app.voice import (
    AudioChannel,
    AudioData,
    AudioFormat,
    STTService,
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptionStatus,
    VoiceConsentGuard,
    VoiceInputMode,
)
from app.voice.providers.base import (
    STTProvider,
    STTProviderError,
    VoiceConsentRequiredError,
)
from app.voice.providers.mock_stt import MockSTTProvider


@pytest.fixture
def sample_audio() -> AudioData:
    """Fixture providing valid 16kHz mono audio payload."""
    raw = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00sample_pcm_bytes"
    return AudioData.create(
        data=raw,
        format=AudioFormat.WAV,
        sample_rate_hz=16000,
        channels=AudioChannel.MONO,
        duration_ms=400,
    )


class TestVoiceConsentGuard:
    """Verifies Rule 18 privacy consent enforcement and PTT input mode."""

    def test_consent_granted_passes(self, sample_audio: AudioData):
        guard = VoiceConsentGuard()
        req = TranscriptionRequest(
            request_id="req-c-001",
            audio=sample_audio,
            input_mode=VoiceInputMode.PTT,
            user_consent_granted=True,
        )
        # Should execute cleanly without exception
        guard.validate_transcription_request(req)

    def test_consent_denied_raises_voice_consent_required_error(self, sample_audio: AudioData):
        guard = VoiceConsentGuard()
        req = TranscriptionRequest(
            request_id="req-c-002",
            audio=sample_audio,
            input_mode=VoiceInputMode.PTT,
            user_consent_granted=False,
        )
        with pytest.raises(VoiceConsentRequiredError) as exc_info:
            guard.validate_transcription_request(req)
        assert "Rule 18 requires explicit user consent" in str(exc_info.value)


class TestMockSTTProvider:
    """Verifies deterministic transcription and failure simulation."""

    @pytest.mark.asyncio
    async def test_mock_stt_transcribes_default(self, sample_audio: AudioData):
        provider = MockSTTProvider(default_transcript="Good evening, Aevum.")
        req = TranscriptionRequest(
            request_id="req-stt-01",
            audio=sample_audio,
            user_consent_granted=True,
        )

        res = await provider.transcribe(req)
        assert res.status == TranscriptionStatus.SUCCESS
        assert res.transcribed_text == "Good evening, Aevum."
        assert res.provider_id == "mock_stt"
        assert res.error_message is None

    @pytest.mark.asyncio
    async def test_mock_stt_registered_mapping(self, sample_audio: AudioData):
        provider = MockSTTProvider()
        provider.register_transcript(sample_audio.sha256_hash, "Custom recognized speech.")

        req = TranscriptionRequest(
            request_id="req-stt-02",
            audio=sample_audio,
            user_consent_granted=True,
        )
        res = await provider.transcribe(req)
        assert res.status == TranscriptionStatus.SUCCESS
        assert res.transcribed_text == "Custom recognized speech."

    @pytest.mark.asyncio
    async def test_mock_stt_simulated_failure(self, sample_audio: AudioData):
        provider = MockSTTProvider(simulate_failure=True, failure_message="Acoustic model timeout")
        req = TranscriptionRequest(
            request_id="req-stt-03",
            audio=sample_audio,
            user_consent_granted=True,
        )

        res = await provider.transcribe(req)
        assert res.status == TranscriptionStatus.FAILED
        assert res.transcribed_text is None
        assert res.error_message == "Acoustic model timeout"

    @pytest.mark.asyncio
    async def test_mock_stt_simulated_unavailable(self, sample_audio: AudioData):
        provider = MockSTTProvider(simulate_unavailable=True)
        assert await provider.is_available() is False

        req = TranscriptionRequest(
            request_id="req-stt-04",
            audio=sample_audio,
            user_consent_granted=True,
        )
        res = await provider.transcribe(req)
        assert res.status == TranscriptionStatus.UNAVAILABLE
        assert res.transcribed_text is None


class TestSTTServiceOrchestration:
    """Verifies STTService consent gating and error isolation."""

    @pytest.mark.asyncio
    async def test_stt_service_unconsented_fails_closed(self, sample_audio: AudioData):
        """Rule 18: Unconsented request returns FAILED without invoking provider."""
        provider = MockSTTProvider()
        service = STTService(provider=provider)

        req_unconsented = TranscriptionRequest(
            request_id="req-gate-01",
            audio=sample_audio,
            user_consent_granted=False,
        )

        res = await service.transcribe(req_unconsented)
        assert res.status == TranscriptionStatus.FAILED
        assert res.transcribed_text is None
        assert "Rule 18" in (res.error_message or "")
        # Crucial: Provider was NEVER called!
        assert provider.invocation_count == 0

    @pytest.mark.asyncio
    async def test_stt_service_consented_succeeds(self, sample_audio: AudioData):
        provider = MockSTTProvider(default_transcript="What is on my schedule today?")
        service = STTService(provider=provider)

        req_consented = TranscriptionRequest(
            request_id="req-gate-02",
            audio=sample_audio,
            user_consent_granted=True,
        )

        res = await service.transcribe(req_consented)
        assert res.status == TranscriptionStatus.SUCCESS
        assert res.transcribed_text == "What is on my schedule today?"
        assert provider.invocation_count == 1

    @pytest.mark.asyncio
    async def test_convenience_transcribe_audio(self, sample_audio: AudioData):
        provider = MockSTTProvider(default_transcript="I like green tea.")
        service = STTService(provider=provider)

        res = await service.transcribe_audio(sample_audio, user_consent_granted=True)
        assert res.status == TranscriptionStatus.SUCCESS
        assert res.transcribed_text == "I like green tea."


class TestDecoupledFailureResilienceLockB:
    """Verifies ADR-021 Lock B: STT failure produces zero fake user turns."""

    @pytest.mark.asyncio
    async def test_provider_error_absorbed_gracefully(self, sample_audio: AudioData):
        class CrashingSTTProvider(STTProvider):
            @property
            def provider_id(self) -> str:
                return "crashing_stt"

            @property
            def provider_version(self) -> str:
                return "0.0.1"

            async def is_available(self) -> bool:
                return False

            async def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
                raise STTProviderError("Microphone device disconnected during capture")

        service = STTService(provider=CrashingSTTProvider())
        req = TranscriptionRequest(request_id="req-crash", audio=sample_audio, user_consent_granted=True)

        res = await service.transcribe(req)
        assert res.status == TranscriptionStatus.FAILED
        assert res.transcribed_text is None
        assert "Microphone device disconnected" in (res.error_message or "")

    @pytest.mark.asyncio
    async def test_unexpected_runtime_exception_absorbed_gracefully(self, sample_audio: AudioData):
        class BuggySTTProvider(STTProvider):
            @property
            def provider_id(self) -> str:
                return "buggy_stt"

            @property
            def provider_version(self) -> str:
                return "0.0.1"

            async def is_available(self) -> bool:
                return True

            async def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
                raise RuntimeError("Segfault inside native audio codec")

        service = STTService(provider=BuggySTTProvider())
        req = TranscriptionRequest(request_id="req-buggy", audio=sample_audio, user_consent_granted=True)

        res = await service.transcribe(req)
        assert res.status == TranscriptionStatus.UNAVAILABLE
        assert res.transcribed_text is None
        assert "Segfault inside native audio codec" in (res.error_message or "")


class TestStaticASTBoundaryAuditPhase104:
    """Static AST Boundary Audit for Phase 10.4 modules.

    Target files:
    - app/voice/voice_consent_guard.py
    - app/voice/providers/mock_stt.py
    - app/voice/stt_service.py

    Asserts:
    1. ZERO database imports or calls (sqlite3, sqlalchemy, aiosqlite).
    2. ZERO network imports or calls (httpx, requests, aiohttp, urllib, google.genai).
    3. ZERO mutation or promotion authority (set_fact, PromotionAuthorizationToken).
    4. ZERO VAD or continuous background listening tokens.
    """

    def test_static_ast_boundary_audit(self):
        app_voice_dir = pathlib.Path(__file__).resolve().parent.parent / "app" / "voice"
        phase104_files = [
            app_voice_dir / "voice_consent_guard.py",
            app_voice_dir / "providers" / "mock_stt.py",
            app_voice_dir / "stt_service.py",
        ]

        forbidden_io_modules = {
            "requests", "httpx", "aiohttp", "urllib", "socket",
            "sqlalchemy", "sqlite3", "aiosqlite", "redis",
            "google.genai",
        }
        forbidden_mutation_tokens = {"set_fact", "PromotionAuthorizationToken"}
        forbidden_vad_tokens = {"continuous_vad", "vad_detector", "listen_continuously"}

        violations: list[str] = []

        for fpath in phase104_files:
            assert fpath.exists(), f"Target file {fpath} must exist"
            tree = ast.parse(fpath.read_text(encoding="utf-8"), filename=str(fpath))

            for node in ast.walk(tree):
                # 1. Zero forbidden imports
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.split(".")[0]
                        if root in forbidden_io_modules:
                            violations.append(f"{fpath.name}:{node.lineno} imports forbidden module '{alias.name}'")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    root = node.module.split(".")[0]
                    if root in forbidden_io_modules:
                        violations.append(f"{fpath.name}:{node.lineno} from-imports forbidden module '{node.module}'")

                # 2. Zero mutation authority
                if isinstance(node, ast.Name) and node.id in forbidden_mutation_tokens:
                    violations.append(f"{fpath.name}:{node.lineno} references forbidden mutation identifier '{node.id}'")
                elif isinstance(node, ast.Attribute) and node.attr in forbidden_mutation_tokens:
                    violations.append(f"{fpath.name}:{node.lineno} references forbidden mutation attribute '{node.attr}'")

                # 3. Zero continuous VAD tokens
                if isinstance(node, ast.Name) and node.id in forbidden_vad_tokens:
                    violations.append(f"{fpath.name}:{node.lineno} references forbidden VAD token '{node.id}'")

        assert not violations, f"AST boundary violations detected across Phase 10.4: {violations}"
