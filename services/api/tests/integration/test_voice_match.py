"""Integration tests for POST /v1/voice/match.

Whisper is mocked end-to-end: we patch the route's `_make_whisper_client` so
no real OpenAI call is made. The fixture below builds a fake `WhisperClient`
that returns a predetermined transcript.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from smartscale_api.app import create_app
from smartscale_api.config import Settings
from smartscale_api.routes import voice as voice_route
from smartscale_api.voice.whisper_client import TranscriptionResult, WhisperError

pytestmark = pytest.mark.integration


DEVICE = "scale-abc"


class _FakeWhisper:
    """Mimics WhisperClient.transcribe + aclose; raises if instructed."""

    def __init__(
        self, *, text: str = "log a banana", lang: str = "en", raise_with: Exception | None = None
    ):
        self._text = text
        self._lang = lang
        self._raise = raise_with

    async def transcribe(
        self,
        *,
        audio_bytes: bytes,
        content_type: str,
        filename: str = "audio.m4a",
        prompt: str | None = None,
        language: str | None = None,
    ) -> TranscriptionResult:
        if self._raise is not None:
            raise self._raise
        return TranscriptionResult(text=self._text, language=self._lang)

    async def aclose(self) -> None:
        return None


@pytest_asyncio.fixture
async def voice_app(database_url: str, schema: None) -> FastAPI:
    """Like the shared `app` fixture but with OPENAI_API_KEY set."""
    settings = Settings(
        env="test",
        device_key=SecretStr("test-key"),
        database_url=database_url,
        openai_api_key=SecretStr("sk-test-fake"),
    )
    return create_app(settings=settings)


@pytest_asyncio.fixture
async def voice_client(voice_app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=voice_app),
        base_url="http://test",
        headers={"x-device-key": "test-key"},
    ) as c:
        yield c


def _patch_whisper(monkeypatch: pytest.MonkeyPatch, fake: _FakeWhisper) -> None:
    monkeypatch.setattr(voice_route, "_make_whisper_client", lambda settings: fake)


async def _seed_pantry_banana(db_session: AsyncSession, client: AsyncClient) -> str:
    """Add a Banana pantry entry. Returns the pantry_item_id."""
    resp = await client.post(
        "/v1/pantry",
        json={
            "device_id": DEVICE,
            "custom": {
                "name": "Banana",
                "per_100g": {
                    "kcal": "89",
                    "protein_g": "1.1",
                    "carbs_g": "23",
                    "fat_g": "0.3",
                    "fiber_g": "2.6",
                },
                "default_serving_g": "118",
            },
        },
    )
    assert resp.status_code == 201
    pi_id: str = resp.json()["id"]
    return pi_id


async def test_returns_transcript_and_candidate(
    voice_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pi_id = await _seed_pantry_banana(db_session, voice_client)
    _patch_whisper(monkeypatch, _FakeWhisper(text="log a banana"))

    files = {"audio": ("clip.m4a", b"\x00\x01\x02\x03", "audio/mp4")}
    data: dict[str, Any] = {"device_id": DEVICE}
    r = await voice_client.post("/v1/voice/match", files=files, data=data)
    assert r.status_code == 200
    body = r.json()
    assert body["transcript"] == "log a banana"
    assert body["language"] == "en"
    assert body["candidate"] is not None
    assert body["candidate"]["pantry_item_id"] == pi_id
    assert body["candidate"]["name"] == "Banana"
    # No weight in transcript → falls back to default_serving_g
    assert Decimal(body["candidate"]["weight_grams"]) == Decimal("118")


async def test_picks_up_explicit_weight_in_transcript(
    voice_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _seed_pantry_banana(db_session, voice_client)
    _patch_whisper(monkeypatch, _FakeWhisper(text="ate 200 grams of banana"))

    r = await voice_client.post(
        "/v1/voice/match",
        files={"audio": ("clip.m4a", b"\x00", "audio/mp4")},
        data={"device_id": DEVICE},
    )
    assert r.status_code == 200
    assert Decimal(r.json()["candidate"]["weight_grams"]) == Decimal("200")


async def test_unmatched_returns_null_candidate(
    voice_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _seed_pantry_banana(db_session, voice_client)
    _patch_whisper(monkeypatch, _FakeWhisper(text="zebra giraffe quasar"))

    r = await voice_client.post(
        "/v1/voice/match",
        files={"audio": ("clip.m4a", b"\x00", "audio/mp4")},
        data={"device_id": DEVICE},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["candidate"] is None
    assert body["transcript"] == "zebra giraffe quasar"


async def test_empty_audio_returns_400(
    voice_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_whisper(monkeypatch, _FakeWhisper(text="ignored"))
    r = await voice_client.post(
        "/v1/voice/match",
        files={"audio": ("clip.m4a", b"", "audio/mp4")},
        data={"device_id": DEVICE},
    )
    assert r.status_code == 400


async def test_whisper_error_returns_502(
    voice_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _seed_pantry_banana(db_session, voice_client)
    _patch_whisper(monkeypatch, _FakeWhisper(raise_with=WhisperError("upstream 500")))

    r = await voice_client.post(
        "/v1/voice/match",
        files={"audio": ("clip.m4a", b"\x00", "audio/mp4")},
        data={"device_id": DEVICE},
    )
    assert r.status_code == 502


async def test_missing_api_key_returns_503(
    database_url: str,
    schema: None,
    db_session: AsyncSession,
) -> None:
    settings = Settings(
        env="test",
        device_key=SecretStr("test-key"),
        database_url=database_url,
        # openai_api_key intentionally empty
    )
    app = create_app(settings=settings)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"x-device-key": "test-key"},
    ) as c:
        r = await c.post(
            "/v1/voice/match",
            files={"audio": ("clip.m4a", b"\x00", "audio/mp4")},
            data={"device_id": DEVICE},
        )
        assert r.status_code == 503


async def test_requires_device_key(voice_app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=voice_app), base_url="http://test") as c:
        r = await c.post(
            "/v1/voice/match",
            files={"audio": ("clip.m4a", b"\x00", "audio/mp4")},
            data={"device_id": DEVICE},
        )
        assert r.status_code == 401


async def test_unused_text_import(db_session: AsyncSession) -> None:
    """Smoke check that the conftest db_session still cleans pantry tables."""
    # Sanity: an empty pantry returns nothing.
    rows = (await db_session.execute(text("SELECT COUNT(*) FROM pantry_items"))).scalar_one()
    assert rows == 0
