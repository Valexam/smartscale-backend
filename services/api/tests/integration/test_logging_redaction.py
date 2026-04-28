"""Auth header values must never appear in logs."""

from __future__ import annotations

import logging

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.security]


async def test_device_key_not_logged(client: AsyncClient, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    await client.get("/v1/healthz", headers={"x-device-key": "test-key"})
    full_log = "\n".join(record.getMessage() for record in caplog.records)
    assert "test-key" not in full_log
