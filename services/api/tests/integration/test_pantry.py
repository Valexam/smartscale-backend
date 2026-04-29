"""/v1/pantry list, add (3 shapes), archive, log."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


DEVICE = "scale-abc"
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


def _custom_body(name: str = "Boiled eggs") -> dict[str, Any]:
    return {
        "device_id": DEVICE,
        "custom": {
            "name": name,
            "per_100g": {
                "kcal": "155",
                "protein_g": "13.0",
                "carbs_g": "1.1",
                "fat_g": "11.0",
                "fiber_g": "0",
            },
            "default_serving_g": "50",
        },
    }


# ---------- POST /v1/pantry shapes ----------


async def test_add_by_barcode_returns_201(client: AsyncClient, db_session: AsyncSession) -> None:
    await _seed_oat_milk(db_session)
    resp = await client.post("/v1/pantry", json={"device_id": DEVICE, "barcode": KNOWN})
    assert resp.status_code == 201
    body = resp.json()
    assert body["source"] == "product"
    assert body["barcode"] == KNOWN
    assert body["name"] == "Havremjölk"
    assert body["user_food_id"] is None


async def test_add_by_barcode_unknown_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resp = await client.post("/v1/pantry", json={"device_id": DEVICE, "barcode": UNKNOWN})
    assert resp.status_code == 404


async def test_add_custom_creates_user_food_and_pantry_atomically(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resp = await client.post("/v1/pantry", json=_custom_body())
    assert resp.status_code == 201
    body = resp.json()
    assert body["source"] == "user_food"
    assert body["barcode"] is None
    assert body["user_food_id"].startswith("uf_")
    assert body["name"] == "Boiled eggs"
    assert Decimal(body["per_100g"]["kcal"]) == Decimal("155")


async def test_add_by_user_food_id(client: AsyncClient, db_session: AsyncSession) -> None:
    # Create a user_food first
    resp = await client.post(
        "/v1/user-foods",
        json={
            "device_id": DEVICE,
            "name": "Greek yogurt",
            "per_100g": {
                "kcal": "97",
                "protein_g": "9.0",
                "carbs_g": "3.6",
                "fat_g": "5.0",
            },
        },
    )
    uf_id = resp.json()["id"]

    resp = await client.post(
        "/v1/pantry",
        json={
            "device_id": DEVICE,
            "user_food_id": uf_id,
            "default_serving_g": "150",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["source"] == "user_food"
    assert body["user_food_id"] == uf_id


async def test_add_by_user_food_id_wrong_device_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resp = await client.post(
        "/v1/user-foods",
        json={
            "device_id": "scale-A",
            "name": "Foo",
            "per_100g": {"kcal": "1", "protein_g": "0", "carbs_g": "0", "fat_g": "0"},
        },
    )
    uf_id = resp.json()["id"]

    resp = await client.post("/v1/pantry", json={"device_id": "scale-B", "user_food_id": uf_id})
    assert resp.status_code == 404


async def test_add_with_zero_sources_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resp = await client.post("/v1/pantry", json={"device_id": DEVICE})
    assert resp.status_code == 422


async def test_add_with_two_sources_returns_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resp = await client.post(
        "/v1/pantry",
        json={"device_id": DEVICE, "barcode": KNOWN, "user_food_id": "uf_xxx"},
    )
    assert resp.status_code == 422


# ---------- GET /v1/pantry ----------


async def test_list_empty_returns_zero_items(client: AsyncClient, db_session: AsyncSession) -> None:
    resp = await client.get(f"/v1/pantry?device_id={DEVICE}")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"items": [], "limit": 50, "offset": 0}


async def test_list_returns_only_live_items(client: AsyncClient, db_session: AsyncSession) -> None:
    await _seed_oat_milk(db_session)
    add = await client.post("/v1/pantry", json={"device_id": DEVICE, "barcode": KNOWN})
    pi_id = add.json()["id"]
    add2 = await client.post("/v1/pantry", json=_custom_body("Eggs"))
    pi_id2 = add2.json()["id"]

    # Archive the first one
    arch = await client.delete(f"/v1/pantry/{pi_id}?device_id={DEVICE}")
    assert arch.status_code == 204

    resp = await client.get(f"/v1/pantry?device_id={DEVICE}")
    items = resp.json()["items"]
    assert {i["id"] for i in items} == {pi_id2}


async def test_list_isolates_devices(client: AsyncClient, db_session: AsyncSession) -> None:
    await _seed_oat_milk(db_session)
    await client.post("/v1/pantry", json={"device_id": "scale-A", "barcode": KNOWN})
    await client.post("/v1/pantry", json=_custom_body("Eggs"))  # device "scale-abc"

    resp_a = await client.get("/v1/pantry?device_id=scale-A")
    resp_b = await client.get(f"/v1/pantry?device_id={DEVICE}")
    assert {i["name"] for i in resp_a.json()["items"]} == {"Havremjölk"}
    assert {i["name"] for i in resp_b.json()["items"]} == {"Eggs"}


async def test_list_respects_limit_and_offset(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    for i in range(3):
        await client.post("/v1/pantry", json=_custom_body(f"Food{i}"))
    r = await client.get(f"/v1/pantry?device_id={DEVICE}&limit=2&offset=1")
    body = r.json()
    assert body["limit"] == 2
    assert body["offset"] == 1
    assert len(body["items"]) == 2


# ---------- DELETE /v1/pantry/{id} ----------


async def test_archive_idempotent(client: AsyncClient, db_session: AsyncSession) -> None:
    add = await client.post("/v1/pantry", json=_custom_body())
    pi_id = add.json()["id"]
    r1 = await client.delete(f"/v1/pantry/{pi_id}?device_id={DEVICE}")
    r2 = await client.delete(f"/v1/pantry/{pi_id}?device_id={DEVICE}")
    assert r1.status_code == 204
    assert r2.status_code == 204


async def test_archive_unknown_returns_404(client: AsyncClient, db_session: AsyncSession) -> None:
    r = await client.delete(f"/v1/pantry/pi_doesnotexist?device_id={DEVICE}")
    assert r.status_code == 404


async def test_archive_wrong_device_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    add = await client.post(
        "/v1/pantry",
        json={
            "device_id": "scale-A",
            "custom": _custom_body()["custom"],
        },
    )
    pi_id = add.json()["id"]
    r = await client.delete(f"/v1/pantry/{pi_id}?device_id=scale-B")
    assert r.status_code == 404


# ---------- POST /v1/pantry/{id}/log ----------


async def test_log_product_backed_writes_measurement(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_oat_milk(db_session)
    add = await client.post("/v1/pantry", json={"device_id": DEVICE, "barcode": KNOWN})
    pi_id = add.json()["id"]

    log = await client.post(
        f"/v1/pantry/{pi_id}/log",
        json={
            "device_id": DEVICE,
            "weight_grams": "100",
            "measured_at": "2026-04-29T19:14:08Z",
        },
    )
    assert log.status_code == 201
    body = log.json()
    assert body["observed_barcode"] == KNOWN
    assert body["product_barcode"] == KNOWN
    assert body["product"]["name"] == "Havremjölk"
    assert Decimal(body["computed"]["kcal"]) == Decimal("46")


async def test_log_user_food_backed_uses_synthetic_barcode(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    add = await client.post("/v1/pantry", json=_custom_body())
    pi_id = add.json()["id"]

    log = await client.post(
        f"/v1/pantry/{pi_id}/log",
        json={
            "device_id": DEVICE,
            "weight_grams": "50",
            "measured_at": "2026-04-29T19:14:08Z",
        },
    )
    assert log.status_code == 201
    body = log.json()
    assert body["observed_barcode"].startswith("uf-")
    assert re.match(r"^[0-9A-Za-z\-]{4,32}$", body["observed_barcode"])
    assert body["product_barcode"] is None
    assert body["product"] is None
    # 155 kcal/100g * 50g / 100 = 77.5 kcal
    assert Decimal(body["computed"]["kcal"]) == Decimal("77.5")


async def test_log_bumps_last_used_at(client: AsyncClient, db_session: AsyncSession) -> None:
    add = await client.post("/v1/pantry", json=_custom_body())
    pi_id = add.json()["id"]
    listed = (await client.get(f"/v1/pantry?device_id={DEVICE}")).json()["items"]
    assert listed[0]["last_used_at"] is None

    await client.post(
        f"/v1/pantry/{pi_id}/log",
        json={
            "device_id": DEVICE,
            "weight_grams": "50",
            "measured_at": "2026-04-29T19:14:08Z",
        },
    )

    listed = (await client.get(f"/v1/pantry?device_id={DEVICE}")).json()["items"]
    assert listed[0]["last_used_at"] is not None


async def test_log_archived_returns_410(client: AsyncClient, db_session: AsyncSession) -> None:
    add = await client.post("/v1/pantry", json=_custom_body())
    pi_id = add.json()["id"]
    await client.delete(f"/v1/pantry/{pi_id}?device_id={DEVICE}")

    log = await client.post(
        f"/v1/pantry/{pi_id}/log",
        json={
            "device_id": DEVICE,
            "weight_grams": "50",
            "measured_at": "2026-04-29T19:14:08Z",
        },
    )
    assert log.status_code == 410


async def test_log_unknown_pantry_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    log = await client.post(
        "/v1/pantry/pi_doesnotexist/log",
        json={
            "device_id": DEVICE,
            "weight_grams": "50",
            "measured_at": "2026-04-29T19:14:08Z",
        },
    )
    assert log.status_code == 404


async def test_log_wrong_device_returns_404(client: AsyncClient, db_session: AsyncSession) -> None:
    add = await client.post(
        "/v1/pantry",
        json={"device_id": "scale-A", "custom": _custom_body()["custom"]},
    )
    pi_id = add.json()["id"]
    log = await client.post(
        f"/v1/pantry/{pi_id}/log",
        json={
            "device_id": "scale-B",
            "weight_grams": "50",
            "measured_at": "2026-04-29T19:14:08Z",
        },
    )
    assert log.status_code == 404


async def test_log_macros_frozen_after_user_food_change(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """ADR-0007: once a measurement is logged, its computed_* must not change
    even if the underlying user_food is later modified."""
    add = await client.post("/v1/pantry", json=_custom_body())
    pi_id = add.json()["id"]
    uf_id = add.json()["user_food_id"]

    log = await client.post(
        f"/v1/pantry/{pi_id}/log",
        json={
            "device_id": DEVICE,
            "weight_grams": "100",
            "measured_at": "2026-04-29T19:14:08Z",
        },
    )
    measurement_id = log.json()["id"]
    original_kcal = Decimal(log.json()["computed"]["kcal"])

    # Mutate the user_food directly (DB-level — there's no edit endpoint in 5a)
    await db_session.execute(
        text("UPDATE user_foods SET kcal_per_100g = 999 WHERE id = :id"),
        {"id": uf_id},
    )
    await db_session.commit()

    # The logged measurement's computed_kcal must be unchanged
    row = (
        await db_session.execute(
            text("SELECT computed_kcal FROM measurements WHERE id = :id"),
            {"id": measurement_id},
        )
    ).scalar_one()
    assert Decimal(row) == original_kcal


# ---------- Helper: make sure list ordering uses last_used_at ----------


async def test_list_orders_by_last_used_at_desc(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    a = await client.post("/v1/pantry", json=_custom_body("A"))
    b = await client.post("/v1/pantry", json=_custom_body("B"))
    c = await client.post("/v1/pantry", json=_custom_body("C"))
    a_id = a.json()["id"]
    b_id = b.json()["id"]
    c_id = c.json()["id"]

    # Log order: B, then A. C never logged.
    measured = datetime(2026, 4, 29, 12, 0, 0, tzinfo=UTC)
    await client.post(
        f"/v1/pantry/{b_id}/log",
        json={
            "device_id": DEVICE,
            "weight_grams": "10",
            "measured_at": measured.isoformat().replace("+00:00", "Z"),
        },
    )
    await client.post(
        f"/v1/pantry/{a_id}/log",
        json={
            "device_id": DEVICE,
            "weight_grams": "10",
            "measured_at": (measured + timedelta(seconds=10)).isoformat().replace("+00:00", "Z"),
        },
    )

    listed = (await client.get(f"/v1/pantry?device_id={DEVICE}")).json()["items"]
    names = [i["name"] for i in listed]
    # A logged most recently → first; B next; C never logged → last (added_at fallback)
    assert names[0] == "A"
    assert names[1] == "B"
    assert names[2] == "C"
    assert listed[0]["id"] == a_id
    assert listed[2]["id"] == c_id
