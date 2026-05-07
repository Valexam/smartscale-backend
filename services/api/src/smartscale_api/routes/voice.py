"""POST /v1/voice/match — phone-side cloud voice pipeline (MVP-5b-1).

Records audio (recorded by the phone), transcribes via Whisper, fuzzy-matches
against the device's live pantry, returns up to 3 candidates. Does NOT log
anything; the phone confirms then hits the existing /v1/pantry/{id}/log.
"""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from smartscale_api.config import Settings
from smartscale_api.deps import get_session
from smartscale_api.domain.voice_match import top_n_matches
from smartscale_api.repos import pantry as pantry_repo
from smartscale_api.repos.pantry import PantryRow
from smartscale_api.schemas.voice import VoiceCandidate, VoiceMatchResponse
from smartscale_api.voice.whisper_client import WhisperClient, WhisperError

router = APIRouter(tags=["voice"])

DbSession = Annotated[AsyncSession, Depends(get_session)]

# Dump every uploaded audio clip to disk for offline inspection. Cheap to
# leave on in dev; would be feature-flagged for prod. Files land in /tmp
# inside the api container — read with `kubectl cp` or via the Tilt UI.
_AUDIO_DUMP_DIR = Path("/tmp/voice_dumps")
_log = logging.getLogger(__name__)

# Whisper auto-detects language across ~99 tongues; on noisy short clips it
# regularly mis-classifies. Restrict to the languages this product actually
# supports so we don't fuzzy-match Italian-detected gibberish against an
# English/Swedish pantry.
ALLOWED_LANGUAGES = frozenset({"en", "english", "sv", "swedish"})

# The amplitude-based wake detector fires mid-utterance: the first ~600 ms of
# the recording contains "Hey Scale" (or similar), which Whisper transcribes
# as a spurious word ("Basket", "Scale", etc.) prepended to the food name.
# Trimming the WAV start discards the wake phrase before Whisper sees it.
# WAV format: 44-byte RIFF header + PCM-16 mono at 8 kHz (16 bytes/ms).
_WAKE_TRIM_MS = 600
_WAV_SAMPLE_RATE = 8000
_WAV_BYTES_PER_SAMPLE = 2  # PCM-16
_WAV_HEADER_SIZE = 44


