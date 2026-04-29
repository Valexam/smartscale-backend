"""Measurement I/O."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smartscale_api.repos.models import Measurement


async def list_paginated(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
    device_id: str | None = None,
) -> list[Measurement]:
    """List measurements ordered by measured_at desc, paginated, optionally filtered."""
    stmt = select(Measurement)
    if device_id:
        stmt = stmt.where(Measurement.device_id == device_id)
    stmt = stmt.order_by(Measurement.measured_at.desc(), Measurement.id).limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())


async def insert(
    session: AsyncSession,
    *,
    measurement_id: str,
    device_id: str,
    observed_barcode: str,
    product_barcode: str | None,
    weight_grams: Decimal,
    measured_at: datetime,
    computed_kcal: Decimal | None,
    computed_protein_g: Decimal | None,
    computed_carbs_g: Decimal | None,
    computed_fat_g: Decimal | None,
    note: str | None,
) -> Measurement:
    row = Measurement(
        id=measurement_id,
        device_id=device_id,
        observed_barcode=observed_barcode,
        product_barcode=product_barcode,
        weight_grams=weight_grams,
        measured_at=measured_at,
        computed_kcal=computed_kcal,
        computed_protein_g=computed_protein_g,
        computed_carbs_g=computed_carbs_g,
        computed_fat_g=computed_fat_g,
        note=note,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row, ["server_received_at"])
    return row
