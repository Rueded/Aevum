"""Test suite for Phase 10.5 Desktop Voice Integration & Playback Pipeline.

Governed by ADR-021:
- Provider Abstraction: Swappable adapters with mock providers guaranteeing zero external network / audio engine leakage.
- Decoupled Response Architecture:
  - Lock A: Audio != Canonical Reality (Voice is transient interface; transcript becomes turn; zero canonical reality mutation).
  - Lock B: Decoupled Failure Resilience:
    - TTS failure does NOT crash or roll back conversation (persists text, returns audio_status='failed').
    - STT failure creates strictly 0 fake turns in database.
  - Lock C: Prosody read-only affect mapping (zero emotion mutation).
  - Lock E: Canonical cache identity.
  - Lock F: Ephemeral media lifecycle isolation (cache miss returns 404, never crashes).
  - Rule 18: Unconsented voice input strictly fails closed (403 Forbidden, 0 provider calls, 0 turns).
  - PTT-Only: Continuous VAD deferred; non-PTT input modes fail closed (422).
"""

import ast
import base64
import pathlib
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Message, MessageRole
from app.voice import (
    AudioCache,
    AudioChannel,
    AudioData,
    AudioFormat,
    SynthesisResult,
    SynthesisStatus,
    TranscriptionResult,
    TranscriptionStatus,
    VoiceInputMode,
)
from app.voice.dependencies import (
    get_audio_cache,
    get_stt_provider,
    get_tts_provider,
)
from app.voice.providers.mock_stt import MockSTTProvider
from app.voice.providers.mock_tts import MockTTSProvider
from app.main import app


# Sample valid 16kHz mono audio payload
SAMPLE_PCM = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00sample_valid_speech_audio"
SAMPLE_AUDIO_B64 = base64.b64encode(SAMPLE_PCM).decode("ascii")


class FailingSTTProvider(MockSTTProvider):
    """STT Provider that unconditionally simulates recognition failure."""

    async def transcribe(self, request):
        return TranscriptionResult(
            request_id=request.request_id,
            status=TranscriptionStatus.FAILED,
            transcribed_text=None,
            confidence=None,
            error_message="Simulated speech recognition model failure",
        )


class FailingTTSProvider(MockTTSProvider):
    """TTS Provider that unconditionally simulates synthesis failure."""

    async def synthesize(self, request):
        return SynthesisResult(
            request_id=request.request_id,
            status=SynthesisStatus.FAILED,
            audio=None,
            cache_key=None,
            error_message="Simulated audio synthesis engine failure",
        )


# =============================================================================
# Standalone Voice Endpoints (/voice/stt, /voice/tts, /voice/audio)
# =============================================================================


