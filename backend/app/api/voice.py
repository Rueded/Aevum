"""Voice API router for standalone speech-to-text, text-to-speech, and audio streaming (Phase 10.5).

Governed by ADR-021:
- Voice is the Body: Voice endpoints provide audio I/O services without altering canonical mind.
- Rule 18 Consent: STT requests require explicit user consent verification.
- Decoupled Failure: TTS synthesis errors return failure status without crashing the API.
- Lock E: Canonical cache key retrieval.
"""

import base64
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    VoiceSTTRequest,
    VoiceSTTResponse,
    VoiceTTSRequest,
    VoiceTTSResponse,
)
from app.character.state_service import CharacterStateService
from app.db.session import get_db_session
from app.emotion.service import EmotionService
from app.voice import (
    AudioCache,
    AudioChannel,
    AudioData,
    AudioFormat,
    EpistemicCue,
    ProsodyConfig,
    ProsodyMapper,
    STTService,
    TTSService,
    TranscriptionStatus,
    VoiceInputMode,
)
from app.voice.dependencies import (
    get_audio_cache,
    get_stt_service,
    get_tts_service,
)

router = APIRouter(prefix="/voice", tags=["Voice"])


@router.post(
    "/stt",
    response_model=VoiceSTTResponse,
    status_code=status.HTTP_200_OK,
    summary="Transcribe spoken audio into text with Rule 18 consent check",
)
async def transcribe_audio(
    payload: VoiceSTTRequest,
    stt_service: STTService = Depends(get_stt_service),
) -> VoiceSTTResponse:
    """Transcribe base64-encoded audio payload into text."""
    # 1. Enforce Rule 18 consent
    if not payload.user_consent_granted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Voice transcription rejected: Rule 18 requires explicit user consent.",
        )

    # 2. Decode audio bytes
    try:
        raw_bytes = base64.b64decode(payload.audio_base64)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Malformed audio_base64 payload: {exc}",
        ) from exc

    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Audio payload cannot be empty.",
        )

    try:
        fmt = AudioFormat(payload.format.upper())
        channels = AudioChannel(payload.channels.upper())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid audio format or channel: {exc}",
        ) from exc

    audio = AudioData.create(
        data=raw_bytes,
        format=fmt,
        sample_rate_hz=payload.sample_rate_hz,
        channels=channels,
        duration_ms=payload.duration_ms,
    )

    result = await stt_service.transcribe_audio(
        audio=audio,
        user_consent_granted=payload.user_consent_granted,
    )

    return VoiceSTTResponse(
        status=result.status.value.lower(),
        transcribed_text=result.transcribed_text,
        error_message=result.error_message,
    )


@router.post(
    "/tts",
    response_model=VoiceTTSResponse,
    status_code=status.HTTP_200_OK,
    summary="Synthesize text into speech with emotional prosody modulation",
)
async def synthesize_speech(
    payload: VoiceTTSRequest,
    tts_service: TTSService = Depends(get_tts_service),
    db: AsyncSession = Depends(get_db_session),
) -> VoiceTTSResponse:
    """Synthesize text into speech using companion's current emotional state."""
    if not payload.text or not payload.text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Text cannot be empty or whitespace only.",
        )

    try:
        fmt = AudioFormat(payload.desired_format.upper())
        epistemic_cue = EpistemicCue(payload.epistemic_cue.upper())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid format or epistemic cue: {exc}",
        ) from exc

    # Query current emotional state for deterministic prosody mapping (Lock C)
    emotion_service = EmotionService(db)
    state_service = CharacterStateService(db)

    try:
        current_emotion = await emotion_service.get_emotion_state(payload.character_id)
        current_char_state = await state_service.get_state(payload.character_id)
        prosody = ProsodyMapper.from_states(
            emotion_state=current_emotion,
            character_state=current_char_state,
            epistemic_cue=epistemic_cue,
        )
    except Exception:
        # Fallback to neutral baseline prosody if state unavailable
        prosody = ProsodyConfig()

    result = await tts_service.synthesize_text(
        text=payload.text,
        voice_id=payload.voice_id,
        desired_format=fmt,
        prosody=prosody,
        epistemic_cue=epistemic_cue,
    )

    audio_b64: Optional[str] = None
    duration_ms = 0
    if result.audio is not None:
        audio_b64 = base64.b64encode(result.audio.data).decode("ascii")
        duration_ms = result.audio.duration_ms

    return VoiceTTSResponse(
        status=result.status.value.lower(),
        audio_base64=audio_b64,
        cache_key=result.cache_key,
        duration_ms=duration_ms,
        error_message=result.error_message,
    )


@router.get(
    "/audio/{cache_key}",
    status_code=status.HTTP_200_OK,
    summary="Retrieve cached binary audio by canonical cache key",
)
async def get_cached_audio(
    cache_key: str,
    cache: AudioCache = Depends(get_audio_cache),
) -> Response:
    """Retrieve raw audio/wav data from the ephemeral cache."""
    audio = cache.get(cache_key)
    if audio is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio artifact '{cache_key}' not found or expired.",
        )

    media_type_map = {
        AudioFormat.WAV: "audio/wav",
        AudioFormat.MP3: "audio/mpeg",
        AudioFormat.WEBM: "audio/webm",
        AudioFormat.OGG_OPUS: "audio/ogg",
    }
    media_type = media_type_map.get(audio.format, "audio/mpeg")
    return Response(content=audio.data, media_type=media_type)
