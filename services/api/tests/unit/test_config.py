"""Settings + startup gate."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from smartscale_api.config import Settings


def test_empty_key_in_dev_is_allowed() -> None:
    s = Settings(env="dev", device_key=SecretStr(""), database_url="")
    s.assert_safe_to_start()  # no raise


def test_empty_key_in_test_is_allowed() -> None:
    s = Settings(env="test", device_key=SecretStr(""), database_url="")
    s.assert_safe_to_start()


def test_empty_key_in_prod_raises() -> None:
    s = Settings(env="prod", device_key=SecretStr("   "), database_url="postgresql://x")
    with pytest.raises(RuntimeError, match="DEVICE_KEY must be non-empty"):
        s.assert_safe_to_start()


def test_secret_str_does_not_leak_in_repr() -> None:
    s = Settings(env="prod", device_key=SecretStr("super-secret"), database_url="")
    assert "super-secret" not in repr(s)
    assert "super-secret" not in str(s)
