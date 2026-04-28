"""Pydantic validators."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from smartscale_api.schemas.measurement import MeasurementRequest


def _valid_payload() -> dict[str, Any]:
    return {
        "observed_barcode": "7311070016010",
        "weight_grams": "142.7",
        "measured_at": "2026-04-27T10:14:08Z",
        "device_id": "scale-abc123",
        "note": "half portion",
    }


def test_valid() -> None:
    m = MeasurementRequest(**_valid_payload())
    assert m.weight_grams == Decimal("142.7")
    assert m.observed_barcode == "7311070016010"


def test_negative_weight_rejected() -> None:
    p = _valid_payload()
    p["weight_grams"] = "-1"
    with pytest.raises(ValidationError):
        MeasurementRequest(**p)


def test_zero_weight_rejected() -> None:
    p = _valid_payload()
    p["weight_grams"] = "0"
    with pytest.raises(ValidationError):
        MeasurementRequest(**p)


def test_short_barcode_rejected() -> None:
    p = _valid_payload()
    p["observed_barcode"] = "abc"
    with pytest.raises(ValidationError):
        MeasurementRequest(**p)


def test_long_barcode_rejected() -> None:
    p = _valid_payload()
    p["observed_barcode"] = "x" * 33
    with pytest.raises(ValidationError):
        MeasurementRequest(**p)


def test_special_chars_in_barcode_rejected() -> None:
    p = _valid_payload()
    p["observed_barcode"] = "7311 0700"
    with pytest.raises(ValidationError):
        MeasurementRequest(**p)
