"""Pydantic models for /v1/measurements."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Barcode = Annotated[str, StringConstraints(pattern=r"^[0-9A-Za-z\-]{4,32}$")]
DeviceId = Annotated[str, StringConstraints(min_length=1, max_length=64)]
Note = Annotated[str, StringConstraints(max_length=256)]


class MeasurementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed_barcode: Barcode
    weight_grams: Annotated[Decimal, Field(gt=0)]
    measured_at: datetime
    device_id: DeviceId
    note: Note | None = None


class Per100gOut(BaseModel):
    kcal: Decimal
    protein_g: Decimal
    carbs_g: Decimal
    fat_g: Decimal
    fiber_g: Decimal | None = None


class ProductOut(BaseModel):
    barcode: str
    name: str
    brand: str | None = None
    per_100g: Per100gOut


class ComputedOut(BaseModel):
    kcal: Decimal
    protein_g: Decimal
    carbs_g: Decimal
    fat_g: Decimal


class MeasurementResponse(BaseModel):
    id: str
    observed_barcode: str
    product_barcode: str | None
    weight_grams: Decimal
    measured_at: datetime
    device_id: str
    note: str | None
    product: ProductOut | None
    computed: ComputedOut | None
    server_received_at: datetime


class MeasurementListResponse(BaseModel):
    items: list[MeasurementResponse]
    limit: int
    offset: int
