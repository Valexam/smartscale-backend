"""RFC 7807 problem+json shape."""

from __future__ import annotations

import json

from smartscale_api.schemas.errors import problem_response


def test_basic_shape() -> None:
    resp = problem_response(401, "INVALID_DEVICE_KEY", "X-Device-Key does not match")
    body = json.loads(bytes(resp.body))
    assert resp.status_code == 401
    assert resp.media_type == "application/problem+json"
    assert body["status"] == 401
    assert body["code"] == "INVALID_DEVICE_KEY"
    assert body["detail"] == "X-Device-Key does not match"
    assert body["title"] == "Unauthorized"
    assert body["type"].startswith("https://smartscale.example/errors/")


def test_extra_fields() -> None:
    resp = problem_response(422, "VALIDATION_ERROR", "bad input", errors=[{"loc": ["body"]}])
    body = json.loads(bytes(resp.body))
    assert body["errors"] == [{"loc": ["body"]}]
