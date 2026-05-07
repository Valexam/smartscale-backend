"""FastAPI application factory."""

from __future__ import annotations

import logging

from fastapi import FastAPI

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
    """
    logger = logging.getLogger("smartscale_api")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)-8s %(name)s - %(message)s"))
        logger.addHandler(handler)
        logger.propagate = False  # handled here; skip root to avoid duplicates
