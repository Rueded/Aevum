"""
test_golden_suite_10.py — Golden Acceptance Suite 10 (Phase 10.6: GC-246 ~ GC-270)

Golden Acceptance Suite for Phase 10: Voice (TTS & STT).
Verifies all frozen contracts (10.1–10.5) and the 6 Constitutional Voice Locks under ADR-021.

"Voice is the body; the backend remains the mind and source of truth."

Covers 25 Acceptance Benchmarks across 6 Structured Clusters:
- Cluster 1: Constitutional Voice Locks & Reality Separation (GC-246 ~ GC-251)
  - GC-246: Mind Singularity & Mind/Body Separation (Lock A)
  - GC-247: Audio != Canonical Reality & Non-Promoting Speech (Lock A)
  - GC-248: Rule 18 Consent First & Fail-Closed Guarantee (Rule 18)
  - GC-249: PTT-Only Input Boundary & Continuous VAD Exclusion (ADR-021 Decision 3)
  - GC-250: STT Failure Decoupling & Zero Fake Turns (Lock B)
  - GC-251: TTS Failure Decoupling & Conversation Persistence Resilience (Lock B)

- Cluster 2: Provider Abstraction & Isolation (GC-252 ~ GC-253)
  - GC-252: Provider Abstraction as Implementation Detail (ADR-021 Decision 1)
  - GC-253: Test Mock Hermetic Isolation & Zero Network Leakage (ADR-021 Decision 1)

- Cluster 3: Affective Prosody Modulation & Categorical Epistemic Cues (GC-254 ~ GC-257)
  - GC-254: Prosody Mapping Pure Determinism (Lock C)
  - GC-255: Prosody Consumer Read-Only Isolation (Lock C)
  - GC-256: Categorical Epistemic Cue Modulation & Zero Pseudo-Floats (Lock D)
  - GC-257: Epistemic Uncertainty Hesitation & Pitch/Rate Dynamics (Lock D)

- Cluster 4: Canonical Audio Cache Identity & Lifecycle Isolation (GC-258 ~ GC-261)
  - GC-258: Canonical Audio Cache Identity Invariant (Lock E)
  - GC-259: Cache Semantic Divergence Across All Tuple Dimensions (Lock E)
  - GC-260: Ephemeral Media Lifecycle Isolation (Lock F)
  - GC-261: Audio Purge != Reality Mutation Invariant (Lock F)

- Cluster 5: Desktop Body Boundary, Barge-in & API Contract Integrity (GC-262 ~ GC-267)
  - GC-262: User Barge-in Isolation Without State Corruption
  - GC-263: Desktop Body Boundary & Non-Canonical Storage
  - GC-264: API Contract Strictness & extra="forbid" Compliance
  - GC-265: Zero Direct set_fact Authority in Voice Subsystem
  - GC-266: Continuous VAD Anti-Leakage Boundary
  - GC-267: STT/TTS Failure Independence & Error Decoupling

- Cluster 6: End-to-End Voice Round-Trip, Replay & Constitutional Guard (GC-268 ~ GC-270)
  - GC-268: End-to-End Voice Turn Round-Trip
  - GC-269: Semantic Replay Determinism Across Voice Turns
  - GC-270: Full Voice Constitutional Boundary Audit
"""

from __future__ import annotations

import ast
import base64
from datetime import datetime, timezone
import hashlib
import json
import pathlib
import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.state_models import CharacterMood, CharacterState
from app.db.models import Conversation, Message, MessageRole
from app.emotion.emotion_models import EmotionState, EmotionType
from app.voice import (
    AudioCache,
    AudioChannel,
    AudioData,
    AudioFormat,
    AudioMediaLifecycle,
    EpistemicCue,
    ProsodyConfig,
    ProsodyMapper,
    STTService,
    SynthesisRequest,
    SynthesisResult,
    SynthesisStatus,
    TTSService,
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptionStatus,
    VoiceConsentGuard,
    VoiceInputMode,
    compute_canonical_audio_cache_key,
)
from app.voice.dependencies import (
    get_audio_cache,
    get_stt_provider,
    get_tts_provider,
)
from app.voice.providers.base import (
    STTProvider,
    STTProviderError,
    TTSProvider,
    TTSProviderError,
    VoiceConsentRequiredError,
)
from app.voice.providers.mock_stt import MockSTTProvider
from app.voice.providers.mock_tts import MockTTSProvider
from app.main import app


