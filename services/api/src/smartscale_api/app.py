"""FastAPI application factory."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from smartscale_api import __version__
from smartscale_api.auth import DeviceKeyMiddleware, RedactingHandler
from smartscale_api.config import Settings
from smartscale_api.db import make_engine, make_sessionmaker
from smartscale_api.routes import (
    health,
    measurements,
    pantry,
    products,
    user_foods,
    voice,
)
from smartscale_api.schemas.errors import problem_response

# Maps an HTTP status to a stable machine-readable error code for problem+json.
# Anything not listed falls back to "HTTP_ERROR".
_CODE_BY_STATUS: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    410: "GONE",
    422: "VALIDATION_ERROR",
    500: "INTERNAL_ERROR",
    502: "UPSTREAM_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


async def _http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Render route-level HTTPExceptions as RFC 7807 application/problem+json.

    Without this, FastAPI returns a bare ``{"detail": ...}`` body, so only the
    auth middleware (which builds problem+json directly) was RFC 7807. Mobile's
    error parser expects the problem+json shape on every error.
    """
    assert isinstance(exc, StarletteHTTPException)
    detail = exc.detail
    extra: dict[str, Any] = {}
    if isinstance(detail, dict):
        # Routes occasionally raise a dict detail (e.g. the archived-pantry 410
        # carries archived_at). Promote "msg" to the problem detail; keep the
        # rest as problem+json extension members.
        detail_str = str(detail.get("msg") or detail.get("detail") or "error")
        extra = {k: v for k, v in detail.items() if k != "msg"}
    else:
        detail_str = detail if isinstance(detail, str) else str(detail)
    code = _CODE_BY_STATUS.get(exc.status_code, "HTTP_ERROR")
    response = problem_response(exc.status_code, code, detail_str, **extra)
    for key, value in (exc.headers or {}).items():
        response.headers[key] = value
    return response


async def _validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Render request-validation failures as RFC 7807 with an `errors` member."""
    assert isinstance(exc, RequestValidationError)
    errors = jsonable_encoder(exc.errors())
    n = len(errors)
    detail = f"{n} validation error{'s' if n != 1 else ''}"
    return problem_response(422, "VALIDATION_ERROR", detail, errors=errors)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.assert_safe_to_start()

    _install_redacting_filter()
    _configure_app_logging()

    app = FastAPI(
        title="SmartScale API",
        version=__version__,
        openapi_url="/v1/openapi.json",
        docs_url="/v1/docs",
        redoc_url=None,
    )

    app.state.settings = settings
    if settings.database_url:
        engine = make_engine(settings)
        app.state.sessionmaker = make_sessionmaker(engine)

    app.include_router(health.router, prefix="/v1")
    app.include_router(measurements.router, prefix="/v1")
    app.include_router(products.router, prefix="/v1")
    app.include_router(user_foods.router, prefix="/v1")
    app.include_router(pantry.router, prefix="/v1")
    app.include_router(voice.router, prefix="/v1")

    # RFC 7807 problem+json for every error, not just auth (see handlers above).
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)

    app.add_middleware(DeviceKeyMiddleware, settings=settings)

    return app


def _install_redacting_filter() -> None:
    """Attach a RedactingHandler to root so every propagating log record is scrubbed.

    Using a Handler (not a Logger filter) ensures that propagated records from
    child loggers are also scrubbed — Logger.filter() only runs on records
    handled directly by that logger, not on records that propagate through it.
    """
    logging.getLogger().addHandler(RedactingHandler())


def _configure_app_logging() -> None:
    """Give the smartscale_api namespace a real stderr handler at INFO level.

    Uvicorn's dictConfig attaches its StreamHandler only to the 'uvicorn'
    logger (propagate=False), leaving root with no real output handler.
    Without this, _log.info() calls in routes are silently dropped because
    the effective level inherited from root is WARNING.

    propagate=True is intentional: root has no StreamHandler (uvicorn omits
    it), so there is no duplicate output. Propagation is required so pytest's
    caplog handler (installed on root) can capture records. The StreamHandler
    carries its own RedactingFilter so stderr output is scrubbed before emit,
    independent of the root-level RedactingHandler.
    """
    from smartscale_api.auth import RedactingFilter

    logger = logging.getLogger("smartscale_api")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)-8s %(name)s - %(message)s"))
        handler.addFilter(RedactingFilter())
        logger.addHandler(handler)
