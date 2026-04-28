"""Pydantic models for /v1/products/{barcode}."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


class Per100gIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kcal: Annotated[Decimal, Field(ge=0)]
    protein_g: Annotated[Decimal, Field(ge=0)]
    carbs_g: Annotated[Decimal, Field(ge=0)]
    fat_g: Annotated[Decimal, Field(ge=0)]
    fiber_g: Annotated[Decimal, Field(ge=0)] | None = None

    @model_validator(mode="after")
    def macros_within_100g(self) -> Per100gIn:
        if self.protein_g + self.carbs_g + self.fat_g > Decimal(100):
            raise ValueError("protein_g + carbs_g + fat_g must not exceed 100")
        return self


class ProductPutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    brand: Annotated[str, StringConstraints(max_length=200)] | None = None
    per_100g: Per100gIn


class ProductPutResponseProduct(BaseModel):
    barcode: str
    name: str
    brand: str | None
    per_100g: Per100gIn


class ProductPutResponse(BaseModel):
    product: ProductPutResponseProduct
    measurements_backfilled: int
