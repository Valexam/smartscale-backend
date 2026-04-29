"""POST /v1/products/{barcode}/refresh."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


BARCODE = "7311070016010"


async def test_refresh_unknown_barcode_creates_queued_job(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resp = await client.post(f"/v1/products/{BARCODE}/refresh")

    assert resp.status_code == 202
    body = resp.json()
    assert body == {"barcode": BARCODE, "status": "queued"}

    row = (
        await db_session.execute(
            text("SELECT status, attempts, last_error FROM scrape_jobs WHERE barcode = :b"),
            {"b": BARCODE},
        )
    ).one()
    assert row[0] == "queued"
    assert row[1] == 0
    assert row[2] is None


async def test_refresh_resets_completed_job_to_queued(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO scrape_jobs (barcode, status, attempts, last_error) "
            "VALUES (:b, 'completed', 3, 'a previous error')"
        ),
        {"b": BARCODE},
    )
    await db_session.commit()

    resp = await client.post(f"/v1/products/{BARCODE}/refresh")
    assert resp.status_code == 202

    row = (
        await db_session.execute(
            text("SELECT status, attempts, last_error FROM scrape_jobs WHERE barcode = :b"),
            {"b": BARCODE},
        )
    ).one()
    assert row[0] == "queued"
    assert row[1] == 0
    assert row[2] is None


async def test_refresh_resets_failed_job_to_queued(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO scrape_jobs (barcode, status, attempts, last_error) "
            "VALUES (:b, 'failed', 5, 'rate limited')"
        ),
        {"b": BARCODE},
    )
    await db_session.commit()

    resp = await client.post(f"/v1/products/{BARCODE}/refresh")
    assert resp.status_code == 202

    row = (
        await db_session.execute(
            text("SELECT status, attempts, last_error FROM scrape_jobs WHERE barcode = :b"),
            {"b": BARCODE},
        )
    ).one()
    assert row[0] == "queued"
    assert row[1] == 0
    assert row[2] is None


async def test_refresh_idempotent_on_already_queued_job(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resp1 = await client.post(f"/v1/products/{BARCODE}/refresh")
    resp2 = await client.post(f"/v1/products/{BARCODE}/refresh")

    assert resp1.status_code == 202
    assert resp2.status_code == 202

    count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM scrape_jobs WHERE barcode = :b"),
            {"b": BARCODE},
        )
    ).scalar_one()
    assert count == 1


async def test_refresh_invalid_barcode_returns_422(client: AsyncClient) -> None:
    resp = await client.post("/v1/products/abc/refresh")
    assert resp.status_code == 422


async def test_refresh_requires_device_key(app: FastAPI) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(f"/v1/products/{BARCODE}/refresh")
    assert resp.status_code == 401
