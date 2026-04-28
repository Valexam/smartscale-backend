"""Macro arithmetic. Pure; uses Decimal end-to-end.

No rounding is applied here — output Decimals carry the full precision of
``weight_grams * (per_100g / 100)``. Callers (the Pydantic response layer or
the DB column) are responsible for quantizing to whatever precision they need
at the I/O boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Per100g:
    kcal: Decimal
    protein_g: Decimal
    carbs_g: Decimal
    fat_g: Decimal


@dataclass(frozen=True)
class Computed:
    kcal: Decimal
    protein_g: Decimal
    carbs_g: Decimal
    fat_g: Decimal


def compute_macros(weight_grams: Decimal, per_100g: Per100g) -> Computed:
    if weight_grams <= 0:
        raise ValueError("weight_grams must be > 0")
    factor = weight_grams / Decimal(100)
    return Computed(
        kcal=per_100g.kcal * factor,
        protein_g=per_100g.protein_g * factor,
        carbs_g=per_100g.carbs_g * factor,
        fat_g=per_100g.fat_g * factor,
    )
