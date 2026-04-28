"""Auth header values must never appear in logs.

The filter is installed on the root logger (see app._install_redacting_filter),
so any propagating logger will have its records scrubbed.
"""

from __future__ import annotations

import logging

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.security]


async def test_device_key_not_logged(client: AsyncClient, caplog: pytest.LogCaptureFixture) -> None:
    """A log record that contains the device-key header name is redacted.

    This exercises the live filter installed by create_app(): we emit a record
    that contains 'x-device-key' as a tuple arg, then assert it was replaced
    with [REDACTED] — proving the filter ran and the key never appears in logs.

    The logger is created inside the test (not at module level) to avoid being
    disabled by Alembic's fileConfig call during the session-scoped schema
    fixture, which uses disable_existing_loggers=True by default.
    """
    test_logger = logging.getLogger("smartscale_api.test_redaction_live")
    test_logger.disabled = False  # guard: ensure Alembic fileConfig hasn't disabled it

    with caplog.at_level(logging.DEBUG, logger="smartscale_api.test_redaction_live"):
        test_logger.info("incoming header: %s", "x-device-key: test-key", stacklevel=1)

    messages = [record.getMessage() for record in caplog.records]
    full_log = "\n".join(messages)

    assert "test-key" not in full_log, "device key must not appear in log output"
    assert "x-device-key" not in full_log, "device key header name must not appear in log output"
    assert "[REDACTED]" in full_log, "filter must replace the sensitive arg with [REDACTED]"