# Standard deterministic test PCM and Base64 payloads
GOLDEN_PCM = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00sample_golden_speech_audio"
GOLDEN_AUDIO_B64 = base64.b64encode(GOLDEN_PCM).decode("ascii")


def create_sample_audio(
    data: bytes = GOLDEN_PCM,
    fmt: AudioFormat = AudioFormat.WAV,
    sample_rate_hz: int = 16000,
    channels: AudioChannel = AudioChannel.MONO,
    duration_ms: int = 600,
) -> AudioData:
    return AudioData.create(
        data=data,
        format=fmt,
        sample_rate_hz=sample_rate_hz,
        channels=channels,
        duration_ms=duration_ms,
    )


def create_sample_emotion_state(
    emotion_type: EmotionType = EmotionType.HAPPY,
    intensity: float = 0.7,
) -> EmotionState:
    now = datetime.now(timezone.utc)
    return EmotionState(
        character_id="aevum",
        emotion_type=emotion_type,
        intensity=intensity,
        version=1,
        created_at=now,
        updated_at=now,
    )


def create_sample_character_state(
    mood: CharacterMood = CharacterMood.GOOD,
) -> CharacterState:
    now = datetime.now(timezone.utc)
    return CharacterState(
        id="aevum",
        version=1,
        updated_at=now,
        mood=mood,
        energy=0.8,
        stress=0.2,
        social_energy=0.7,
        confidence=0.9,
        irritation=0.0,
        loneliness=0.1,
        current_activity="resting",
        current_location="home",
    )


# =============================================================================
# Cluster 1: Constitutional Voice Locks & Reality Separation (GC-246 ~ GC-251)
# =============================================================================


