"""Pure functions for voice intent matching.

No DB, no network. Given a transcript and a list of pantry titles,
return the best match (or None) and an extracted weight.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from rapidfuzz import fuzz

# Items below this score are not surfaced as a match. Empirically:
# - exact title or transcript-contains-title matches at >= 95
# - "I had some bananas" vs "Banana" partial-matches at ~95
# - random Swedish words rarely cross 50
_DEFAULT_THRESHOLD = 70

# Match a positive integer or decimal followed by a gram suffix.
# Greedy on the unit suffix (.../grams|gram|gr|g\b/), case-insensitive.
_WEIGHT_RE = re.compile(
    r"\b(\d{1,4}(?:\.\d{1,2})?)\s*(?:grams|gram|gr|g)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Candidate:
    """A pantry-item match for a voice utterance."""

    pantry_item_id: str
    name: str
    weight_grams: Decimal
    confidence: float  # 0.0-1.0


def extract_weight_grams(transcript: str) -> Decimal | None:
    """Pull a weight in grams out of the transcript. None if no match."""
    m = _WEIGHT_RE.search(transcript)
    if not m:
        return None
    return Decimal(m.group(1))


def best_match(
    transcript: str,
    candidates: list[tuple[str, str, Decimal | None]],
    *,
    threshold: int = _DEFAULT_THRESHOLD,
    final_fallback_weight_g: Decimal = Decimal("100"),
) -> Candidate | None:
    """Pick the best pantry item for a transcript, or None if no item passes the threshold.

    Args:
        transcript: lowercased + stripped speech transcription.
        candidates: list of (pantry_item_id, title, default_serving_g) tuples.
        threshold: minimum partial_ratio score (0-100) required to return a match.
        final_fallback_weight_g: used when neither the transcript nor the
            pantry item supplies a weight.

    Returns the best [Candidate] above [threshold], or None.
    """
    transcript = transcript.strip().lower()
    if not transcript or not candidates:
        return None

    best_id, best_title, best_default, best_score = None, None, None, -1.0
    for pid, title, default_g in candidates:
        score = fuzz.partial_ratio(transcript, title.lower())
        if score > best_score:
            best_id, best_title, best_default, best_score = pid, title, default_g, score

    if best_score < threshold or best_id is None or best_title is None:
        return None

    weight = extract_weight_grams(transcript) or best_default or final_fallback_weight_g
    return Candidate(
        pantry_item_id=best_id,
        name=best_title,
        weight_grams=weight,
        confidence=round(best_score / 100.0, 3),
    )
