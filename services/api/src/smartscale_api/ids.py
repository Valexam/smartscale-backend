"""Server-generated IDs."""

from __future__ import annotations

from ulid import ULID


def new_measurement_id() -> str:
    """Return `mea_<26-char ulid lowercase>`."""
    return f"mea_{str(ULID()).lower()}"


def new_user_food_id() -> str:
    """Return `uf_<26-char ulid lowercase>`."""
    return f"uf_{str(ULID()).lower()}"


def new_pantry_item_id() -> str:
    """Return `pi_<26-char ulid lowercase>`."""
    return f"pi_{str(ULID()).lower()}"


def synth_observed_barcode_for_user_food(user_food_id: str) -> str:
    """Synthesize an observed_barcode for a user-food-backed measurement.

    Format: `uf-<last 12 chars of the ulid>`. 15 chars total. Always satisfies
    the existing check `^[0-9A-Za-z-]{4,32}$` on `measurements.observed_barcode`
    because ULIDs use Crockford base32 (alphanumeric, no dashes).

    The collision risk is dominated by the 12-char suffix of a ULID, which is
    monotonic per millisecond per device — astronomically unlikely. A unique
    constraint on (device_id, observed_barcode) on `measurements` would be a
    follow-up safety net but is not required for MVP-5a.
    """
    if not user_food_id.startswith("uf_"):
        raise ValueError(f"expected uf_-prefixed user_food_id, got {user_food_id!r}")
    return f"uf-{user_food_id[-12:]}"
