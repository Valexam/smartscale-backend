"""Schemathesis property tests: generated inputs must not break the OpenAPI contract.

Schemathesis 4.x uses schemathesis.openapi.from_asgi() + schema.parametrize()
(not the 3.x from_asgi shortcut). The parametrize() decorator drives Hypothesis
to generate many inputs per operation; case.call_and_validate() asserts that each
response matches the schema declared in the OpenAPI document.

CLI equivalent (exercised in CI against a live server):
    uv run schemathesis run http://127.0.0.1:8000/v1/openapi.json --checks all

Checks used in embedded form
----------------------------
We run an explicit allowlist rather than all checks. Several built-in checks
conflict with our middleware-auth pattern (DeviceKeyMiddleware returns 401 for
*any* unauthenticated request, before the router resolves the method/path):

- `unsupported_method` expects 405 for unlisted methods — we return 401.
- `status_code_conformance` reports 401 as undocumented — it is intentional.
- `missing_required_header` / `ignored_auth` generate requests without the key —
  they produce 401s that are not in the OpenAPI responses block.

The three checks below all work correctly with the auth header injected via
`from_asgi(..., headers={...})` and cover the most valuable invariants:

- `not_a_server_error` — no 5xx responses.
- `response_schema_conformance` — every non-4xx response matches its declared schema.
- `content_type_conformance` — responses declare the right Content-Type.
"""

from __future__ import annotations

import pytest
import schemathesis
from fastapi import FastAPI
from schemathesis.checks import CHECKS

pytestmark = [pytest.mark.integration, pytest.mark.schema]

# Load all built-in checks so CHECKS.get_one() resolves for the allowlist.
schemathesis.checks.load_all_checks()

_ACTIVE_CHECKS = [
    CHECKS.get_one("not_a_server_error"),
    CHECKS.get_one("response_schema_conformance"),
    CHECKS.get_one("content_type_conformance"),
]

# NOTE: "schema" is already a session fixture in conftest.py (Alembic migrations).
# "api_openapi_schema" is the fixture; "lazy_schema" is the LazySchema used as
# the parametrize decorator source — two names to avoid the name collision.
lazy_schema = schemathesis.pytest.from_fixture("api_openapi_schema")


@pytest.fixture
def api_openapi_schema(app: FastAPI) -> schemathesis.BaseSchema:
    """Load the OpenAPI schema from the running ASGI app."""
    return schemathesis.openapi.from_asgi(
        "/v1/openapi.json",
        app,
        headers={"x-device-key": "test-key"},
    )


@lazy_schema.parametrize()
def test_openapi_is_consistent(case: schemathesis.Case) -> None:
    """Every generated request must not produce a 5xx and must match the schema."""
    case.call_and_validate(checks=_ACTIVE_CHECKS)
