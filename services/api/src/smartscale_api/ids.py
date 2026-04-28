"""Server-generated IDs."""

from __future__ import annotations

from ulid import ULID


def new_measurement_id() -> str:
    """Return `mea_<26-char ulid lowercase>`."""
    return f"mea_{str(ULID()).lower()}"
