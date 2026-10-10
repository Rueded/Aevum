"""Test suite for Phase 10.3 Text-to-Speech Engine & Canonical Audio Cache.

Tests:
1. AudioCache put, get, hit/miss, LRU eviction, and TTL expiration (ADR-021 Lock E & Lock F).
2. MockTTSProvider deterministic synthesis, valid WAV RIFF structure, and failure simulation.
3. TTSService orchestration, cache-aside behavior, and cross-emotion separation.
4. Decoupled Failure Resilience (ADR-021 Lock B): provider failure/timeout never raises unhandled exception.
5. Ephemeral Media Isolation (ADR-021 Lock F): cache eviction/purge strictly isolated from domain state.
6. Static AST Boundary Audit across Phase 10.3 modules (0 DB, 0 network, 0 mutation tokens).
"""

import ast
from datetime import datetime, timedelta, timezone
import pathlib
import pytest
from pydantic import ValidationError

from app.voice import (
    AudioCache,
    AudioCacheEntry,
    AudioChannel,
    AudioData,
    AudioFormat,
    AudioMediaLifecycle,
    EpistemicCue,
    ProsodyConfig,
    SynthesisRequest,
    SynthesisResult,
    SynthesisStatus,
    TTSService,
    compute_canonical_audio_cache_key,
)
from app.voice.providers.base import TTSProvider, TTSProviderError
from app.voice.providers.mock_tts import MockTTSProvider


class TestAudioCacheOperations:
    """Verifies ADR-021 Lock E (Canonical Cache Identity) and Lock F (Ephemeral Media Isolation)."""

    def test_cache_put_and_get_hit(self):
        cache = AudioCache(max_entries=10, default_ttl_seconds=3600)
        audio = AudioData.create(b"test_payload_bytes", AudioFormat.WAV, 24000, AudioChannel.MONO, 200)
        cache_key = "key_test_001"

        assert cache.current_size == 0
        assert cache.get(cache_key) is None

        cache.put(cache_key, audio)
        assert cache.current_size == 1

        hit = cache.get(cache_key)
        assert hit is not None
        assert hit.data == audio.data
        assert hit.sha256_hash == audio.sha256_hash

    def test_cache_ttl_expiration(self):
        """Expired entries must return None and transition lifecycle to EXPIRED."""
        cache = AudioCache(max_entries=10, default_ttl_seconds=10)
        audio = AudioData.create(b"ephemeral_bytes", AudioFormat.WAV, 24000, AudioChannel.MONO, 150)
        cache_key = "key_expiring"

        t0 = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
        cache.put(cache_key, audio, ttl_seconds=10, now=t0)

        # Before TTL expiry
        t_valid = t0 + timedelta(seconds=5)
        assert cache.get(cache_key, now=t_valid) is not None

        # After TTL expiry
        t_expired = t0 + timedelta(seconds=11)
        assert cache.get(cache_key, now=t_expired) is None
        assert cache.current_size == 0

    def test_cache_evict_expired_batch(self):
        cache = AudioCache(max_entries=10, default_ttl_seconds=10)
        audio = AudioData.create(b"audio_bytes", AudioFormat.WAV, 24000, AudioChannel.MONO, 150)
        t0 = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)

        cache.put("k1", audio, ttl_seconds=5, now=t0)
        cache.put("k2", audio, ttl_seconds=15, now=t0)
        assert cache.current_size == 2

        # At t0 + 10s: k1 expired, k2 active
        evicted = cache.evict_expired(now=t0 + timedelta(seconds=10))
        assert evicted == 1
        assert cache.current_size == 1
        assert cache.get("k2", now=t0 + timedelta(seconds=10)) is not None

    def test_cache_lru_capacity_eviction(self):
        """Capacity overflow evicts the least recently accessed item."""
        cache = AudioCache(max_entries=2, default_ttl_seconds=3600)
        a1 = AudioData.create(b"audio_1", AudioFormat.WAV, 24000, AudioChannel.MONO, 100)
        a2 = AudioData.create(b"audio_2", AudioFormat.WAV, 24000, AudioChannel.MONO, 100)
        a3 = AudioData.create(b"audio_3", AudioFormat.WAV, 24000, AudioChannel.MONO, 100)

        cache.put("k1", a1)
        cache.put("k2", a2)
        assert cache.current_size == 2

        # Access k1 to make k2 the least recently accessed
        _ = cache.get("k1")

        # Insert k3: k2 should be evicted
        cache.put("k3", a3)
        assert cache.current_size == 2
        assert cache.get("k1") is not None
        assert cache.get("k2") is None
        assert cache.get("k3") is not None

    def test_cache_purge_all_isolation(self):
        """ADR-021 Lock F: Purging cache empties store without affecting domain state."""
        cache = AudioCache(max_entries=5)
        audio = AudioData.create(b"sample_data", AudioFormat.WAV, 24000, AudioChannel.MONO, 100)
        cache.put("k1", audio)
        cache.put("k2", audio)

        assert cache.current_size == 2
        purged_count = cache.purge_all()
        assert purged_count == 2
        assert cache.current_size == 0


