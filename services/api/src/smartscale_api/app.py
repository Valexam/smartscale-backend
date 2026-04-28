"""FastAPI application factory."""

from __future__ import annotations

import logging

from fastapi import FastAPI

from smartscale_api import __version__
from smartscale_api.auth import DeviceKeyMiddleware, RedactingFilter
from smartscale_api.config import Settings
from smartscale_api.db import make_engine, make_sessionmaker
from smartscale_api.deps import _set_sessionmaker
from smartscale_api.routes import health, measurements


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.assert_safe_to_start()

    _install_redacting_filter()

    engine = make_engine(settings)
    sm = make_sessionmaker(engine)

    # Populate the deps module so that route Depends(get_session) resolves correctly.
    _set_sessionmaker(sm)

    app = FastAPI(
        title="SmartScale API",
        version=__version__,
        openapi_url="/v1/openapi.json",
        docs_url="/v1/docs",
        redoc_url=None,
    )

    app.include_router(health.router, prefix="/v1")
    app.include_router(measurements.router, prefix="/v1")

    app.add_middleware(DeviceKeyMiddleware, settings=settings)

    return app


def _install_redacting_filter() -> None:
    flt = RedactingFilter()
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"):
        logging.getLogger(name).addFilter(flt)
