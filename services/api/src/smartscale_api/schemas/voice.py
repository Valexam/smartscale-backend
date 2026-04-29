"""Pydantic models for /v1/voice/*."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class VoiceCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pantry_item_id: str
    name: str
    weight_grams: Decimal
    confidence: float


class VoiceMatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transcript: str
    language: str | None = None
    candidate: VoiceCandidate | None = None