class TestMockTTSProvider:
    """Verifies deterministic synthesis and WAV binary structure."""

    @pytest.mark.asyncio
    async def test_mock_tts_synthesizes_valid_wav(self):
        provider = MockTTSProvider()
        req = SynthesisRequest(
            request_id="req-001",
            text="Hello from Aevum!",
            voice_id="aevum_default",
            desired_format=AudioFormat.WAV,
            prosody=ProsodyConfig(rate_multiplier=1.0, pitch_shift_semitones=0.0),
        )

        res = await provider.synthesize(req)
        assert res.status == SynthesisStatus.SUCCESS
        assert res.audio is not None
        assert res.error_message is None
        assert res.provider_id == "mock_tts"
        assert res.cache_key is not None

        # Verify WAV structural header
        wav_bytes = res.audio.data
        assert wav_bytes.startswith(b"RIFF")
        assert b"WAVE" in wav_bytes[:16]
        assert b"fmt " in wav_bytes[:20]
        assert b"data" in wav_bytes[30:44]
        assert len(wav_bytes) > 44

    @pytest.mark.asyncio
    async def test_mock_tts_simulated_failure(self):
        provider = MockTTSProvider(simulate_failure=True, failure_message="Engine quota exceeded")
        req = SynthesisRequest(request_id="req-002", text="Test", voice_id="v1")
        res = await provider.synthesize(req)

        assert res.status == SynthesisStatus.FAILED
        assert res.audio is None
        assert res.error_message == "Engine quota exceeded"

    @pytest.mark.asyncio
    async def test_mock_tts_simulated_unavailable(self):
        provider = MockTTSProvider(simulate_unavailable=True)
        assert await provider.is_available() is False

        req = SynthesisRequest(request_id="req-003", text="Test", voice_id="v1")
        res = await provider.synthesize(req)

        assert res.status == SynthesisStatus.UNAVAILABLE
        assert res.audio is None


class TestTTSServiceOrchestration:
    """Verifies TTSService cache-aside and decoupled fault tolerance."""

    @pytest.mark.asyncio
    async def test_tts_service_cache_aside_flow(self):
        provider = MockTTSProvider()
        cache = AudioCache()
        service = TTSService(provider=provider, cache=cache)

        req = SynthesisRequest(
            request_id="req-101",
            text="Let's study for the upcoming quiz.",
            voice_id="aevum_default",
            prosody=ProsodyConfig(rate_multiplier=1.05),
        )

        # 1. First call: Cache MISS -> Provider invoked
        assert cache.current_size == 0
        assert provider.invocation_count == 0

        res1 = await service.synthesize(req)
        assert res1.status == SynthesisStatus.SUCCESS
        assert provider.invocation_count == 1
        assert cache.current_size == 1

        # 2. Second identical call: Cache HIT -> Provider NOT invoked
        res2 = await service.synthesize(req)
        assert res2.status == SynthesisStatus.SUCCESS
        assert provider.invocation_count == 1  # count did not increase
        assert res2.audio.data == res1.audio.data
        assert res2.cache_key == res1.cache_key

    @pytest.mark.asyncio
    async def test_cross_emotion_cache_divergence(self):
        """ADR-021 Lock E: Identical text with different prosody must not share cache."""
        provider = MockTTSProvider()
        cache = AudioCache()
        service = TTSService(provider=provider, cache=cache)

        text = "I'm going to the campus now."

        req_happy = SynthesisRequest(
            request_id="req-h",
            text=text,
            voice_id="aevum_v1",
            prosody=ProsodyConfig(rate_multiplier=1.10, pitch_shift_semitones=2.0),
        )
        req_sad = SynthesisRequest(
            request_id="req-s",
            text=text,
            voice_id="aevum_v1",
            prosody=ProsodyConfig(rate_multiplier=0.90, pitch_shift_semitones=-2.0),
        )

        res_happy = await service.synthesize(req_happy)
        res_sad = await service.synthesize(req_sad)

        assert provider.invocation_count == 2
        assert cache.current_size == 2
        assert res_happy.cache_key != res_sad.cache_key

    @pytest.mark.asyncio
    async def test_convenience_method_synthesize_text(self):
        provider = MockTTSProvider()
        service = TTSService(provider=provider)

        res = await service.synthesize_text(
            text="Good afternoon!",
            epistemic_cue=EpistemicCue.CERTAIN,
        )
        assert res.status == SynthesisStatus.SUCCESS
        assert res.audio is not None


