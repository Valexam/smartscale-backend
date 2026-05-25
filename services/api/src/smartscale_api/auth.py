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


class RedactingHandler(logging.Handler):
    """A logging handler that mutates records in-place to scrub sensitive data.

    Attach to the root logger so every propagating record is scrubbed before
    any other handler (e.g. caplog, StreamHandler) can read the raw values.
    This handler never emits output itself — it only runs the redaction filter.
    """

    def __init__(self) -> None:
        super().__init__()
        self.addFilter(RedactingFilter())

    def emit(self, record: logging.LogRecord) -> None:
        """No-op: record mutation happens in the filter before emit is called."""


def _redact(value: object) -> object:
    # Intentionally substring-based, defense-in-depth. May redact unrelated log
    # args containing "authorization"; tighten if false positives become noisy.
    if not isinstance(value, str):
        return value
    lower = value.lower()
    for header in REDACTED_HEADER_NAMES:
        if header in lower:
            return "[REDACTED]"
    return value


class DeviceKeyMiddleware(BaseHTTPMiddleware):
    """Gate /v1/* routes (except /v1/healthz) with X-Device-Key or X-Admin-Key.

    A request is authorized if it presents a correct ``X-Device-Key`` *or* a
    correct ``X-Admin-Key``. The admin path is only active when ``ADMIN_KEY`` is
    configured (non-empty); it exists for non-device clients such as the scraper
    worker. Both expected keys are captured at construction — rotating either
    requires restarting the process.
    """

    def __init__(self, app: object, settings: Settings) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._expected_device = settings.device_key.get_secret_value().encode()
        self._expected_admin = settings.admin_key.get_secret_value().encode()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path
        if path == "/v1/healthz" or not path.startswith("/v1/"):
            return await call_next(request)

        device_key = request.headers.get("x-device-key")
        admin_key = request.headers.get("x-admin-key")
        if device_key is None and admin_key is None:
            return problem_response(
                401, "MISSING_DEVICE_KEY", "X-Device-Key or X-Admin-Key header is required"
            )
        if device_key is not None and hmac.compare_digest(
            device_key.encode(), self._expected_device
        ):
            return await call_next(request)
        # Admin path is disabled unless ADMIN_KEY is configured (non-empty).
        if (
            admin_key is not None
            and self._expected_admin
            and hmac.compare_digest(admin_key.encode(), self._expected_admin)
        ):
            return await call_next(request)
        return problem_response(401, "INVALID_DEVICE_KEY", "X-Device-Key does not match")
