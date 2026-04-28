"""Settings, loaded from env. Secrets are SecretStr so they don't leak via repr/logs."""

from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    env: str = "dev"
    device_key: SecretStr = SecretStr("")
    database_url: str = ""

    def assert_safe_to_start(self) -> None:
        """Refuse to boot with an empty device key outside dev/test."""
        key = self.device_key.get_secret_value().strip()
        if not key and self.env not in {"dev", "test"}:
            raise RuntimeError(
                f"DEVICE_KEY must be non-empty when ENV={self.env!r} "
                "(empty allowed only in dev/test)"
            )