class TestDecoupledFailureResilienceLockB:
    """Verifies ADR-021 Lock B: TTS failure must never crash conversational mind."""

    @pytest.mark.asyncio
    async def test_provider_error_absorbed_gracefully(self):
        class CrashingTTSProvider(TTSProvider):
            @property
            def provider_id(self) -> str:
                return "crashing_tts"

            @property
            def provider_version(self) -> str:
                return "0.0.1"

            async def is_available(self) -> bool:
                return False

            async def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
                raise TTSProviderError("Connection refused by audio synthesizer")

        service = TTSService(provider=CrashingTTSProvider())
        req = SynthesisRequest(request_id="req-crash", text="Test crash", voice_id="v1")

        # Must NOT raise unhandled exception!
        res = await service.synthesize(req)
        assert res.status == SynthesisStatus.FAILED
        assert res.audio is None
        assert "Connection refused" in (res.error_message or "")

    @pytest.mark.asyncio
    async def test_unexpected_runtime_exception_absorbed_gracefully(self):
        class BuggyTTSProvider(TTSProvider):
            @property
            def provider_id(self) -> str:
                return "buggy_tts"

            @property
            def provider_version(self) -> str:
                return "0.0.1"

            async def is_available(self) -> bool:
                return True

            async def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
                raise RuntimeError("Unexpected internal crash inside proprietary driver")

        service = TTSService(provider=BuggyTTSProvider())
        req = SynthesisRequest(request_id="req-buggy", text="Test bug", voice_id="v1")

        # Must NOT raise unhandled exception!
        res = await service.synthesize(req)
        assert res.status == SynthesisStatus.UNAVAILABLE
        assert res.audio is None
        assert "Unexpected internal crash" in (res.error_message or "")


class TestStaticASTBoundaryAuditPhase103:
    """Static AST Boundary Audit for Phase 10.3 modules.

    Target files:
    - app/voice/audio_cache.py
    - app/voice/providers/mock_tts.py
    - app/voice/tts_service.py

    Asserts:
    1. ZERO database imports or calls (sqlite3, sqlalchemy, aiosqlite).
    2. ZERO network imports or calls (httpx, requests, aiohttp, urllib, google.genai).
    3. ZERO mutation or promotion authority (set_fact, PromotionAuthorizationToken).
    4. ZERO STT imports or methods (no premature Phase 10.4 implementation).
    """

    def test_static_ast_boundary_audit(self):
        app_voice_dir = pathlib.Path(__file__).resolve().parent.parent / "app" / "voice"
        phase103_files = [
            app_voice_dir / "audio_cache.py",
            app_voice_dir / "providers" / "mock_tts.py",
            app_voice_dir / "tts_service.py",
        ]

        forbidden_io_modules = {
            "requests", "httpx", "aiohttp", "urllib", "socket",
            "sqlalchemy", "sqlite3", "aiosqlite", "redis",
            "google.genai",
        }
        forbidden_mutation_tokens = {"set_fact", "PromotionAuthorizationToken"}
        forbidden_stt_tokens = {"STTService", "transcribe_audio"}

        violations: list[str] = []

        for fpath in phase103_files:
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

                # 3. Zero premature STT implementation
                if isinstance(node, ast.Name) and node.id in forbidden_stt_tokens:
                    violations.append(f"{fpath.name}:{node.lineno} prematurely references STT token '{node.id}'")

        assert not violations, f"AST boundary violations detected across Phase 10.3: {violations}"
