"""ULID-based measurement IDs."""

from __future__ import annotations

import re

from smartscale_api.ids import new_measurement_id

PATTERN = re.compile(r"^mea_[0-9a-z]{26}$")


def test_format() -> None:
    assert PATTERN.match(new_measurement_id())


def test_uniqueness() -> None:
    ids = {new_measurement_id() for _ in range(1000)}
    assert len(ids) == 1000
