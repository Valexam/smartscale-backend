"""Device-key middleware behavior."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.integration


async def test_missing_key_returns_401(app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/v1/measurements",
            json={
                "observed_barcode": "1234567890",
                "weight_grams": "1",
                "measured_at": "2026-04-27T10:14:08Z",
                "device_id": "scale-abc123",
            },
        )
    assert resp.status_code == 401
    assert resp.json()["code"] == "MISSING_DEVICE_KEY"
    assert resp.headers["content-type"].startswith("application/problem+json")


async def test_wrong_key_returns_401(app: FastAPI) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"x-device-key": "wrong"},
    ) as c:
        resp = await c.post(
            "/v1/measurements",
            json={
                "observed_barcode": "1234567890",
                "weight_grams": "1",
                "measured_at": "2026-04-27T10:14:08Z",
                "device_id": "scale-abc123",
            },
        )
    assert resp.status_code == 401
    assert resp.json()["code"] == "INVALID_DEVICE_KEY"


async def test_health_does_not_require_key(app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/v1/healthz")
    assert resp.status_code == 200
