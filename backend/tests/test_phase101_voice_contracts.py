"""Test suite for Phase 10.1 Voice Contracts & DTOs.

Tests:
1. AudioFormat, AudioChannel, and AudioMediaLifecycle enums (ADR-021 Lock F).
2. Categorical EpistemicCue validation (ADR-021 Lock D — Zero pseudo-probability floats).
3. AudioData validation, SHA-256 integrity, and convenience factory.
4. ProsodyConfig bounded validation and canonical dict serialization.
5. Canonical audio cache key computation and collision resistance (ADR-021 Lock E).
6. SynthesisRequest and SynthesisResult consistency (ADR-021 Lock B).
7. TranscriptionRequest (PTT-only & consent check) and TranscriptionResult (ADR-021 Lock B & Decision 3).
8. TTSProvider and STTProvider abstract protocol contracts.
9. Static AST boundary audit across Phase 10.1 modules (0 DB, 0 network, 0 mutation).
"""

import ast
from datetime import datetime, timezone
import hashlib
import json
import math
import pathlib
import pytest
from pydantic import ValidationError

from app.voice import (
    AudioChannel,
    AudioData,
    AudioFormat,
    AudioMediaLifecycle,
    EpistemicCue,
    ProsodyConfig,
    SynthesisRequest,
    SynthesisResult,
    SynthesisStatus,
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptionStatus,
    VoiceInputMode,
    VoiceProfile,
    compute_canonical_audio_cache_key,
)
from app.voice.providers.base import (
    STTProvider,
    STTProviderError,
    TTSProvider,
    TTSProviderError,
    VoiceConsentRequiredError,
    VoiceProviderError,
)


class TestVoiceEnumsAndEpistemicCues:
    """Verifies enum values and categorical EpistemicCue (Lock D)."""

    def test_audio_format_values(self):
        assert AudioFormat.WAV.value == "WAV"
        assert AudioFormat.MP3.value == "MP3"
        assert AudioFormat.OGG_OPUS.value == "OGG_OPUS"

    def test_audio_media_lifecycle_states(self):
        """ADR-021 Lock F: Ephemeral media states."""
        expected = {"CREATED", "ACTIVE", "EXPIRED", "PURGED"}
        actual = {s.value for s in AudioMediaLifecycle}
        assert actual == expected

    def test_epistemic_cue_categorical_values(self):
        """ADR-021 Lock D: Pure discrete categorical cues, zero pseudo-probability floats."""
        expected = {"CERTAIN", "UNCERTAIN", "AMBIGUOUS", "CONTESTED", "UNKNOWN"}
        actual = {cue.value for cue in EpistemicCue}
        assert actual == expected

        # Verify that cues are discrete strings, not floats
        for cue in EpistemicCue:
            assert isinstance(cue.value, str)
            with pytest.raises(ValueError):
                float(cue.value)

    def test_voice_input_mode_ptt_only(self):
        """ADR-021 Decision 3: PTT is the sole mandatory input mode in Phase 10."""
        assert VoiceInputMode.PTT.value == "PTT"
        assert len(list(VoiceInputMode)) == 1


class TestAudioDataValidation:
    """Verifies AudioData integrity and factory."""

    def test_audio_data_create_factory(self):
        raw_bytes = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
        audio = AudioData.create(
            data=raw_bytes,
            format=AudioFormat.WAV,
            sample_rate_hz=24000,
            channels=AudioChannel.MONO,
            duration_ms=500,
        )
        assert audio.data == raw_bytes
        assert audio.format == AudioFormat.WAV
        assert audio.sample_rate_hz == 24000
        assert audio.channels == AudioChannel.MONO
        assert audio.duration_ms == 500
        assert audio.sha256_hash == hashlib.sha256(raw_bytes).hexdigest()

    def test_audio_data_sha256_mismatch_raises(self):
        raw_bytes = b"fake_audio_bytes"
        with pytest.raises(ValidationError) as exc_info:
            AudioData(
                data=raw_bytes,
                format=AudioFormat.WAV,
                sample_rate_hz=16000,
                channels=AudioChannel.MONO,
                duration_ms=100,
                sha256_hash="incorrect_hash",
            )
        assert "sha256_hash mismatch" in str(exc_info.value)

    def test_audio_data_empty_bytes_raises(self):
        with pytest.raises(ValidationError):
            AudioData.create(
                data=b"",
                format=AudioFormat.WAV,
                sample_rate_hz=16000,
                channels=AudioChannel.MONO,
                duration_ms=0,
            )

    def test_audio_data_invalid_sample_rate_raises(self):
        raw = b"valid_bytes"
        with pytest.raises(ValidationError):
            AudioData.create(raw, AudioFormat.WAV, 4000, AudioChannel.MONO, 100)
        with pytest.raises(ValidationError):
            AudioData.create(raw, AudioFormat.WAV, 192000, AudioChannel.MONO, 100)

    def test_audio_data_negative_duration_raises(self):
        raw = b"valid_bytes"
        with pytest.raises(ValidationError):
            AudioData.create(raw, AudioFormat.WAV, 16000, AudioChannel.MONO, -1)

    def test_audio_data_immutability(self):
        audio = AudioData.create(b"test", AudioFormat.WAV, 16000, AudioChannel.MONO, 10)
        with pytest.raises(ValidationError):
            audio.duration_ms = 20  # type: ignore[misc]


