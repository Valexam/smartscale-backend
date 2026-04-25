"""Uvicorn entry point: `python -m smartscale_api.main`."""

import uvicorn

from smartscale_api.app import create_app

app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "smartscale_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
