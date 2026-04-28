"""POST /v1/measurements."""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


KNOWN = "7311070016010"
UNKNOWN = "9999999999999"


async def _seed_oat_milk(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO products (barcode, name, brand, source, "
            "kcal_per_100g, protein_g_per_100g, carbs_g_per_100g, fat_g_per_100g, "
            "fiber_g_per_100g) "
            "VALUES (:barcode, 'Havremjölk', 'Oatly', 'user', 46, 1.0, 6.7, 1.5, 0.8)"
        ),
        {"barcode": KNOWN},
    )
    await db_session.commit()


async def test_known_product_returns_201_with_computed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_oat_milk(db_session)
    resp = await client.post(
        "/v1/measurements",
        json={
            "observed_barcode": KNOWN,
            "weight_grams": "142.7",
            "measured_at": "2026-04-27T10:14:08Z",
            "device_id": "scale-abc123",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["product"]["name"] == "Havremjölk"
    assert Decimal(body["computed"]["kcal"]) == Decimal("65.642")
    assert body["product_barcode"] == KNOWN


async def test_unknown_product_returns_202_and_queues_scrape_job(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resp = await client.post(
        "/v1/measurements",
        json={
            "observed_barcode": UNKNOWN,
            "weight_grams": "100",
            "measured_at": "2026-04-27T10:14:08Z",
            "device_id": "scale-abc123",
        },
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["product"] is None
    assert body["computed"] is None
    assert body["product_barcode"] is None

    job_status = (
        await db_session.execute(
            text("SELECT status FROM scrape_jobs WHERE barcode = :b"), {"b": UNKNOWN}
        )
    ).scalar_one()
    assert job_status == "queued"


async def test_repeat_unknown_does_not_duplicate_scrape_job(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    payload = {
        "observed_barcode": UNKNOWN,
        "weight_grams": "100",
        "measured_at": "2026-04-27T10:14:08Z",
        "device_id": "scale-abc123",
    }
    await client.post("/v1/measurements", json=payload)
    await client.post("/v1/measurements", json=payload)
    count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM scrape_jobs WHERE barcode = :b"), {"b": UNKNOWN}
        )
    ).scalar_one()
    assert count == 1


async def test_invalid_weight_returns_422(client: AsyncClient) -> None:
    resp = await client.post(
        "/v1/measurements",
        json={
            "observed_barcode": KNOWN,
            "weight_grams": "0",
            "measured_at": "2026-04-27T10:14:08Z",
            "device_id": "scale-abc123",
        },
    )
    assert resp.status_code == 422
