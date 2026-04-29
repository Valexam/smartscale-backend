"""Pure-function tests for voice intent matching."""

from __future__ import annotations

from decimal import Decimal

import pytest

from smartscale_api.domain.voice_match import best_match, extract_weight_grams

# ---------- weight extraction ----------


@pytest.mark.parametrize(
    ("transcript", "expected"),
    [
        ("log 200g of banana", Decimal("200")),
        ("log 200 g of banana", Decimal("200")),
        ("log 200 grams of banana", Decimal("200")),
        ("log 200gr of banana", Decimal("200")),
        ("log 200gram of banana", Decimal("200")),
        ("ate 12.5g of nuts", Decimal("12.5")),
        ("ate 12.50 g of nuts", Decimal("12.50")),
        ("upper case 50G of banana", Decimal("50")),
    ],
)
def test_extract_weight_hits(transcript: str, expected: Decimal) -> None:
    assert extract_weight_grams(transcript) == expected


@pytest.mark.parametrize(
    "transcript",
    [
        "log a banana",
        "ate two apples",
        "ate 200 kilograms of nuts",  # 'kg' not in regex
        "code 200ghz of cpu",  # 'ghz' is not 'g\b'
        "",
        "200",
        "g",
    ],
)
def test_extract_weight_misses(transcript: str) -> None:
    assert extract_weight_grams(transcript) is None


# ---------- match ranking ----------


def _cands() -> list[tuple[str, str, Decimal | None]]:
    return [
        ("pi_banana", "Banana", Decimal("118")),
        ("pi_oat", "Havremjölk", Decimal("250")),
        ("pi_egg", "Boiled eggs", Decimal("50")),
    ]


def test_exact_match() -> None:
    m = best_match("banana", _cands())
    assert m is not None
    assert m.pantry_item_id == "pi_banana"
    assert m.confidence >= 0.99
    # No weight in transcript → falls back to default_serving_g (118)
    assert m.weight_grams == Decimal("118")


def test_substring_match_with_extra_words() -> None:
    m = best_match("log a banana please", _cands())
    assert m is not None
    assert m.pantry_item_id == "pi_banana"


def test_match_uses_extracted_weight_over_default_serving() -> None:
    m = best_match("ate 200 g of banana", _cands())
    assert m is not None
    assert m.pantry_item_id == "pi_banana"
    assert m.weight_grams == Decimal("200")


def test_match_falls_back_to_100g_when_no_weight_and_no_default() -> None:
    cands: list[tuple[str, str, Decimal | None]] = [("pi_x", "Apple", None)]
    m = best_match("ate apple", cands)
    assert m is not None
    assert m.weight_grams == Decimal("100")


def test_no_match_returns_none() -> None:
    m = best_match("zebra giraffe quasar", _cands())
    assert m is None


def test_empty_transcript_returns_none() -> None:
    assert best_match("", _cands()) is None
    assert best_match("   ", _cands()) is None


def test_empty_pantry_returns_none() -> None:
    assert best_match("anything", []) is None


def test_threshold_can_be_tuned() -> None:
    # "milk" partial-matches Havremjölk weakly (~50). Default threshold (70)
    # rejects; threshold=50 accepts.
    cands = _cands()
    assert best_match("milk", cands) is None
    relaxed = best_match("milk", cands, threshold=40)
    assert relaxed is not None
    assert relaxed.pantry_item_id == "pi_oat"


def test_swedish_match_case_insensitive() -> None:
    m = best_match("HAVREMJÖLK", _cands())
    assert m is not None
    assert m.pantry_item_id == "pi_oat"
    assert m.confidence >= 0.99


def test_confidence_is_score_over_100() -> None:
    m = best_match("banana", _cands())
    assert m is not None
    assert 0.0 <= m.confidence <= 1.0
