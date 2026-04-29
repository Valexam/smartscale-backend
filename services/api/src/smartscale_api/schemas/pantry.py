"""Pydantic models for /v1/pantry."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from smartscale_api.schemas.product import Per100gIn

DeviceId = Annotated[str, StringConstraints(min_length=1, max_length=64)]
Barcode = Annotated[str, StringConstraints(pattern=r"^[0-9A-Za-z\-]{4,32}$")]
UserFoodId = Annotated[str, StringConstraints(pattern=r"^uf_[0-9a-z]{26}$")]
PantryItemId = Annotated[str, StringConstraints(pattern=r"^pi_[0-9a-z]{26}$")]
Note = Annotated[str, StringConstraints(max_length=256)]


class PantryAddCustom(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    brand: Annotated[str, StringConstraints(max_length=200)] | None = None
    per_100g: Per100gIn
    default_serving_g: Annotated[Decimal, Field(gt=0)] | None = None


class PantryAddRequest(BaseModel):
    """Add to pantry. Exactly one of barcode / user_food_id / custom."""

    model_config = ConfigDict(extra="forbid")

    device_id: DeviceId
    barcode: Barcode | None = None
    user_food_id: UserFoodId | None = None
    custom: PantryAddCustom | None = None
    default_serving_g: Annotated[Decimal, Field(gt=0)] | None = None

    @model_validator(mode="after")
    def exactly_one_source(self) -> PantryAddRequest:
        n = sum(x is not None for x in (self.barcode, self.user_food_id, self.custom))
        if n != 1:
            raise ValueError("exactly one of `barcode`, `user_food_id`, `custom` must be provided")
        return self


class PantryItemOut(BaseModel):
    """Pantry list / add response. Joined with the source so name/macros are present."""

    model_config = ConfigDict(extra="forbid")

    id: str
    source: Literal["product", "user_food"]
    barcode: str | None
    user_food_id: str | None
    name: str
    brand: str | None
    per_100g: Per100gIn
    default_serving_g: Decimal | None
    added_at: datetime
    last_used_at: datetime | None


class PantryListResponse(BaseModel):
    items: list[PantryItemOut]
    limit: int
    offset: int


class PantryLogRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: DeviceId
    weight_grams: Annotated[Decimal, Field(gt=0)]
    measured_at: datetime
    note: Note | None = None