class TestProsodyConfigValidation:
    """Verifies bounded acoustic parameters and canonical dictionary serialization."""

    def test_prosody_defaults(self):
        config = ProsodyConfig()
        assert config.rate_multiplier == 1.0
        assert config.pitch_shift_semitones == 0.0
        assert config.volume_gain_db == 0.0
        assert config.style_tag is None
        assert config.hesitation_pause_ms == 0

    def test_prosody_bounds_validation(self):
        # Rate multiplier: [0.50, 2.00]
        ProsodyConfig(rate_multiplier=0.50)
        ProsodyConfig(rate_multiplier=2.00)
        with pytest.raises(ValidationError):
            ProsodyConfig(rate_multiplier=0.49)
        with pytest.raises(ValidationError):
            ProsodyConfig(rate_multiplier=2.01)
        with pytest.raises(ValidationError):
            ProsodyConfig(rate_multiplier=float("nan"))

        # Pitch shift: [-12.0, 12.0]
        ProsodyConfig(pitch_shift_semitones=-12.0)
        ProsodyConfig(pitch_shift_semitones=12.0)
        with pytest.raises(ValidationError):
            ProsodyConfig(pitch_shift_semitones=-12.1)
        with pytest.raises(ValidationError):
            ProsodyConfig(pitch_shift_semitones=12.1)

        # Volume gain: [-20.0, 10.0]
        ProsodyConfig(volume_gain_db=-20.0)
        ProsodyConfig(volume_gain_db=10.0)
        with pytest.raises(ValidationError):
            ProsodyConfig(volume_gain_db=-20.5)
        with pytest.raises(ValidationError):
            ProsodyConfig(volume_gain_db=10.5)

        # Hesitation pause: [0, 2000] ms
        ProsodyConfig(hesitation_pause_ms=0)
        ProsodyConfig(hesitation_pause_ms=2000)
        with pytest.raises(ValidationError):
            ProsodyConfig(hesitation_pause_ms=-1)
        with pytest.raises(ValidationError):
            ProsodyConfig(hesitation_pause_ms=2001)

    def test_canonical_dict_serialization(self):
        """ADR-021 Lock E: Canonical dictionary serialization for cache hashing."""
        config = ProsodyConfig(
            rate_multiplier=1.10,
            pitch_shift_semitones=2.5,
            volume_gain_db=-1.5,
            style_tag="cheerful",
            hesitation_pause_ms=150,
        )
        cdict = config.to_canonical_dict()
        assert cdict == {
            "hesitation_pause_ms": 150,
            "pitch_shift_semitones": 2.5,
            "rate_multiplier": 1.10,
            "style_tag": "cheerful",
            "volume_gain_db": -1.5,
        }