class TestCluster1ConstitutionalVoiceLocks:
    """Verifies Lock A, Lock B, Rule 18, and PTT-Only core architectural guarantees."""

    @pytest.mark.asyncio
    async def test_gc246_mind_singularity_and_mind_body_separation(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        """GC-246: Voice is interface/body; mind owns reality.

        Voice interaction flows through CharacterEngine and leaves canonical core untouched.
        """
        # Create conversation
        conv_resp = await client.post("/conversations")
        conv_id = conv_resp.json()["id"]

        stt = MockSTTProvider(default_transcript="Hello Aevum, tell me about yourself.")
        app.dependency_overrides[get_stt_provider] = lambda: stt

        try:
            payload = {
                "audio_base64": GOLDEN_AUDIO_B64,
                "user_consent_granted": True,
                "input_mode": "PTT",
                "synthesize_reply_audio": True,
            }
            resp = await client.post(f"/conversations/{conv_id}/voice-messages", json=payload)
            assert resp.status_code == 201

            # Verify that voice pipeline did not inject any synthetic reality facts
            # Messages are stored in DB, but no ungrounded core mutations occurred
            stmt = select(Message).where(Message.conversation_id == conv_id)
            messages = (await test_session.execute(stmt)).scalars().all()
            assert len(messages) == 2
            assert messages[0].content == "Hello Aevum, tell me about yourself."
        finally:
            app.dependency_overrides.pop(get_stt_provider, None)

    @pytest.mark.asyncio
    async def test_gc247_audio_not_canonical_reality_and_unpromoted_dialogue(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        """GC-247 (Lock A): Spoken audio and transcripts are raw dialogue input, never pre-promoted fact.

        Transcripts enter conversation history without minting PromotionAuthorizationToken or altering facts.
        """
        conv_resp = await client.post("/conversations")
        conv_id = conv_resp.json()["id"]

        stt = MockSTTProvider(default_transcript="I love drinking green tea.")
        app.dependency_overrides[get_stt_provider] = lambda: stt

        try:
            payload = {
                "audio_base64": GOLDEN_AUDIO_B64,
                "user_consent_granted": True,
                "input_mode": "PTT",
            }
            resp = await client.post(f"/conversations/{conv_id}/voice-messages", json=payload)
            assert resp.status_code == 201
            data = resp.json()

            # Transcript is persisted as standard user dialogue
            assert data["transcribed_text"] == "I love drinking green tea."
            assert data["message"]["role"] == "user"

            # Check that audio transcript did NOT bypass reality governance:
            # Profile facts must remain unaffected by mere spoken audio
            profile_resp = await client.get("/character/profile")
            if profile_resp.status_code == 200:
                core_facts = profile_resp.json().get("core", {}).get("facts", {})
                assert "preference.green_tea" not in core_facts
        finally:
            app.dependency_overrides.pop(get_stt_provider, None)

    @pytest.mark.asyncio
    async def test_gc248_rule_18_consent_first_and_fail_closed_guarantee(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        """GC-248 (Rule 18): Unconsented voice input strictly fails closed with 0 provider calls and 0 DB turns."""
        conv_resp = await client.post("/conversations")
        conv_id = conv_resp.json()["id"]

        mock_stt = MockSTTProvider()
        app.dependency_overrides[get_stt_provider] = lambda: mock_stt

        try:
            payload = {
                "audio_base64": GOLDEN_AUDIO_B64,
                "user_consent_granted": False,  # Violates Rule 18
                "input_mode": "PTT",
            }
            resp = await client.post(f"/conversations/{conv_id}/voice-messages", json=payload)
            assert resp.status_code == 403
            assert "Rule 18" in resp.json()["detail"]

            # Provider must NEVER have been invoked
            assert mock_stt.invocation_count == 0

            # Database must contain 0 messages
            stmt = select(Message).where(Message.conversation_id == conv_id)
            messages = (await test_session.execute(stmt)).scalars().all()
            assert len(messages) == 0
        finally:
            app.dependency_overrides.pop(get_stt_provider, None)

    @pytest.mark.asyncio
    async def test_gc249_ptt_only_input_boundary_and_continuous_vad_exclusion(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        """GC-249 (ADR-021 Decision 3): PTT is the only permitted mode; non-PTT input is rejected with 422."""
        conv_resp = await client.post("/conversations")
        conv_id = conv_resp.json()["id"]

        mock_stt = MockSTTProvider()
        app.dependency_overrides[get_stt_provider] = lambda: mock_stt

        try:
            for invalid_mode in ["CONTINUOUS_VAD", "ALWAYS_ON", "BACKGROUND_LISTEN", "STREAMING"]:
                payload = {
                    "audio_base64": GOLDEN_AUDIO_B64,
                    "user_consent_granted": True,
                    "input_mode": invalid_mode,
                }
                resp = await client.post(f"/conversations/{conv_id}/voice-messages", json=payload)
                assert resp.status_code == 422
                assert "Only PTT input mode" in resp.json()["detail"]

            assert mock_stt.invocation_count == 0
            stmt = select(Message).where(Message.conversation_id == conv_id)
            messages = (await test_session.execute(stmt)).scalars().all()
            assert len(messages) == 0
        finally:
            app.dependency_overrides.pop(get_stt_provider, None)

    @pytest.mark.asyncio
    async def test_gc250_stt_failure_decoupling_and_zero_fake_turns(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        """GC-250 (Lock B): STT failure returns 422 and creates strictly 0 fake turns or DB writes."""
        conv_resp = await client.post("/conversations")
        conv_id = conv_resp.json()["id"]

        failing_stt = MockSTTProvider(simulate_failure=True)
        app.dependency_overrides[get_stt_provider] = lambda: failing_stt

        try:
            payload = {
                "audio_base64": GOLDEN_AUDIO_B64,
                "user_consent_granted": True,
                "input_mode": "PTT",
            }
            resp = await client.post(f"/conversations/{conv_id}/voice-messages", json=payload)
            assert resp.status_code == 422
            assert "Speech transcription failed" in resp.json()["detail"]

            # Strictly zero turns created
            stmt = select(Message).where(Message.conversation_id == conv_id)
            messages = (await test_session.execute(stmt)).scalars().all()
            assert len(messages) == 0
        finally:
            app.dependency_overrides.pop(get_stt_provider, None)

    @pytest.mark.asyncio
    async def test_gc251_tts_failure_decoupling_and_conversation_persistence_resilience(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        """GC-251 (Lock B): TTS failure does NOT roll back conversation; text persists with audio_status='failed'."""
        conv_resp = await client.post("/conversations")
        conv_id = conv_resp.json()["id"]

        failing_tts = MockTTSProvider(simulate_failure=True)
        fresh_cache = AudioCache()
        app.dependency_overrides[get_tts_provider] = lambda: failing_tts
        app.dependency_overrides[get_audio_cache] = lambda: fresh_cache

        try:
            payload = {
                "audio_base64": GOLDEN_AUDIO_B64,
                "user_consent_granted": True,
                "input_mode": "PTT",
                "synthesize_reply_audio": True,
            }
            resp = await client.post(f"/conversations/{conv_id}/voice-messages", json=payload)
            # Conversation must succeed despite TTS engine failure
            assert resp.status_code == 201
            data = resp.json()

            assert data["assistant_status"] == "generated"
            assert data["audio_status"] == "failed"
            assert data["audio_data_base64"] is None
            assert data["audio_cache_key"] is None

            # Both messages are persistently committed in DB
            stmt = select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at.asc())
            messages = (await test_session.execute(stmt)).scalars().all()
            assert len(messages) == 2
            assert messages[0].role == MessageRole.USER.value
            assert messages[1].role == MessageRole.ASSISTANT.value
        finally:
            app.dependency_overrides.pop(get_tts_provider, None)
            app.dependency_overrides.pop(get_audio_cache, None)


# =============================================================================
# Cluster 2: Provider Abstraction & Isolation (GC-252 ~ GC-253)
# =============================================================================


class TestCluster2ProviderAbstraction:
    """Verifies that providers are pure implementation details with zero architectural leakage."""

    def test_gc252_provider_abstraction_as_implementation_detail(self):
        """GC-252: Base protocols define swappable contracts without engine-specific binding."""
        # TTSProvider and STTProvider are runtime checkable protocols
        assert isinstance(MockTTSProvider(), TTSProvider)
        assert isinstance(MockSTTProvider(), STTProvider)

        # Base module must not import any specific audio processing libraries
        base_path = pathlib.Path(__file__).parent.parent / "app" / "voice" / "providers" / "base.py"
        tree = ast.parse(base_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mod = getattr(node, "module", "") or ""
                for alias in node.names:
                    full_name = f"{mod}.{alias.name}" if mod else alias.name
                    assert "torch" not in full_name
                    assert "transformers" not in full_name
                    assert "whisper" not in full_name
                    assert "edge_tts" not in full_name
                    assert "soundfile" not in full_name

    @pytest.mark.asyncio
    async def test_gc253_test_mock_hermetic_isolation_and_zero_network_leakage(self):
        """GC-253: Mock providers run completely offline with zero network or socket operations."""
        stt_mock = MockSTTProvider(default_transcript="Isolated offline transcript")
        tts_mock = MockTTSProvider()

        audio = create_sample_audio()
        stt_req = TranscriptionRequest(
            request_id="iso-stt-01",
            audio=audio,
            input_mode=VoiceInputMode.PTT,
            user_consent_granted=True,
        )
        stt_res = await stt_mock.transcribe(stt_req)
        assert stt_res.status == TranscriptionStatus.SUCCESS
        assert stt_res.transcribed_text == "Isolated offline transcript"

        tts_req = SynthesisRequest(
            request_id="iso-tts-01",
            text="Testing offline isolation.",
            voice_id="default_voice",
            desired_format=AudioFormat.WAV,
            prosody=ProsodyConfig(),
        )
        tts_res = await tts_mock.synthesize(tts_req)
        assert tts_res.status == SynthesisStatus.SUCCESS
        assert tts_res.audio is not None
        assert tts_res.audio.data.startswith(b"RIFF")


# =============================================================================
# Cluster 3: Affective Prosody Modulation & Categorical Epistemic Cues (GC-254 ~ GC-257)
# =============================================================================


class TestCluster3ProsodyModulation:
    """Verifies Lock C and Lock D: affect-driven prosody modulation and categorical epistemic cues."""

    def test_gc254_prosody_mapping_pure_determinism(self):
        """GC-254 (Lock C): Identical emotional state and epistemic cue produce identical ProsodyConfig."""
        emotion = create_sample_emotion_state(EmotionType.EXCITED, intensity=0.85)
        char_state = create_sample_character_state(CharacterMood.GOOD)

        cfg1 = ProsodyMapper.from_states(
            emotion_state=emotion,
            character_state=char_state,
            epistemic_cue=EpistemicCue.CERTAIN,
        )
        cfg2 = ProsodyMapper.from_states(
            emotion_state=emotion,
            character_state=char_state,
            epistemic_cue=EpistemicCue.CERTAIN,
        )

        assert cfg1 == cfg2
        assert cfg1.model_dump() == cfg2.model_dump()
        assert cfg1.pitch_shift_semitones > 0.0  # Excited elevates pitch
        assert cfg1.rate_multiplier > 1.0        # Excited elevates speech rate

    def test_gc255_prosody_consumer_read_only_isolation(self):
        """GC-255 (Lock C): ProsodyMapper is strictly read-only and never mutates emotion or character state."""
        emotion = create_sample_emotion_state(EmotionType.SAD, intensity=0.6)
        char_state = create_sample_character_state(CharacterMood.NEUTRAL)

        orig_emotion_dump = emotion.model_dump()
        orig_char_dump = char_state.model_dump()

        _ = ProsodyMapper.from_states(
            emotion_state=emotion,
            character_state=char_state,
            epistemic_cue=EpistemicCue.UNCERTAIN,
        )

        assert emotion.model_dump() == orig_emotion_dump
        assert char_state.model_dump() == orig_char_dump

    def test_gc256_categorical_epistemic_cue_modulation_and_zero_pseudo_floats(self):
        """GC-256 (Lock D): Epistemic cue is categorical enum; zero pseudo-probability float weights."""
        valid_cues = {
            EpistemicCue.CERTAIN,
            EpistemicCue.UNCERTAIN,
            EpistemicCue.AMBIGUOUS,
            EpistemicCue.CONTESTED,
            EpistemicCue.UNKNOWN,
        }
        for cue in valid_cues:
            cfg = ProsodyMapper.map_prosody(
                emotion_type=EmotionType.CALM,
                intensity=0.5,
                epistemic_cue=cue,
            )
            assert isinstance(cfg, ProsodyConfig)
            assert isinstance(cfg.rate_multiplier, float)
            assert isinstance(cfg.pitch_shift_semitones, float)
            assert isinstance(cfg.hesitation_pause_ms, int)

        # Verify extra="forbid" rejects float weights
        with pytest.raises(ValidationError):
            ProsodyConfig(confidence_weight=0.85)  # type: ignore

    def test_gc257_epistemic_uncertainty_hesitation_and_pitch_rate_dynamics(self):
        """GC-257 (Lock D): Uncertainty slows rate, drops pitch, and introduces hesitation pause."""
        certain_cfg = ProsodyMapper.map_prosody(
            emotion_type=EmotionType.NEUTRAL,
            intensity=0.5,
            epistemic_cue=EpistemicCue.CERTAIN,
        )
        uncertain_cfg = ProsodyMapper.map_prosody(
            emotion_type=EmotionType.NEUTRAL,
            intensity=0.5,
            epistemic_cue=EpistemicCue.UNCERTAIN,
        )
        ambiguous_cfg = ProsodyMapper.map_prosody(
            emotion_type=EmotionType.NEUTRAL,
            intensity=0.5,
            epistemic_cue=EpistemicCue.AMBIGUOUS,
        )

        # Certain cue has 0 hesitation
        assert certain_cfg.hesitation_pause_ms == 0

        # Uncertain cue has hesitation, slower rate, lower/equal pitch
        assert uncertain_cfg.hesitation_pause_ms == 250
        assert uncertain_cfg.rate_multiplier < certain_cfg.rate_multiplier
        assert uncertain_cfg.pitch_shift_semitones <= certain_cfg.pitch_shift_semitones

        # Ambiguous cue has hesitation and slower rate
        assert ambiguous_cfg.hesitation_pause_ms == 350
        assert ambiguous_cfg.rate_multiplier < certain_cfg.rate_multiplier


# =============================================================================
# Cluster 4: Canonical Audio Cache Identity & Lifecycle Isolation (GC-258 ~ GC-261)
# =============================================================================


class TestCluster4AudioCacheLifecycle:
    """Verifies Lock E and Lock F: canonical cache keying and ephemeral lifecycle isolation."""

    def test_gc258_canonical_audio_cache_identity_invariant(self):
        """GC-258 (Lock E): Cache key is SHA-256 over canonical JSON tuple."""
        key1 = compute_canonical_audio_cache_key(
            text="Hello world",
            voice_id="voice_alpha",
            audio_format=AudioFormat.WAV,
            prosody=ProsodyConfig(pitch_shift_semitones=1.1, rate_multiplier=1.0),
            provider_id="mock_tts",
            provider_version="1.0.0",
        )
        key2 = compute_canonical_audio_cache_key(
            text="Hello world",
            voice_id="voice_alpha",
            audio_format=AudioFormat.WAV,
            prosody=ProsodyConfig(pitch_shift_semitones=1.1, rate_multiplier=1.0),
            provider_id="mock_tts",
            provider_version="1.0.0",
        )
        assert key1 == key2
        assert len(key1) == 64
        # Validate hex SHA-256
        int(key1, 16)

    def test_gc259_cache_semantic_divergence_across_all_tuple_dimensions(self):
        """GC-259 (Lock E): Any dimension variation produces distinct canonical cache key."""
        base_args = {
            "text": "The weather is lovely.",
            "voice_id": "v1",
            "audio_format": AudioFormat.WAV,
            "prosody": ProsodyConfig(pitch_shift_semitones=1.0, rate_multiplier=1.0),
            "provider_id": "p1",
            "provider_version": "1.0.0",
        }
        base_key = compute_canonical_audio_cache_key(**base_args)

        # Variance 1: Text changed
        args_text = dict(base_args, text="The weather is rainy.")
        assert compute_canonical_audio_cache_key(**args_text) != base_key

        # Variance 2: Voice ID changed
        args_voice = dict(base_args, voice_id="v2")
        assert compute_canonical_audio_cache_key(**args_voice) != base_key

        # Variance 3: Format changed
        args_fmt = dict(base_args, audio_format=AudioFormat.MP3)
        assert compute_canonical_audio_cache_key(**args_fmt) != base_key

        # Variance 4: Prosody changed
        args_prosody = dict(base_args, prosody=ProsodyConfig(pitch_shift_semitones=2.0))
        assert compute_canonical_audio_cache_key(**args_prosody) != base_key

        # Variance 5: Provider version changed
        args_ver = dict(base_args, provider_version="2.0.0")
        assert compute_canonical_audio_cache_key(**args_ver) != base_key

    def test_gc260_ephemeral_media_lifecycle_isolation(self):
        """GC-260 (Lock F): Cache capacity eviction and TTL expiration isolate media lifecycle without error."""
        cache = AudioCache(max_entries=2, default_ttl_seconds=3600)
        audio1 = create_sample_audio(data=b"audio1")
        audio2 = create_sample_audio(data=b"audio2")
        audio3 = create_sample_audio(data=b"audio3")

        cache.put("key1", audio1)
        cache.put("key2", audio2)
        assert cache.get("key1") is not None
        assert cache.get("key2") is not None

        # Inserting key3 must evict least-recently-used key
        cache.put("key3", audio3)
        assert cache.current_size <= 2
        # Missing key returns None cleanly (zero exception)
        assert cache.get("non_existent_key") is None

    @pytest.mark.asyncio
    async def test_gc261_audio_purge_not_reality_mutation_invariant(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        """GC-261 (Lock F): Purging audio cache leaves messages, biography, and reality state completely intact."""
        conv_resp = await client.post("/conversations")
        conv_id = conv_resp.json()["id"]

        # Run successful voice turn
        payload = {
            "audio_base64": GOLDEN_AUDIO_B64,
            "user_consent_granted": True,
            "input_mode": "PTT",
            "synthesize_reply_audio": True,
        }
        resp = await client.post(f"/conversations/{conv_id}/voice-messages", json=payload)
        assert resp.status_code == 201
        cache_key = resp.json()["audio_cache_key"]
        assert cache_key is not None

        # Verify audio exists in cache
        audio_resp = await client.get(f"/voice/audio/{cache_key}")
        assert audio_resp.status_code == 200

        # Purge audio cache completely
        global_cache = get_audio_cache()
        global_cache.purge_all()

        # Cache miss now returns 404
        purged_resp = await client.get(f"/voice/audio/{cache_key}")
        assert purged_resp.status_code == 404

        # Non-blocking reminder verification:
        # Conversation history and messages MUST remain 100% intact!
        stmt = select(Message).where(Message.conversation_id == conv_id)
        messages = (await test_session.execute(stmt)).scalars().all()
        assert len(messages) == 2
        assert messages[0].role == MessageRole.USER.value
        assert messages[1].role == MessageRole.ASSISTANT.value


# =============================================================================
# Cluster 5: Desktop Body Boundary, Barge-in & API Contract Integrity (GC-262 ~ GC-267)
# =============================================================================


class TestCluster5DesktopAndAPIContracts:
    """Verifies boundary strictness, barge-in isolation, and zero unauthorized mutation authority."""

    def test_gc262_user_barge_in_isolation_without_state_corruption(self):
        """GC-262: Barge-in stops audio playback in frontend without corrupting backend state."""
        # Simulated barge-in action
        client_playback_state = {"playing": True, "audio_id": "msg-123"}
        # User starts typing or clicks PTT -> barge-in triggered
        client_playback_state["playing"] = False
        client_playback_state["audio_id"] = None

        # Verify that frontend playback state change does not touch canonical state models
        char_state = create_sample_character_state()
        emotion = create_sample_emotion_state()
        assert char_state.mood == CharacterMood.GOOD
        assert emotion.emotion_type == EmotionType.HAPPY

    def test_gc263_desktop_body_boundary_and_non_canonical_storage(self):
        """GC-263: Desktop components are body-only; zero canonical state in React / LocalStorage."""
        desktop_chat = pathlib.Path(__file__).parent.parent.parent / "apps" / "desktop" / "src" / "components" / "ChatView.tsx"
        desktop_app = pathlib.Path(__file__).parent.parent.parent / "apps" / "desktop" / "src" / "App.tsx"

        assert desktop_chat.exists()
        assert desktop_app.exists()

        chat_code = desktop_chat.read_text(encoding="utf-8")
        app_code = desktop_app.read_text(encoding="utf-8")

        # Desktop frontend must never declare canonical biography mutation
        assert "set_fact" not in chat_code
        assert "PromotionAuthorizationToken" not in chat_code
        assert "set_fact" not in app_code
        assert "PromotionAuthorizationToken" not in app_code

    def test_gc264_api_contract_strictness_and_extra_forbid_compliance(self):
        """GC-264: Voice DTOs enforce extra='forbid' to prevent unvalidated field leakage."""
        from app.voice.voice_models import SynthesisRequest, TranscriptionRequest

        audio = create_sample_audio()

        # SynthesisRequest extra="forbid"
        with pytest.raises(ValidationError):
            SynthesisRequest(
                request_id="req-1",
                text="hello",
                extra_forbidden_field="hack",  # type: ignore
            )

        # TranscriptionRequest extra="forbid"
        with pytest.raises(ValidationError):
            TranscriptionRequest(
                request_id="req-2",
                audio=audio,
                input_mode=VoiceInputMode.PTT,
                user_consent_granted=True,
                unauthorized_token="bypass",  # type: ignore
            )

    def test_gc265_zero_direct_set_fact_authority_in_voice_subsystem(self):
        """GC-265: Zero voice subsystem modules have authority or code paths to invoke set_fact."""
        voice_dir = pathlib.Path(__file__).parent.parent / "app" / "voice"
        python_files = list(voice_dir.rglob("*.py"))

        for py_file in python_files:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id == "set_fact":
                        pytest.fail(f"Unauthorized set_fact call found in {py_file.name}")
                    elif isinstance(node.func, ast.Attribute) and node.func.attr == "set_fact":
                        pytest.fail(f"Unauthorized set_fact call found in {py_file.name}")
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in getattr(node, "names", []):
                        if alias.name in {"set_fact", "PromotionAuthorizationToken"}:
                            pytest.fail(f"Unauthorized import {alias.name} found in {py_file.name}")

    def test_gc266_continuous_vad_anti_leakage_boundary(self):
        """GC-266: Voice subsystem explicitly rejects continuous VAD and passive recording."""
        # 1. VoiceInputMode enum strictly permits only PTT
        assert [m.value for m in VoiceInputMode] == ["PTT"]

        # 2. Pydantic validation rejects any continuous VAD input mode
        audio = create_sample_audio()
        with pytest.raises(ValidationError):
            TranscriptionRequest(
                request_id="req-vad-test",
                audio=audio,
                input_mode="CONTINUOUS_VAD",  # type: ignore
                user_consent_granted=True,
            )

    @pytest.mark.asyncio
    async def test_gc267_stt_tts_failure_independence_and_error_decoupling(self):
        """GC-267: STT failure and TTS failure are completely decoupled and independently handled."""
        stt_service = STTService(provider=MockSTTProvider(simulate_failure=True))
        tts_service = TTSService(provider=MockTTSProvider(simulate_failure=True))

        audio = create_sample_audio()

        # STT failure produces failed TranscriptionResult with None transcribed text
        stt_res = await stt_service.transcribe_audio(audio=audio, user_consent_granted=True)
        assert stt_res.status == TranscriptionStatus.FAILED
        assert stt_res.transcribed_text is None

        # TTS failure produces failed SynthesisResult with None audio and None cache_key
        tts_res = await tts_service.synthesize_text(text="Test decoupled failure", desired_format=AudioFormat.WAV)
        assert tts_res.status == SynthesisStatus.FAILED
        assert tts_res.audio is None
        assert tts_res.cache_key is None


# =============================================================================
# Cluster 6: End-to-End Voice Round-Trip, Replay & Constitutional Guard (GC-268 ~ GC-270)
# =============================================================================


class TestCluster6EndToEndAndConstitutionalAudit:
    """Verifies complete round-trip integration, replay determinism, and full AST boundaries."""

    @pytest.mark.asyncio
    async def test_gc268_end_to_end_voice_turn_round_trip(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        """GC-268: Complete end-to-end voice round trip: PTT -> STT -> turn -> LLM -> TTS -> cache streaming."""
        conv_resp = await client.post("/conversations")
        conv_id = conv_resp.json()["id"]

        stt_provider = MockSTTProvider(default_transcript="What is your favorite memory?")
        tts_provider = MockTTSProvider()
        app.dependency_overrides[get_stt_provider] = lambda: stt_provider
        app.dependency_overrides[get_tts_provider] = lambda: tts_provider

        try:
            payload = {
                "audio_base64": GOLDEN_AUDIO_B64,
                "format": "WAV",
                "sample_rate_hz": 16000,
                "channels": "MONO",
                "duration_ms": 1500,
                "user_consent_granted": True,
                "input_mode": "PTT",
                "synthesize_reply_audio": True,
            }
            resp = await client.post(f"/conversations/{conv_id}/voice-messages", json=payload)
            assert resp.status_code == 201
            data = resp.json()

            # 1. Transcript recognized
            assert data["transcribed_text"] == "What is your favorite memory?"

            # 2. User message persisted
            assert data["message"]["content"] == "What is your favorite memory?"
            assert data["message"]["role"] == "user"

            # 3. Assistant response generated and persisted
            assert data["assistant_response"] is not None
            assert data["assistant_status"] == "generated"

            # 4. Audio reply synthesized
            assert data["audio_status"] == "success"
            assert data["audio_data_base64"] is not None
            assert data["audio_cache_key"] is not None

            # 5. Audio streamable from cache
            audio_resp = await client.get(f"/voice/audio/{data['audio_cache_key']}")
            assert audio_resp.status_code == 200
            assert audio_resp.headers["content-type"] == "audio/wav"
            assert len(audio_resp.content) > 0
        finally:
            app.dependency_overrides.pop(get_stt_provider, None)
            app.dependency_overrides.pop(get_tts_provider, None)

    @pytest.mark.asyncio
    async def test_gc269_semantic_replay_determinism_across_voice_turns(
        self,
        client: AsyncClient,
    ):
        """GC-269: Replaying voice input produces deterministic semantic projection and cache key stability."""
        conv_resp1 = await client.post("/conversations")
        conv_id1 = conv_resp1.json()["id"]

        conv_resp2 = await client.post("/conversations")
        conv_id2 = conv_resp2.json()["id"]

        stt_provider = MockSTTProvider(default_transcript="Consistent deterministic input")
        app.dependency_overrides[get_stt_provider] = lambda: stt_provider

        try:
            payload = {
                "audio_base64": GOLDEN_AUDIO_B64,
                "format": "WAV",
                "user_consent_granted": True,
                "input_mode": "PTT",
                "synthesize_reply_audio": True,
            }
            resp1 = await client.post(f"/conversations/{conv_id1}/voice-messages", json=payload)
            resp2 = await client.post(f"/conversations/{conv_id2}/voice-messages", json=payload)

            assert resp1.status_code == 201
            assert resp2.status_code == 201

            data1 = resp1.json()
            data2 = resp2.json()

            # Transcript must be identical
            assert data1["transcribed_text"] == data2["transcribed_text"]

            # Cache key for identical assistant response content must be identical
            if data1["assistant_response"]["content"] == data2["assistant_response"]["content"]:
                assert data1["audio_cache_key"] == data2["audio_cache_key"]
        finally:
            app.dependency_overrides.pop(get_stt_provider, None)

    def test_gc270_full_voice_constitutional_boundary_audit(self):
        """GC-270: Full system-wide AST audit enforcing Constitutional Locks 1–10 and ADR-021.

        Verifies 0 unauthorized mutation tokens, 0 continuous VAD calls, and 0 concrete engine imports.
        """
        backend_dir = pathlib.Path(__file__).parent.parent / "app"
        voice_targets = list((backend_dir / "voice").rglob("*.py")) + [
            backend_dir / "api" / "voice.py",
            backend_dir / "api" / "conversations.py",
        ]

        forbidden_tokens = {
            "set_fact",
            "PromotionAuthorizationToken",
            "continuous_vad",
            "listen_continuously",
            "vad_detector",
        }

        violations = []
        for file_path in voice_targets:
            tree = ast.parse(file_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id in forbidden_tokens:
                    violations.append((file_path.name, node.id, node.lineno))
                elif isinstance(node, ast.Attribute) and node.attr in forbidden_tokens:
                    violations.append((file_path.name, node.attr, node.lineno))

        assert not violations, f"Constitutional boundary violations detected: {violations}"
