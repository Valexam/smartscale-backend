"""OpenAI Whisper client (HTTPX wrapper).

Single-shot upload to /v1/audio/transcriptions. No streaming, no retries —
the caller (route layer) owns 502/503 mapping. We deliberately avoid the
official `openai` SDK to keep dep surface small; the REST shape is stable.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

OPENAI_AUDIO_URL = "https://api.openai.com/v1/audio/transcriptions"


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str | None


class WhisperError(RuntimeError):
    """Raised when Whisper returns a non-2xx status or the request fails."""


class WhisperClient:
    """Tiny async client. Re-uses a single HTTPX client across calls."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "whisper-1",
        timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None

    async def transcribe(
        self,
        *,
        audio_bytes: bytes,
        content_type: str,
        filename: str = "audio.m4a",
        prompt: str | None = None,
        language: str | None = None,
    ) -> TranscriptionResult:
        files = {"file": (filename, audio_bytes, content_type)}
        data: dict[str, str] = {
            "model": self._model,
            "response_format": "verbose_json",
            "temperature": "0",
        }
        if prompt:
            data["prompt"] = prompt
        if language:
            data["language"] = language
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            resp = await self._client.post(
                OPENAI_AUDIO_URL, files=files, data=data, headers=headers
            )
        except httpx.HTTPError as e:
            raise WhisperError(f"Whisper request failed: {e}") from e

        if resp.status_code >= 400:
            raise WhisperError(f"Whisper returned {resp.status_code}: {resp.text[:500]}")

        body = resp.json()
        return TranscriptionResult(
            text=str(body.get("text", "")).strip(),
            language=body.get("language"),
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
