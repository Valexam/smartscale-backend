"""ULID-based IDs and synthesized observed_barcode for user-food logs."""

from __future__ import annotations

import re

import pytest

from smartscale_api.ids import (
    new_measurement_id,
    new_pantry_item_id,
    new_user_food_id,
    synth_observed_barcode_for_user_food,
)

MEASUREMENT_PATTERN = re.compile(r"^mea_[0-9a-z]{26}$")
USER_FOOD_PATTERN = re.compile(r"^uf_[0-9a-z]{26}$")
PANTRY_ITEM_PATTERN = re.compile(r"^pi_[0-9a-z]{26}$")

# Mirrors the existing CHECK on measurements.observed_barcode.
OBSERVED_BARCODE_RE = re.compile(r"^[0-9A-Za-z\-]{4,32}$")


def test_measurement_id_format() -> None:
    assert MEASUREMENT_PATTERN.match(new_measurement_id())


def test_measurement_id_uniqueness() -> None:
    ids = {new_measurement_id() for _ in range(1000)}
    assert len(ids) == 1000


def test_user_food_id_format() -> None:
    assert USER_FOOD_PATTERN.match(new_user_food_id())


def test_pantry_item_id_format() -> None:
    assert PANTRY_ITEM_PATTERN.match(new_pantry_item_id())


def test_ids_uniqueness_across_kinds() -> None:
    ufs = {new_user_food_id() for _ in range(100)}
    pis = {new_pantry_item_id() for _ in range(100)}
    assert len(ufs) == 100
    assert len(pis) == 100
    # Different prefixes guarantee no overlap
    assert ufs.isdisjoint(pis)


def test_synth_barcode_satisfies_observed_barcode_check() -> None:
    """Synthesized barcodes must match the existing CHECK constraint."""
    for _ in range(50):
        uid = new_user_food_id()
        bc = synth_observed_barcode_for_user_food(uid)
        assert OBSERVED_BARCODE_RE.match(bc), bc


def test_synth_barcode_starts_with_uf_dash() -> None:
    bc = synth_observed_barcode_for_user_food(new_user_food_id())
    assert bc.startswith("uf-")
    assert len(bc) == 15  # "uf-" (3) + 12-char suffix


def test_synth_barcode_uses_last_12_chars_of_ulid() -> None:
    uid = "uf_01jr3y5abcdef0123456789xy"
    bc = synth_observed_barcode_for_user_food(uid)
    assert bc == "uf-" + uid[-12:]


def test_synth_barcode_rejects_wrong_prefix() -> None:
    with pytest.raises(ValueError, match="uf_-prefixed"):
        synth_observed_barcode_for_user_food("pi_01jr3y5abcdef0123456789xy")
    with pytest.raises(ValueError):
        synth_observed_barcode_for_user_food("01jr3y5abcdef0123456789xy")


def test_synth_barcode_is_deterministic() -> None:
    uid = new_user_food_id()
    assert synth_observed_barcode_for_user_food(uid) == synth_observed_barcode_for_user_food(uid)
