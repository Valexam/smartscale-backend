"""GET /v1/measurements (paginated list)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
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


async def _post_measurement(
    client: AsyncClient,
    *,
    barcode: str,
    weight: str,
    measured_at: datetime,
    device_id: str = "scale-abc",
) -> None:
    resp = await client.post(
        "/v1/measurements",
        json={
            "observed_barcode": barcode,
            "weight_grams": weight,
            "measured_at": measured_at.isoformat().replace("+00:00", "Z"),
            "device_id": device_id,
        },
    )
    assert resp.status_code in (201, 202)


async def test_empty_list_returns_200_with_zero_items(client: AsyncClient) -> None:
    resp = await client.get("/v1/measurements")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"items": [], "limit": 20, "offset": 0}


async def test_list_returns_measurements_ordered_by_measured_at_desc(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    base = datetime(2026, 4, 27, 10, 0, 0, tzinfo=UTC)
    await _post_measurement(client, barcode=UNKNOWN, weight="100", measured_at=base)
    await _post_measurement(
        client, barcode=UNKNOWN, weight="200", measured_at=base + timedelta(hours=1)
    )
    await _post_measurement(
        client, barcode=UNKNOWN, weight="300", measured_at=base + timedelta(hours=2)
    )

    resp = await client.get("/v1/measurements")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 3
    weights = [item["weight_grams"] for item in items]
    assert weights == ["300", "200", "100"]  # most-recent first


async def test_list_respects_limit(client: AsyncClient, db_session: AsyncSession) -> None:
    base = datetime(2026, 4, 27, 10, 0, 0, tzinfo=UTC)
    for i in range(5):
        await _post_measurement(
            client, barcode=UNKNOWN, weight=str(100 + i), measured_at=base + timedelta(hours=i)
        )
    resp = await client.get("/v1/measurements?limit=2")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["limit"] == 2


async def test_list_respects_offset(client: AsyncClient, db_session: AsyncSession) -> None:
    base = datetime(2026, 4, 27, 10, 0, 0, tzinfo=UTC)
    for i in range(5):
        await _post_measurement(
            client, barcode=UNKNOWN, weight=str(100 + i), measured_at=base + timedelta(hours=i)
        )
    resp = await client.get("/v1/measurements?limit=2&offset=2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["offset"] == 2
    # Sorted desc by measured_at: the third-most-recent has weight 102
    weights = [item["weight_grams"] for item in body["items"]]
    assert weights == ["102", "101"]


async def test_list_limit_clamped_to_100(client: AsyncClient) -> None:
    resp = await client.get("/v1/measurements?limit=999")
    assert resp.status_code == 422


async def test_list_limit_below_one_rejected(client: AsyncClient) -> None:
    resp = await client.get("/v1/measurements?limit=0")
    assert resp.status_code == 422


async def test_list_filters_by_device_id(client: AsyncClient, db_session: AsyncSession) -> None:
    base = datetime(2026, 4, 27, 10, 0, 0, tzinfo=UTC)
    await _post_measurement(
        client, barcode=UNKNOWN, weight="100", measured_at=base, device_id="scale-A"
    )
    await _post_measurement(
        client,
        barcode=UNKNOWN,
        weight="200",
        measured_at=base + timedelta(hours=1),
        device_id="scale-B",
    )
    resp = await client.get("/v1/measurements?device_id=scale-A")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["device_id"] == "scale-A"


async def test_list_embeds_product_for_resolved_measurements(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_oat_milk(db_session)
    base = datetime(2026, 4, 27, 10, 0, 0, tzinfo=UTC)
    await _post_measurement(client, barcode=KNOWN, weight="100", measured_at=base)
    await _post_measurement(
        client, barcode=UNKNOWN, weight="200", measured_at=base + timedelta(hours=1)
    )

    resp = await client.get("/v1/measurements")
    items = resp.json()["items"]
    by_barcode = {item["observed_barcode"]: item for item in items}
    assert by_barcode[KNOWN]["product"] is not None
    assert by_barcode[KNOWN]["product"]["name"] == "Havremjölk"
    assert by_barcode[KNOWN]["computed"] is not None
    assert by_barcode[UNKNOWN]["product"] is None
    assert by_barcode[UNKNOWN]["computed"] is None


async def test_list_requires_device_key(app: FastAPI) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/v1/measurements")
    assert resp.status_code == 401
