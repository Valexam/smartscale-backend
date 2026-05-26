"""Non-auth route errors must also be RFC 7807 application/problem+json.

Auth errors were already problem+json (see test_auth / test_contract). These
assert the same shape now applies to route-level HTTPExceptions (404, …) and to
request-validation failures (422), via the exception handlers in app.py.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_route_404_is_problem_json(client: AsyncClient) -> None:
    resp = await client.get("/v1/products/9999999999999")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["status"] == 404
    assert body["code"] == "NOT_FOUND"
    assert body["detail"] == "product not found"
    assert body["title"] == "Not Found"
    assert body["type"].startswith("https://smartscale.example/errors/")


async def test_validation_422_is_problem_json(client: AsyncClient) -> None:
    resp = await client.post(
        "/v1/measurements",
        json={
            "observed_barcode": "1234567890",
            "weight_grams": "-1",  # fails weight > 0 validation
            "measured_at": "2026-04-27T10:14:08Z",
            "device_id": "scale-abc",
        },
    )
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["status"] == 422
    assert body["code"] == "VALIDATION_ERROR"
    assert isinstance(body["errors"], list) and body["errors"]
