"""POST /v1/user-foods."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


def _body(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "device_id": "scale-abc",
        "name": "Boiled eggs",
        "brand": None,
        "per_100g": {
            "kcal": "155",
            "protein_g": "13.0",
            "carbs_g": "1.1",
            "fat_g": "11.0",
            "fiber_g": "0",
        },
        "default_serving_g": "50",
    }
    base.update(overrides)
    return base


async def test_create_returns_201_with_full_body(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resp = await client.post("/v1/user-foods", json=_body())
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"].startswith("uf_")
    assert body["name"] == "Boiled eggs"
    assert body["device_id"] == "scale-abc"
    assert Decimal(body["per_100g"]["kcal"]) == Decimal("155")
    assert "created_at" in body and "updated_at" in body


async def test_create_persists_row(client: AsyncClient, db_session: AsyncSession) -> None:
    resp = await client.post("/v1/user-foods", json=_body(name="Banana"))
    user_food_id = resp.json()["id"]
    row = (
        await db_session.execute(
            text("SELECT name, device_id, kcal_per_100g FROM user_foods WHERE id = :id"),
            {"id": user_food_id},
        )
    ).one()
    assert row[0] == "Banana"
    assert row[1] == "scale-abc"
    assert Decimal(row[2]) == Decimal("155")


async def test_create_macros_over_100g_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    body = _body(
        per_100g={
            "kcal": "100",
            "protein_g": "40",
            "carbs_g": "40",
            "fat_g": "30",  # 110 total
        }
    )
    resp = await client.post("/v1/user-foods", json=body)
    assert resp.status_code == 422


async def test_create_negative_kcal_rejected(client: AsyncClient, db_session: AsyncSession) -> None:
    body = _body(per_100g={"kcal": "-1", "protein_g": "0", "carbs_g": "0", "fat_g": "0"})
    resp = await client.post("/v1/user-foods", json=body)
    assert resp.status_code == 422


async def test_create_empty_name_rejected(client: AsyncClient, db_session: AsyncSession) -> None:
    body = _body(name="")
    resp = await client.post("/v1/user-foods", json=body)
    assert resp.status_code == 422


async def test_create_extra_field_rejected(client: AsyncClient, db_session: AsyncSession) -> None:
    body = _body()
    body["unexpected"] = "x"
    resp = await client.post("/v1/user-foods", json=body)
    assert resp.status_code == 422


async def test_two_devices_can_have_same_name(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    a = await client.post("/v1/user-foods", json=_body(device_id="scale-A"))
    b = await client.post("/v1/user-foods", json=_body(device_id="scale-B"))
    assert a.status_code == 201
    assert b.status_code == 201
    assert a.json()["id"] != b.json()["id"]