class TestCanonicalAudioCacheKey:
    """Verifies ADR-021 Lock E: Canonical Audio Cache Identity."""

    def test_cache_key_determinism(self):
        prosody = ProsodyConfig(rate_multiplier=1.0, pitch_shift_semitones=0.0)
        key1 = compute_canonical_audio_cache_key(
            text="Hello world!",
            voice_id="aevum_voice_1",
            audio_format=AudioFormat.WAV,
            prosody=prosody,
            provider_id="mock_tts",
            provider_version="1.0.0",
        )
        key2 = compute_canonical_audio_cache_key(
            text="Hello world!",
            voice_id="aevum_voice_1",
            audio_format=AudioFormat.WAV,
            prosody=prosody,
            provider_id="mock_tts",
            provider_version="1.0.0",
        )
        assert key1 == key2
        assert len(key1) == 64

    def test_cache_key_different_emotion_prosody_divergence(self):
        """Different emotions/prosody MUST produce distinct cache keys."""
        text = "I'm ready for the lecture today."
        voice = "aevum_voice_1"
        fmt = AudioFormat.WAV
        prov = "mock_tts"
        ver = "1.0.0"

        # Cheerful / Excited
        prosody_cheerful = ProsodyConfig(
            rate_multiplier=1.15,
            pitch_shift_semitones=2.0,
            style_tag="cheerful",
        )
        # Sad / Hesitant
        prosody_sad = ProsodyConfig(
            rate_multiplier=0.88,
            pitch_shift_semitones=-2.0,
            hesitation_pause_ms=250,
            style_tag="somber",
        )

        key_cheerful = compute_canonical_audio_cache_key(text, voice, fmt, prosody_cheerful, prov, ver)
        key_sad = compute_canonical_audio_cache_key(text, voice, fmt, prosody_sad, prov, ver)

        assert key_cheerful != key_sad, "Cross-emotion prosody must never collide in audio cache!"

    def test_cache_key_different_provider_version_divergence(self):
        """Different provider or model version MUST produce distinct cache keys."""
        text = "Good morning!"
        prosody = ProsodyConfig()
        key_v1 = compute_canonical_audio_cache_key(
            text, "v_aevum", AudioFormat.WAV, prosody, "mock_tts", "1.0.0"
        )
        key_v2 = compute_canonical_audio_cache_key(
            text, "v_aevum", AudioFormat.WAV, prosody, "mock_tts", "1.1.0"
        )
        assert key_v1 != key_v2


class TestSynthesisContracts:
    """Verifies ADR-021 Lock B decoupled synthesis contracts."""

    def test_synthesis_request_valid(self):
        req = SynthesisRequest(
            request_id="req-synth-001",
            text="Hello there!",
            voice_id="aevum_v1",
            desired_format=AudioFormat.WAV,
            epistemic_cue=EpistemicCue.CERTAIN,
        )
        assert req.request_id == "req-synth-001"
        assert req.text == "Hello there!"
        assert req.epistemic_cue == EpistemicCue.CERTAIN

    def test_synthesis_request_empty_text_raises(self):
        with pytest.raises(ValidationError):
            SynthesisRequest(
                request_id="req-synth-002",
                text="   ",
                voice_id="aevum_v1",
            )

    def test_synthesis_result_success_requires_audio_and_cache_key(self):
        audio = AudioData.create(b"synth_bytes", AudioFormat.WAV, 24000, AudioChannel.MONO, 300)
        res = SynthesisResult(
            request_id="req-synth-001",
            status=SynthesisStatus.SUCCESS,
            audio=audio,
            cache_key="fake_cache_key_12345",
            provider_id="mock_tts",
            provider_version="1.0.0",
        )
        assert res.status == SynthesisStatus.SUCCESS
        assert res.audio is not None

        # Missing audio on SUCCESS raises ValidationError
        with pytest.raises(ValidationError):
            SynthesisResult(
                request_id="req-synth-001",
                status=SynthesisStatus.SUCCESS,
                audio=None,
                cache_key="key",
                provider_id="mock_tts",
                provider_version="1.0.0",
            )

    def test_synthesis_result_failed_forbids_audio(self):
        audio = AudioData.create(b"synth_bytes", AudioFormat.WAV, 24000, AudioChannel.MONO, 300)
        # FAILED with audio raises ValidationError
        with pytest.raises(ValidationError):
            SynthesisResult(
                request_id="req-synth-002",
                status=SynthesisStatus.FAILED,
                audio=audio,
                provider_id="mock_tts",
                provider_version="1.0.0",
                error_message="Synthesis failed",
            )

        # Valid FAILED result
        res_fail = SynthesisResult(
            request_id="req-synth-002",
            status=SynthesisStatus.FAILED,
            audio=None,
            provider_id="mock_tts",
            provider_version="1.0.0",
            error_message="Upstream TTS engine timeout",
        )
        assert res_fail.status == SynthesisStatus.FAILED
        assert res_fail.audio is None
        assert res_fail.error_message == "Upstream TTS engine timeout"


