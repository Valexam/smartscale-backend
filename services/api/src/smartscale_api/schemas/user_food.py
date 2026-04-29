"""Pydantic models for /v1/user-foods."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from smartscale_api.schemas.product import Per100gIn

DeviceId = Annotated[str, StringConstraints(min_length=1, max_length=64)]
FoodName = Annotated[str, StringConstraints(min_length=1, max_length=200)]
Brand = Annotated[str, StringConstraints(max_length=200)]


class UserFoodCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: DeviceId
    name: FoodName
    brand: Brand | None = None
    per_100g: Per100gIn
    default_serving_g: Annotated[Decimal, Field(gt=0)] | None = None


class UserFoodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    device_id: str
    name: str
    brand: str | None
    per_100g: Per100gIn
    default_serving_g: Decimal | None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _from_orm(cls, value: object) -> object:
        """Project flat ORM columns into the nested per_100g shape on input."""
        if isinstance(value, dict):
            return value
        # SQLAlchemy ORM instance: synthesize the nested per_100g dict.
        return {
            "id": value.id,  # type: ignore[attr-defined]
            "device_id": value.device_id,  # type: ignore[attr-defined]
            "name": value.name,  # type: ignore[attr-defined]
            "brand": value.brand,  # type: ignore[attr-defined]
            "per_100g": Per100gIn(
                kcal=value.kcal_per_100g,  # type: ignore[attr-defined]
                protein_g=value.protein_g_per_100g,  # type: ignore[attr-defined]
                carbs_g=value.carbs_g_per_100g,  # type: ignore[attr-defined]
                fat_g=value.fat_g_per_100g,  # type: ignore[attr-defined]
                fiber_g=value.fiber_g_per_100g,  # type: ignore[attr-defined]
            ),
            "default_serving_g": value.default_serving_g,  # type: ignore[attr-defined]
            "created_at": value.created_at,  # type: ignore[attr-defined]
            "updated_at": value.updated_at,  # type: ignore[attr-defined]
        }
