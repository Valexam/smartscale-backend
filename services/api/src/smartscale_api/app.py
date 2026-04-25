"""FastAPI application factory."""

from fastapi import FastAPI

from smartscale_api import __version__
from smartscale_api.routes import health


def create_app() -> FastAPI:
    app = FastAPI(
        title="SmartScale API",
        version=__version__,
        openapi_url="/v1/openapi.json",
        docs_url="/v1/docs",
        redoc_url=None,
    )
    app.include_router(health.router, prefix="/v1")
    return app