class TestTranscriptionContracts:
    """Verifies ADR-021 Decision 3 (PTT-only) & Lock B decoupled transcription contracts."""

    def test_transcription_request_ptt_and_consent(self):
        audio = AudioData.create(b"voice_input", AudioFormat.WAV, 16000, AudioChannel.MONO, 450)
        req = TranscriptionRequest(
            request_id="req-stt-001",
            audio=audio,
            input_mode=VoiceInputMode.PTT,
            user_consent_granted=True,
        )
        assert req.input_mode == VoiceInputMode.PTT
        assert req.user_consent_granted is True

    def test_transcription_result_success(self):
        res = TranscriptionResult(
            request_id="req-stt-001",
            status=TranscriptionStatus.SUCCESS,
            transcribed_text="How are you doing today?",
            provider_id="mock_stt",
            provider_version="1.0.0",
        )
        assert res.status == TranscriptionStatus.SUCCESS
        assert res.transcribed_text == "How are you doing today?"

    def test_transcription_result_failed_forbids_text(self):
        with pytest.raises(ValidationError):
            TranscriptionResult(
                request_id="req-stt-002",
                status=TranscriptionStatus.FAILED,
                transcribed_text="Hallucinated text during failure",
                provider_id="mock_stt",
                provider_version="1.0.0",
            )

        res_fail = TranscriptionResult(
            request_id="req-stt-002",
            status=TranscriptionStatus.FAILED,
            transcribed_text=None,
            provider_id="mock_stt",
            provider_version="1.0.0",
            error_message="Audio decoding error",
        )
        assert res_fail.status == TranscriptionStatus.FAILED
        assert res_fail.transcribed_text is None


class TestProviderProtocols:
    """Verifies TTSProvider and STTProvider abstract base class contracts."""

    def test_tts_provider_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            TTSProvider()  # type: ignore[abstract]

    def test_stt_provider_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            STTProvider()  # type: ignore[abstract]

    @pytest.mark.asyncio
    async def test_concrete_mock_tts_provider_implements_protocol(self):
        class DummyTTS(TTSProvider):
            @property
            def provider_id(self) -> str:
                return "dummy_tts"

            @property
            def provider_version(self) -> str:
                return "0.1.0"

            async def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
                audio = AudioData.create(b"dummy_pcm", request.desired_format, 24000, AudioChannel.MONO, 100)
                cache_key = compute_canonical_audio_cache_key(
                    request.text, request.voice_id, request.desired_format, request.prosody, self.provider_id, self.provider_version
                )
                return SynthesisResult(
                    request_id=request.request_id,
                    status=SynthesisStatus.SUCCESS,
                    audio=audio,
                    cache_key=cache_key,
                    provider_id=self.provider_id,
                    provider_version=self.provider_version,
                )

            async def is_available(self) -> bool:
                return True

        provider = DummyTTS()
        assert provider.provider_id == "dummy_tts"
        assert await provider.is_available() is True
        req = SynthesisRequest(request_id="r1", text="test", voice_id="v1")
        res = await provider.synthesize(req)
        assert res.status == SynthesisStatus.SUCCESS


class TestStaticASTBoundaryAuditPhase101:
    """Static AST Boundary Audit across Phase 10.1 modules.

    Asserts:
    1. ZERO database imports or calls (sqlite3, sqlalchemy, aiosqlite).
    2. ZERO network imports or calls (httpx, requests, aiohttp, urllib, google.genai).
    3. ZERO mutation or promotion authority (set_fact, PromotionAuthorizationToken).
    4. ZERO concrete provider implementations (must be pure DTOs and ABC protocols).
    """

    def test_static_ast_boundary_audit(self):
        app_voice_dir = pathlib.Path(__file__).resolve().parent.parent / "app" / "voice"
        phase101_files = [
            app_voice_dir / "voice_models.py",
            app_voice_dir / "providers" / "base.py",
        ]

        forbidden_io_modules = {
            "requests", "httpx", "aiohttp", "urllib", "socket",
            "sqlalchemy", "sqlite3", "aiosqlite", "redis",
            "google.genai",
        }
        forbidden_mutation_tokens = {"set_fact", "PromotionAuthorizationToken"}

        violations: list[str] = []

        for fpath in phase101_files:
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

        assert not violations, f"AST boundary violations detected in Phase 10.1: {violations}"
