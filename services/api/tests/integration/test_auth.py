"""Device-key middleware behavior."""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from smartscale_api.app import create_app
from smartscale_api.config import Settings

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def admin_app(database_url: str, schema: None) -> FastAPI:
    """Like the shared `app` fixture but with ADMIN_KEY also configured."""
    settings = Settings(
        env="test",
        device_key=SecretStr("test-key"),
        admin_key=SecretStr("admin-secret"),
        database_url=database_url,
    )
    return create_app(settings=settings)


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


async def test_put_product_without_key_returns_401(app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.put(
            "/v1/products/7311070016010",
            json={
                "name": "Havremjölk",
                "per_100g": {
                    "kcal": "46",
                    "protein_g": "1.0",
                    "carbs_g": "6.7",
                    "fat_g": "1.5",
                },
            },
        )
    assert resp.status_code == 401
    assert resp.json()["code"] == "MISSING_DEVICE_KEY"
    assert resp.headers["content-type"].startswith("application/problem+json")


async def test_admin_key_grants_access(admin_app: FastAPI) -> None:
    """A correct X-Admin-Key authenticates in place of X-Device-Key."""
    async with AsyncClient(
        transport=ASGITransport(app=admin_app),
        base_url="http://test",
        headers={"x-admin-key": "admin-secret"},
    ) as c:
        resp = await c.get("/v1/measurements", params={"device_id": "scale-abc"})
    assert resp.status_code == 200


async def test_wrong_admin_key_returns_401(admin_app: FastAPI) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=admin_app),
        base_url="http://test",
        headers={"x-admin-key": "nope"},
    ) as c:
        resp = await c.get("/v1/measurements", params={"device_id": "scale-abc"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "INVALID_DEVICE_KEY"


async def test_admin_key_rejected_when_not_configured(app: FastAPI) -> None:
    """With no ADMIN_KEY set, an X-Admin-Key header never authenticates."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"x-admin-key": "anything"},
    ) as c:
        resp = await c.get("/v1/measurements", params={"device_id": "scale-abc"})
    assert resp.status_code == 401
