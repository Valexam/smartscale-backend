"""X-Device-Key middleware + a logging filter that redacts auth headers."""

from __future__ import annotations

import hmac
import logging
from collections.abc import Awaitable, Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from smartscale_api.config import Settings
from smartscale_api.schemas.errors import problem_response

REDACTED_HEADER_NAMES: frozenset[str] = frozenset(
    {
        "x-device-key",
        "authorization",
        "x-admin-key",
    }
)


class RedactingFilter(logging.Filter):
    """Replace any string log argument that contains a sensitive header name."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(_redact(a) for a in record.args)
        elif isinstance(record.args, dict):
            record.args = {k: _redact(v) for k, v in record.args.items()}
        return True


def _redact(value: object) -> object:
    if not isinstance(value, str):
        return value
    lower = value.lower()
    for header in REDACTED_HEADER_NAMES:
        if header in lower:
            return "[REDACTED]"
    return value


class DeviceKeyMiddleware(BaseHTTPMiddleware):
    """Gate /v1/* routes (except /v1/healthz) with X-Device-Key."""

    def __init__(self, app: object, settings: Settings) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._expected = settings.device_key.get_secret_value().encode()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path
        if path == "/v1/healthz" or not path.startswith("/v1/"):
            return await call_next(request)

        provided = request.headers.get("x-device-key")
        if provided is None:
            return problem_response(401, "MISSING_DEVICE_KEY", "X-Device-Key header is required")
        if not hmac.compare_digest(provided.encode(), self._expected):
            return problem_response(401, "INVALID_DEVICE_KEY", "X-Device-Key does not match")
        return await call_next(request)
