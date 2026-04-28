"""Smoke tests for the API skeleton."""

from fastapi.testclient import TestClient

from smartscale_api.app import create_app


def test_healthz_returns_200() -> None:
    client = TestClient(create_app())
    response = client.get("/v1/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_route_is_404() -> None:
    # Routes outside /v1/* are not gated by DeviceKeyMiddleware.
    client = TestClient(create_app())
    response = client.get("/does-not-exist")
    assert response.status_code == 404