class TestStandaloneVoiceEndpoints:
    """Verifies standalone audio processing endpoints."""

    @pytest.mark.asyncio
    async def test_voice_stt_success(self, client: AsyncClient):
        """Valid audio payload with Rule 18 consent successfully transcribes."""
        payload = {
            "audio_base64": SAMPLE_AUDIO_B64,
            "format": "WAV",
            "sample_rate_hz": 16000,
            "channels": "MONO",
            "duration_ms": 500,
            "user_consent_granted": True,
            "input_mode": "PTT",
        }
        resp = await client.post("/voice/stt", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["transcribed_text"] is not None
        assert len(data["transcribed_text"]) > 0

    @pytest.mark.asyncio
    async def test_voice_stt_unconsented_fails_closed(self, client: AsyncClient):
        """Unconsented STT request must be rejected with 403 Forbidden (Rule 18)."""
        payload = {
            "audio_base64": SAMPLE_AUDIO_B64,
            "format": "WAV",
            "user_consent_granted": False,
            "input_mode": "PTT",
        }
        resp = await client.post("/voice/stt", json=payload)
        assert resp.status_code == 403
        assert "Rule 18" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_voice_stt_empty_payload_rejected(self, client: AsyncClient):
        """Empty audio payload returns 422 Unprocessable Entity."""
        payload = {
            "audio_base64": "",
            "user_consent_granted": True,
            "input_mode": "PTT",
        }
        resp = await client.post("/voice/stt", json=payload)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_voice_stt_malformed_base64_rejected(self, client: AsyncClient):
        """Malformed base64 audio returns 422."""
        payload = {
            "audio_base64": "not_valid_base64_!@#$%",
            "user_consent_granted": True,
            "input_mode": "PTT",
        }
        resp = await client.post("/voice/stt", json=payload)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_voice_tts_success_and_cache_streaming(self, client: AsyncClient):
        """Synthesizing speech caches binary audio and permits subsequent streaming."""
        tts_payload = {
            "text": "Hello, this is Aevum speaking.",
            "desired_format": "WAV",
            "epistemic_cue": "CERTAIN",
            "character_id": "aevum",
        }
        tts_resp = await client.post("/voice/tts", json=tts_payload)
        assert tts_resp.status_code == 200
        tts_data = tts_resp.json()
        assert tts_data["status"] == "success"
        assert tts_data["audio_base64"] is not None
        assert tts_data["cache_key"] is not None
        cache_key = tts_data["cache_key"]

        # Stream cached audio via GET /voice/audio/{cache_key}
        audio_resp = await client.get(f"/voice/audio/{cache_key}")
        assert audio_resp.status_code == 200
        assert audio_resp.headers["content-type"] == "audio/wav"
        assert len(audio_resp.content) > 0

    @pytest.mark.asyncio
    async def test_voice_tts_empty_text_rejected(self, client: AsyncClient):
        """Empty text payload returns 422."""
        resp = await client.post("/voice/tts", json={"text": "   "})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_voice_audio_cache_miss_returns_404(self, client: AsyncClient):
        """Accessing missing/expired audio key returns 404 Not Found."""
        resp = await client.get("/voice/audio/non_existent_key_12345")
        assert resp.status_code == 404


# =============================================================================
# Conversational Voice Turn Pipeline (/conversations/{id}/voice-messages)
# =============================================================================


class TestConversationVoicePipeline:
    """Verifies end-to-end voice-driven conversational turns and constitutional locks."""

    @pytest.mark.asyncio
    async def test_voice_message_end_to_end_success(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        """Voice turn transcribes input, generates grounded text, and synthesizes audio."""
        # 1. Create conversation
        conv_resp = await client.post("/conversations")
        assert conv_resp.status_code == 201
        conv_id = conv_resp.json()["id"]

        # 2. Configure deterministic speech transcript in mock STT provider
        spoken_text = "Good morning Aevum, how are you today?"
        stt_provider = MockSTTProvider(default_transcript=spoken_text)
        app.dependency_overrides[get_stt_provider] = lambda: stt_provider

        try:
            # 3. Post voice message
            voice_payload = {
                "audio_base64": SAMPLE_AUDIO_B64,
                "format": "WAV",
                "sample_rate_hz": 16000,
                "channels": "MONO",
                "duration_ms": 1200,
                "user_consent_granted": True,
                "input_mode": "PTT",
                "synthesize_reply_audio": True,
            }
            resp = await client.post(f"/conversations/{conv_id}/voice-messages", json=voice_payload)
            assert resp.status_code == 201
            data = resp.json()

            # Verify response schema
            assert data["transcribed_text"] == spoken_text
            assert data["message"]["content"] == spoken_text
            assert data["message"]["role"] == "user"
            assert data["assistant_response"] is not None
            assert data["assistant_status"] == "generated"
            assert data["audio_status"] == "success"
            assert data["audio_data_base64"] is not None
            assert data["audio_cache_key"] is not None

            # Verify database persistence: both turns persisted
            stmt = select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at.asc())
            db_res = await test_session.execute(stmt)
            messages = db_res.scalars().all()
            assert len(messages) == 2
            assert messages[0].role == MessageRole.USER.value
            assert messages[0].content == spoken_text
            assert messages[1].role == MessageRole.ASSISTANT.value

            # Verify audio streaming by cache key
            stream_resp = await client.get(f"/voice/audio/{data['audio_cache_key']}")
            assert stream_resp.status_code == 200
            assert len(stream_resp.content) > 0
        finally:
            app.dependency_overrides.pop(get_stt_provider, None)

    @pytest.mark.asyncio
    async def test_voice_message_unconsented_fails_closed(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        """Rule 18 Consent Gate: unconsented voice submission fails closed with 0 turns in DB."""
        conv_resp = await client.post("/conversations")
        conv_id = conv_resp.json()["id"]

        voice_payload = {
            "audio_base64": SAMPLE_AUDIO_B64,
            "format": "WAV",
            "user_consent_granted": False,  # Violates Rule 18
            "input_mode": "PTT",
        }
        resp = await client.post(f"/conversations/{conv_id}/voice-messages", json=voice_payload)
        assert resp.status_code == 403
        assert "Rule 18" in resp.json()["detail"]

        # Lock B & Rule 18: Zero messages persisted in DB
        stmt = select(Message).where(Message.conversation_id == conv_id)
        db_res = await test_session.execute(stmt)
        messages = db_res.scalars().all()
        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_voice_message_non_ptt_input_rejected(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        """Continuous VAD is strictly deferred (ADR-021 Decision 3); non-PTT input rejected."""
        conv_resp = await client.post("/conversations")
        conv_id = conv_resp.json()["id"]

        voice_payload = {
            "audio_base64": SAMPLE_AUDIO_B64,
            "format": "WAV",
            "user_consent_granted": True,
            "input_mode": "CONTINUOUS_VAD",  # Not allowed in Phase 10
        }
        resp = await client.post(f"/conversations/{conv_id}/voice-messages", json=voice_payload)
        assert resp.status_code == 422
        assert "Only PTT input mode" in resp.json()["detail"]

        # Zero messages persisted in DB
        stmt = select(Message).where(Message.conversation_id == conv_id)
        db_res = await test_session.execute(stmt)
        messages = db_res.scalars().all()
        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_voice_message_stt_failure_isolation(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        """Lock B: When STT fails, returns 422 and strictly 0 turns are created in DB."""
        conv_resp = await client.post("/conversations")
        conv_id = conv_resp.json()["id"]

        # Override STT provider with unconditionally failing provider
        app.dependency_overrides[get_stt_provider] = lambda: FailingSTTProvider()

        try:
            voice_payload = {
                "audio_base64": SAMPLE_AUDIO_B64,
                "format": "WAV",
                "user_consent_granted": True,
                "input_mode": "PTT",
            }
            resp = await client.post(f"/conversations/{conv_id}/voice-messages", json=voice_payload)
            assert resp.status_code == 422
            assert "Speech transcription failed" in resp.json()["detail"]

            # Lock B: STT failure guarantees 0 fake turns
            stmt = select(Message).where(Message.conversation_id == conv_id)
            db_res = await test_session.execute(stmt)
            messages = db_res.scalars().all()
            assert len(messages) == 0
        finally:
            app.dependency_overrides.pop(get_stt_provider, None)

    @pytest.mark.asyncio
    async def test_voice_message_tts_failure_decoupled_resilience(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        """Lock B: TTS synthesis failure does NOT fail conversational turn (persists text, audio_status='failed')."""
        conv_resp = await client.post("/conversations")
        conv_id = conv_resp.json()["id"]

        # Override TTS provider with failing provider and fresh empty cache to avoid cache hit
        fresh_cache = AudioCache()
        app.dependency_overrides[get_tts_provider] = lambda: FailingTTSProvider()
        app.dependency_overrides[get_audio_cache] = lambda: fresh_cache

        try:
            voice_payload = {
                "audio_base64": SAMPLE_AUDIO_B64,
                "format": "WAV",
                "user_consent_granted": True,
                "input_mode": "PTT",
                "synthesize_reply_audio": True,
            }
            resp = await client.post(f"/conversations/{conv_id}/voice-messages", json=voice_payload)
            # Must succeed with 201 Created despite audio engine failure!
            assert resp.status_code == 201
            data = resp.json()

            # Assistant response generated and committed
            assert data["assistant_response"] is not None
            assert data["assistant_status"] == "generated"

            # Audio gracefully marked as failed without crashing
            assert data["audio_status"] == "failed"
            assert data["audio_data_base64"] is None
            assert data["audio_cache_key"] is None

            # Verify database integrity: both messages exist and are intact
            stmt = select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at.asc())
            db_res = await test_session.execute(stmt)
            messages = db_res.scalars().all()
            assert len(messages) == 2
            assert messages[0].role == MessageRole.USER.value
            assert messages[1].role == MessageRole.ASSISTANT.value
        finally:
            app.dependency_overrides.pop(get_tts_provider, None)
            app.dependency_overrides.pop(get_audio_cache, None)

    @pytest.mark.asyncio
    async def test_voice_message_synthesize_false_skips_audio(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        """synthesize_reply_audio=False skips TTS synthesis entirely (audio_status='skipped')."""
        conv_resp = await client.post("/conversations")
        conv_id = conv_resp.json()["id"]

        voice_payload = {
            "audio_base64": SAMPLE_AUDIO_B64,
            "format": "WAV",
            "user_consent_granted": True,
            "input_mode": "PTT",
            "synthesize_reply_audio": False,
        }
        resp = await client.post(f"/conversations/{conv_id}/voice-messages", json=voice_payload)
        assert resp.status_code == 201
        data = resp.json()

        assert data["assistant_response"] is not None
        assert data["audio_status"] == "skipped"
        assert data["audio_data_base64"] is None
        assert data["audio_cache_key"] is None

    @pytest.mark.asyncio
    async def test_voice_message_nonexistent_conversation_returns_404(
        self,
        client: AsyncClient,
    ):
        """Voice message to unknown conversation ID returns 404 Not Found."""
        voice_payload = {
            "audio_base64": SAMPLE_AUDIO_B64,
            "format": "WAV",
            "user_consent_granted": True,
            "input_mode": "PTT",
        }
        resp = await client.post("/conversations/non_existent_conv_9999/voice-messages", json=voice_payload)
        assert resp.status_code == 404


# =============================================================================
# Static AST Boundary Audit (Phase 10.5)
# =============================================================================


class TestPhase105ASTBoundaries:
    """Verifies that Phase 10.5 endpoints adhere to all constitutional boundaries."""

    def test_voice_api_boundary_compliance(self):
        """Ensure backend/app/api/voice.py does not violate reality or consent boundaries."""
        target_path = pathlib.Path(__file__).parent.parent / "app" / "api" / "voice.py"
        assert target_path.exists(), "voice.py router must exist"

        tree = ast.parse(target_path.read_text(encoding="utf-8"))

        forbidden_names = {
            "set_fact",
            "PromotionAuthorizationToken",
            "BiographyPromotionService",
            "RealityRepairService",
            "continuous_vad",
            "listen_continuously",
            "whisper",
            "edge_tts",
            "azure",
        }

        found_forbidden = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden_names:
                found_forbidden.append(node.id)
            elif isinstance(node, ast.Attribute) and node.attr in forbidden_names:
                found_forbidden.append(node.attr)

        assert not found_forbidden, f"Forbidden tokens found in voice.py: {found_forbidden}"

    def test_conversations_api_voice_boundary_compliance(self):
        """Ensure backend/app/api/conversations.py maintains strict voice decoupling."""
        target_path = pathlib.Path(__file__).parent.parent / "app" / "api" / "conversations.py"
        assert target_path.exists(), "conversations.py must exist"

        tree = ast.parse(target_path.read_text(encoding="utf-8"))

        forbidden_names = {
            "set_fact",
            "PromotionAuthorizationToken",
            "continuous_vad",
            "listen_continuously",
        }

        found_forbidden = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden_names:
                found_forbidden.append(node.id)
            elif isinstance(node, ast.Attribute) and node.attr in forbidden_names:
                found_forbidden.append(node.attr)

        assert not found_forbidden, f"Forbidden tokens found in conversations.py: {found_forbidden}"
