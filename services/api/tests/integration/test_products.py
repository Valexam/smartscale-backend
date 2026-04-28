"""PUT /v1/products/{barcode}."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


BARCODE = "7311070016010"


def _put_body() -> dict[str, Any]:
    return {
        "name": "Havremjölk",
        "brand": "Oatly",
        "per_100g": {
            "kcal": "46",
            "protein_g": "1.0",
            "carbs_g": "6.7",
            "fat_g": "1.5",
            "fiber_g": "0.8",
        },
    }


async def test_create_new_product_no_measurements_returns_201(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resp = await client.put(f"/v1/products/{BARCODE}", json=_put_body())
    assert resp.status_code == 201
    body = resp.json()
    assert body["product"]["name"] == "Havremjölk"
    assert body["measurements_backfilled"] == 0


async def test_create_with_unresolved_measurements_backfills(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Three unresolved measurements at varying weights
    for weight in ("100", "142.7", "200"):
        resp = await client.post(
            "/v1/measurements",
            json={
                "observed_barcode": BARCODE,
                "weight_grams": weight,
                "measured_at": "2026-04-27T10:14:08Z",
                "device_id": "scale-abc",
            },
        )
        assert resp.status_code == 202

    resp = await client.put(f"/v1/products/{BARCODE}", json=_put_body())
    assert resp.status_code == 201
    assert resp.json()["measurements_backfilled"] == 3

    # And spot-check that the 142.7 g row got the right macros
    row = (
        await db_session.execute(
            text(
                "SELECT computed_kcal, product_barcode FROM measurements WHERE weight_grams = 142.7"
            )
        )
    ).one()
    assert Decimal(row[0]) == Decimal("65.642")
    assert row[1] == BARCODE


async def test_reput_returns_200_and_updates_name(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.put(f"/v1/products/{BARCODE}", json=_put_body())
    body = _put_body()
    body["name"] = "Havremjölk Original"
    resp = await client.put(f"/v1/products/{BARCODE}", json=body)
    assert resp.status_code == 200
    assert resp.json()["product"]["name"] == "Havremjölk Original"


async def test_reput_does_not_touch_frozen_rows(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Create the product first so the measurement is frozen on insert.
    await client.put(f"/v1/products/{BARCODE}", json=_put_body())
    await client.post(
        "/v1/measurements",
        json={
            "observed_barcode": BARCODE,
            "weight_grams": "100",
            "measured_at": "2026-04-27T10:14:08Z",
            "device_id": "scale-abc",
        },
    )
    # Re-PUT with very different macros
    new_body = _put_body()
    new_body["per_100g"]["kcal"] = "1000"
    resp = await client.put(f"/v1/products/{BARCODE}", json=new_body)
    assert resp.status_code == 200
    assert resp.json()["measurements_backfilled"] == 0  # already-frozen row not touched

    kcal = (
        await db_session.execute(
            text("SELECT computed_kcal FROM measurements WHERE weight_grams = 100")
        )
    ).scalar_one()
    assert Decimal(kcal) == Decimal("46.0")  # original 46 kcal/100g, not 1000


async def test_scrape_job_closes_on_user_submission(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post(
        "/v1/measurements",
        json={
            "observed_barcode": BARCODE,
            "weight_grams": "100",
            "measured_at": "2026-04-27T10:14:08Z",
            "device_id": "scale-abc",
        },
    )
    await client.put(f"/v1/products/{BARCODE}", json=_put_body())

    status_value = (
        await db_session.execute(
            text("SELECT status FROM scrape_jobs WHERE barcode = :b"), {"b": BARCODE}
        )
    ).scalar_one()
    assert status_value == "completed_by_user"


async def test_macros_over_100g_rejected(client: AsyncClient) -> None:
    body = _put_body()
    body["per_100g"]["protein_g"] = "60"
    body["per_100g"]["carbs_g"] = "30"
    body["per_100g"]["fat_g"] = "30"  # 60 + 30 + 30 = 120 > 100
    resp = await client.put(f"/v1/products/{BARCODE}", json=body)
    assert resp.status_code == 422
