"""GET /v1/products/{barcode}."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


BARCODE = "7311070016010"
UNKNOWN = "9999999999999"


async def _seed_oat_milk(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO products (barcode, name, brand, source, source_url, "
            "kcal_per_100g, protein_g_per_100g, carbs_g_per_100g, fat_g_per_100g, "
            "fiber_g_per_100g) "
            "VALUES (:barcode, 'Havremjölk', 'Oatly', 'openfoodfacts', "
            "'https://world.openfoodfacts.org/product/7311070016010', "
            "46, 1.0, 6.7, 1.5, 0.8)"
        ),
        {"barcode": BARCODE},
    )
    await db_session.commit()


async def test_get_existing_product_returns_200(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_oat_milk(db_session)

    resp = await client.get(f"/v1/products/{BARCODE}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["barcode"] == BARCODE
    assert body["name"] == "Havremjölk"
    assert body["brand"] == "Oatly"
    assert body["source"] == "openfoodfacts"
    assert body["source_url"] == "https://world.openfoodfacts.org/product/7311070016010"


async def test_get_existing_product_includes_per_100g_macros(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_oat_milk(db_session)

    resp = await client.get(f"/v1/products/{BARCODE}")

    assert resp.status_code == 200
    per_100g = resp.json()["per_100g"]
    assert Decimal(per_100g["kcal"]) == Decimal("46")
    assert Decimal(per_100g["protein_g"]) == Decimal("1.0")
    assert Decimal(per_100g["carbs_g"]) == Decimal("6.7")
    assert Decimal(per_100g["fat_g"]) == Decimal("1.5")
    assert Decimal(per_100g["fiber_g"]) == Decimal("0.8")


async def test_get_unknown_product_returns_404(client: AsyncClient) -> None:
    resp = await client.get(f"/v1/products/{UNKNOWN}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "product not found"


async def test_get_invalid_barcode_returns_422(client: AsyncClient) -> None:
    resp = await client.get("/v1/products/abc")  # too short (<4 chars)
    assert resp.status_code == 422


async def test_get_special_chars_in_barcode_rejected(client: AsyncClient) -> None:
    resp = await client.get("/v1/products/foo$bar")
    assert resp.status_code == 422


async def test_get_requires_device_key(app: FastAPI) -> None:
    """Confirm GET inherits the DeviceKey middleware (no header → 401)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get(f"/v1/products/{BARCODE}")
    assert resp.status_code == 401
