"""Expert settings example: layered sources and application lifecycle.

Requires Python 3.10+:
    python3 -m pip install 'pydantic-settings>=2,<3'
    python3 3_practice.py

Optional config.3.json beside this script (JSON keys use Python field names):
    {
      "port": 8100,
      "database": {"host": "db.internal", "pool_size": 10}
    }

Optional .env beside this script:
    APP_PORT=8200
    APP_DATABASE__POOL_SIZE=15

Try environment overrides and validation:
    APP_PORT=8300 APP_DATABASE__HOST=db.example.com python3 3_practice.py
    APP_DATABASE__POOL_SIZE=50 APP_WORKERS=4 python3 3_practice.py
    APP_ENVIRONMENT=production python3 3_practice.py
    APP_ENVIRONMENT=production APP_API_KEY=practice-only python3 3_practice.py

To load a file secret, create a private directory outside the repository,
put a practice key in a file named APP_API_KEY, then run:
    APP_SECRETS_DIR=/absolute/path/to/private-secrets python3 3_practice.py

Priority (highest first): constructor > environment > dotenv > secrets > JSON
> field defaults. Nested dictionaries merge across sources, so overriding a
single database field preserves other fields from lower-priority sources.

Reference: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

BASE_DIR = Path(__file__).resolve().parent


class DatabaseSettings(BaseModel):
    # Frozen nested models prevent accidental mutation of cached configuration.
    model_config = {"frozen": True, "extra": "forbid"}

    host: str = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)
    pool_size: int = Field(default=5, ge=1, le=100)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_nested_delimiter="__",
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        json_file=BASE_DIR / "config.3.json",
        json_file_encoding="utf-8",
        # Permit a shared dotenv file containing other practice examples.
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
    )

    environment: Literal["development", "test", "production"] = "development"
    port: int = Field(default=8000, ge=1, le=65535)
    workers: int = Field(default=2, ge=1, le=16)
    max_database_connections: int = Field(default=100, ge=1)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    api_key: SecretStr | None = None

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Declaring json_file alone does not register the JSON source.
        # The returned tuple explicitly defines source priority.
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            JsonConfigSettingsSource(settings_cls),
        )

    @model_validator(mode="after")
    def validate_deployment(self) -> "Settings":
        if self.workers * self.database.pool_size > self.max_database_connections:
            raise ValueError("workers * pool_size exceeds max_database_connections")
        if self.environment == "production":
            if self.api_key is None or not self.api_key.get_secret_value().strip():
                raise ValueError("production requires a non-empty api_key")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # APP_SECRETS_DIR is a bootstrap option read from the process environment.
    # No directory is configured by default, so a plain run needs no extra files.
    return Settings(_secrets_dir=os.environ.get("APP_SECRETS_DIR"))


def reload_settings() -> Settings:
    """Explicitly rebuild the cached snapshot after configuration changes."""
    get_settings.cache_clear()
    return get_settings()


if __name__ == "__main__":
    settings = get_settings()
    print(f"Environment: {settings.environment}; port: {settings.port}")
    print(f"Database: {settings.database.host}:{settings.database.port}")
    print(f"Total pool connections: {settings.workers * settings.database.pool_size}")
    # Print selected fields; never dump raw secret values or validation inputs.
    print(f"API key: {settings.api_key if settings.api_key is not None else 'unset'}")
    print(f"Cached instance reused: {get_settings() is settings}")

    # Constructor overrides remain highest priority for isolated instances.
    print(f"Explicit port override: {Settings(port=8400).port}")
    # Call reload_settings() only at a controlled application lifecycle boundary.
    # Existing consumers retain their old instance; the cache is per process.
