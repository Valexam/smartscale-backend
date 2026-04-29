"""POST /v1/voice/match — phone-side cloud voice pipeline (MVP-5b-1).

Records audio (recorded by the phone), transcribes via Whisper, fuzzy-matches
against the device's live pantry, returns a candidate. Does NOT log anything;
the phone confirms then hits the existing /v1/pantry/{id}/log.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from smartscale_api.config import Settings
from smartscale_api.deps import get_session
from smartscale_api.domain.voice_match import best_match
from smartscale_api.repos import pantry as pantry_repo
from smartscale_api.repos.pantry import PantryRow
from smartscale_api.schemas.voice import VoiceCandidate, VoiceMatchResponse
from smartscale_api.voice.whisper_client import WhisperClient, WhisperError

router = APIRouter(tags=["voice"])

DbSession = Annotated[AsyncSession, Depends(get_session)]


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
        200: {"description": "Transcription + best pantry match (or null candidate)."},
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

    whisper = _make_whisper_client(settings)
    try:
        transcription = await whisper.transcribe(
            audio_bytes=audio_bytes,
            content_type=audio.content_type or "application/octet-stream",
            filename=audio.filename or "audio.m4a",
        )
    except WhisperError as e:
        raise HTTPException(status_code=502, detail=f"transcription failed: {e}") from e
    finally:
        await whisper.aclose()

    rows = await pantry_repo.list_live(session, device_id=device_id, limit=200, offset=0)
    cands = _candidate_tuples(rows)
    match = best_match(transcription.text, cands)

    candidate = (
        VoiceCandidate(
            pantry_item_id=match.pantry_item_id,
            name=match.name,
            weight_grams=match.weight_grams,
            confidence=match.confidence,
        )
        if match is not None
        else None
    )
    return VoiceMatchResponse(
        transcript=transcription.text,
        language=transcription.language,
        candidate=candidate,
    )
