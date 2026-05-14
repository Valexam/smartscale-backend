"""Regenerate services/api/openapi.json from the live FastAPI app.

Invocation: `uv run python scripts/generate_openapi.py` from services/api/.
CI uses the same entry point — no inline shell one-liners.
"""

from __future__ import annotations

import json
from pathlib import Path

from smartscale_api.app import create_app
from smartscale_api.config import Settings


def main() -> None:
    # Throwaway settings — create_app() only reads them to wire middleware.
    # No real DB or external call happens when we ask for the OpenAPI document.
    settings = Settings(
        env="dev",
        device_key="_",
        database_url="postgresql+asyncpg://_:_@_:5432/_",
        openai_api_key="_",
    )
    app = create_app(settings)
    out = Path(__file__).resolve().parents[1] / "openapi.json"
    out.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
