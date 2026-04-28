"""Contract tests: requests built from fixtures, responses match fixtures."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures import load, strip_dynamic

pytestmark = [pytest.mark.integration, pytest.mark.contract]


async def _seed_oat_milk(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO products (barcode, name, brand, source, "
            "kcal_per_100g, protein_g_per_100g, carbs_g_per_100g, fat_g_per_100g, "
            "fiber_g_per_100g) "
            "VALUES ('7311070016010', 'Havremjölk', 'Oatly', 'user', "
            "46, 1.0, 6.7, 1.5, 0.8)"
        )
    )
    await db_session.commit()


async def test_measurement_known_contract(client: AsyncClient, db_session: AsyncSession) -> None:
    await _seed_oat_milk(db_session)
    req = load("measurement_known_request.json")
    expected = load("measurement_known_response_201.json")
    resp = await client.post("/v1/measurements", json=req)
    assert resp.status_code == 201
    assert strip_dynamic(resp.json()) == expected


async def test_measurement_unknown_contract(client: AsyncClient) -> None:
    req = load("measurement_unknown_request.json")
    expected = load("measurement_unknown_response_202.json")
    resp = await client.post("/v1/measurements", json=req)
    assert resp.status_code == 202
    assert strip_dynamic(resp.json()) == expected


async def test_product_put_create_contract(client: AsyncClient) -> None:
    req = load("product_put_request.json")
    expected = load("product_put_response_201.json")
    resp = await client.put("/v1/products/7311070016010", json=req)
    assert resp.status_code == 201
    assert resp.json() == expected


async def test_invalid_device_key_contract(app: FastAPI) -> None:
    from httpx import ASGITransport
    from httpx import AsyncClient as Raw

    expected = load("error_invalid_device_key.json")
    async with Raw(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"x-device-key": "wrong"},
    ) as c:
        resp = await c.put("/v1/products/7311070016010", json=load("product_put_request.json"))
    assert resp.status_code == 401
    assert resp.json() == expected