def _trim_wav_start(wav: bytes, trim_ms: int) -> bytes:
    """Return wav with the first trim_ms milliseconds of audio removed."""
    import struct

    trim_bytes = (trim_ms * _WAV_SAMPLE_RATE // 1000) * _WAV_BYTES_PER_SAMPLE
    if len(wav) <= _WAV_HEADER_SIZE + trim_bytes:
        return wav  # clip is shorter than the trim window; leave it intact

    header = bytearray(wav[:_WAV_HEADER_SIZE])
    audio = wav[_WAV_HEADER_SIZE + trim_bytes :]
    struct.pack_into("<I", header, 4, 36 + len(audio))  # RIFF chunk size
    struct.pack_into("<I", header, 40, len(audio))  # data chunk size
    return bytes(header) + audio


def _candidate_tuples(rows: list[PantryRow]) -> list[tuple[str, str, Decimal | None]]:
    """Project (id, name, default_serving_g) — name comes from product/user_food."""
    out: list[tuple[str, str, Decimal | None]] = []
    for r in rows:
        if r.product is not None:
            name = r.product.name
        elif r.user_food is not None:
            name = r.user_food.name
        else:  # pragma: no cover — pantry CHECK guarantees one source
            continue
        out.append((r.item.id, name, r.item.default_serving_g))
    return out


def _build_whisper_prompt(cands: list[tuple[str, str, Decimal | None]]) -> str:
    """Bias Whisper toward this user's pantry item names.

    Short noisy clips otherwise get mis-transcribed as unrelated phrases —
    Whisper hallucinates confidently when it has no context. Listing the
    actual food names anchors the model. The prompt is intentionally
    language-neutral: pantry names may be Swedish (mjölk, kaffe), English
    (banana, milk), or mixed, and Whisper auto-detects per-utterance.
    Capped to keep the total prompt under Whisper's ~224-token budget.
    """
    if not cands:
        return ""
    names = [name for _, name, _ in cands][:50]
    return ", ".join(names) + "."


def _make_whisper_client(settings: Settings) -> WhisperClient:
    """Override hook for tests via dependency_overrides."""
    return WhisperClient(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.whisper_model,
    )


@router.post(
    "/voice/match",
    response_model=VoiceMatchResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Transcription + top-3 pantry candidates (empty list if none match)."},
        400: {"description": "Audio missing or empty."},
        502: {"description": "Whisper upstream error."},
        503: {"description": "OPENAI_API_KEY not configured on the server."},
    },
)
async def voice_match(
    request: Request,
    session: DbSession,
    device_id: Annotated[str, Form(min_length=1, max_length=64)],
    audio: Annotated[UploadFile, File(...)],
) -> VoiceMatchResponse:
    settings: Settings = request.app.state.settings
    if not settings.openai_api_key.get_secret_value().strip():
        raise HTTPException(status_code=503, detail="voice transcription not configured")

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="audio file is empty")

    # Dump the raw upload so we can replay it offline and see what Whisper
    # is actually receiving. Best-effort — never fail the request on this.
    try:
        _AUDIO_DUMP_DIR.mkdir(parents=True, exist_ok=True)
        ext = (audio.filename or "audio").rsplit(".", 1)[-1] or "bin"
        path = _AUDIO_DUMP_DIR / f"{int(time.time() * 1000)}_{device_id}.{ext}"
        path.write_bytes(audio_bytes)
        _log.info("voice.dump path=%s bytes=%d ct=%s", path, len(audio_bytes), audio.content_type)
    except Exception as e:  # pragma: no cover — diagnostic only
        _log.warning("voice.dump failed: %s", e)

    # Fetch pantry once. Used to (a) build a Whisper prompt that biases the
    # transcription toward the user's actual food names, and (b) fuzzy-match
    # the resulting transcript to candidates.
    rows = await pantry_repo.list_live(session, device_id=device_id, limit=200, offset=0)
    cands = _candidate_tuples(rows)

    # Trim the wake-word audio so Whisper doesn't transcribe "Hey Scale".
    # Only applied to WAV uploads (device upload path); phone-mic uploads are
    # already food-name-only since the user taps a button to start recording.
    whisper_bytes = (
        _trim_wav_start(audio_bytes, _WAKE_TRIM_MS)
        if (audio.filename or "").endswith(".wav")
        else audio_bytes
    )

    whisper = _make_whisper_client(settings)
    try:
        transcription = await whisper.transcribe(
            audio_bytes=whisper_bytes,
            content_type=audio.content_type or "application/octet-stream",
            filename=audio.filename or "audio.m4a",
            prompt=_build_whisper_prompt(cands),
        )
    except WhisperError as e:
        raise HTTPException(status_code=502, detail=f"transcription failed: {e}") from e
    finally:
        await whisper.aclose()

    _log.info(
        "voice.transcript text=%r language=%r bytes=%d",
        transcription.text,
        transcription.language,
        len(audio_bytes),
    )

    # Detect repetition hallucinations: Whisper fills near-silent audio with
    # repeated words (e.g. "Hej. Hej. Hej..."). If the most common token
    # makes up >50% of the transcript, treat it as garbage and return nothing.
    words = transcription.text.split()
    if words:
        most_common_count = max(words.count(w) for w in set(words))
        if most_common_count >= 3 and most_common_count / len(words) > 0.5:
            _log.info("voice.hallucination detected — discarding transcript")
            return VoiceMatchResponse(
                transcript=transcription.text,
                language=transcription.language,
                candidates=[],
            )

    # Discard transcripts in unsupported languages. Whisper returns the
    # detected language in `language` (full name in verbose_json, ISO-639-1
    # in some response shapes). Compare lowercased.
    detected = (transcription.language or "").lower()
    if detected and detected not in ALLOWED_LANGUAGES:
        return VoiceMatchResponse(
            transcript=transcription.text,
            language=transcription.language,
            candidates=[],
        )

    matches = top_n_matches(transcription.text, cands, n=3)
    candidates = [
        VoiceCandidate(
            pantry_item_id=m.pantry_item_id,
            name=m.name,
            weight_grams=m.weight_grams,
            confidence=m.confidence,
        )
        for m in matches
    ]
    return VoiceMatchResponse(
        transcript=transcription.text,
        language=transcription.language,
        candidates=candidates,
    )
