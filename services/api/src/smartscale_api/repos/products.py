"""Product I/O."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from smartscale_api.repos.models import Product


async def get_by_barcode(session: AsyncSession, barcode: str) -> Product | None:
    return (
        await session.execute(select(Product).where(Product.barcode == barcode))
    ).scalar_one_or_none()


async def upsert(
    session: AsyncSession,
    *,
    barcode: str,
    name: str,
    brand: str | None,
    kcal: Decimal,
    protein_g: Decimal,
    carbs_g: Decimal,
    fat_g: Decimal,
    fiber_g: Decimal | None,
    source: str = "user",
    source_url: str | None = None,
    raw_payload: dict[str, Any] | None = None,
) -> tuple[Product, bool]:
    """Insert or replace; return (product, created_flag).

    Uses a SELECT-before-upsert pattern to reliably detect INSERT vs UPDATE.
    The xmax trick was avoided due to SQLAlchemy 2.x multi-column .returning()
    typing friction when mixing ORM-mapped columns with raw SQL expressions.
    """
    existing = await get_by_barcode(session, barcode)
    created = existing is None
    # Expire the cached instance so SQLAlchemy uses the RETURNING data, not the
    # stale identity-map copy, when the on_conflict_do_update fires.
    if existing is not None:
        session.expire(existing)

    now = datetime.now(UTC)
    stmt = (
        pg_insert(Product)
        .values(
            barcode=barcode,
            name=name,
            brand=brand,
            source=source,
            source_url=source_url,
            raw_payload=raw_payload,
            kcal_per_100g=kcal,
            protein_g_per_100g=protein_g,
            carbs_g_per_100g=carbs_g,
            fat_g_per_100g=fat_g,
            fiber_g_per_100g=fiber_g,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["barcode"],
            set_={
                "name": name,
                "brand": brand,
                "source": source,
                "source_url": source_url,
                "raw_payload": raw_payload,
                "kcal_per_100g": kcal,
                "protein_g_per_100g": protein_g,
                "carbs_g_per_100g": carbs_g,
                "fat_g_per_100g": fat_g,
                "fiber_g_per_100g": fiber_g,
                "updated_at": now,
            },
        )
        .returning(Product)
    )
    product = (await session.execute(stmt)).scalar_one()
    return product, created


async def backfill_measurements(
    session: AsyncSession,
    *,
    barcode: str,
    kcal: Decimal,
    protein_g: Decimal,
    carbs_g: Decimal,
    fat_g: Decimal,
) -> int:
    """Resolve unresolved measurements for this barcode. Returns rows updated."""
    raw: Any = await session.execute(
        text(
            """
            UPDATE measurements
               SET product_barcode    = :barcode,
                   computed_kcal      = weight_grams * :kcal      / 100,
                   computed_protein_g = weight_grams * :protein_g / 100,
                   computed_carbs_g   = weight_grams * :carbs_g   / 100,
                   computed_fat_g     = weight_grams * :fat_g     / 100
             WHERE observed_barcode = :barcode
               AND product_barcode  IS NULL
            """
        ),
        {
            "barcode": barcode,
            "kcal": kcal,
            "protein_g": protein_g,
            "carbs_g": carbs_g,
            "fat_g": fat_g,
        },
    )
    return int(raw.rowcount) if raw.rowcount else 0
