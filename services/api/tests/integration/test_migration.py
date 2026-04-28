"""Smoke test the schema migration."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def test_three_tables_exist(db_session: AsyncSession) -> None:
    rows = (
        (
            await db_session.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' ORDER BY table_name"
                )
            )
        )
        .scalars()
        .all()
    )
    assert {"products", "measurements", "scrape_jobs"}.issubset(set(rows))


async def test_unresolved_index_is_partial(db_session: AsyncSession) -> None:
    row = (
        await db_session.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname='measurements_unresolved_idx'")
        )
    ).scalar_one()
    assert "WHERE" in row
    assert "product_barcode IS NULL" in row


async def test_macros_within_100g_check_rejects(db_session: AsyncSession) -> None:
    with pytest.raises(Exception, match="products_macros_within_100g"):
        await db_session.execute(
            text(
                "INSERT INTO products(barcode, name, kcal_per_100g, "
                "protein_g_per_100g, carbs_g_per_100g, fat_g_per_100g) "
                "VALUES ('1234567890', 'bad', 0, 50, 50, 50)"
            )
        )
        await db_session.commit()
