"""Helpers for loading docs/fixtures/rest/ during contract tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

FIXTURE_DIR = Path(__file__).resolve().parents[3] / "docs" / "fixtures" / "rest"

DYNAMIC_PLACEHOLDERS: dict[str, str] = {
    "id": "mea_<dynamic>",
    "server_received_at": "<dynamic>",
}


def load(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8")))


def strip_dynamic(payload: dict[str, Any]) -> dict[str, Any]:
    """Replace dynamic fields with their placeholder value before comparing."""
    out = dict(payload)
    for key, placeholder in DYNAMIC_PLACEHOLDERS.items():
        if key in out:
            out[key] = placeholder
    return out
