"""EXPERT: define configuration policy and control its lifecycle.

THEORY
------
Build on 2_intermediate.py by deciding exactly which sources participate,
how deployment-wide constraints work, and when configuration is refreshed.

1. Custom sources are an explicit policy
   settings_customise_sources returns source objects in descending priority.
   This example adds JsonConfigSettingsSource after file secrets, so deployment
   credentials and environment overrides outrank the shipped JSON configuration.
   Setting json_file alone does not activate that source. The JSON file is
   optional here; malformed JSON fails loading. Its keys are field names such
   as database, not environment names such as APP_DATABASE.
   Sources produce dictionaries. Nested mappings merge across sources before
   validation: an environment host can replace the JSON host while retaining
   JSON pool_size. This does not mean arbitrary lists merge element by element.

2. Secrets have a bootstrap problem
   A secrets directory must be known before settings are loaded. get_settings()
   reads APP_SECRETS_DIR from the process environment and passes _secrets_dir.
   Putting APP_SECRETS_DIR only in .env will not configure that directory.
   A file named APP_API_KEY supplies the top-level api_key field. Ordinary file
   secrets do not automatically interpret nested filenames like the environment
   delimiter. A missing configured directory warns; an absent production key
   fails the validator. SecretStr masks display but is not encryption.

3. Cross-field invariants express resource budgets
   Each worker owns a connection pool. workers * database.pool_size must fit
   max_database_connections. Checking each field separately cannot enforce this.
   A production deployment additionally requires a non-empty API key.

4. Cache at the application boundary
   Construct settings at startup and inject the instance into components.
   lru_cache avoids repeated source reads and returns one snapshot per process.
   reload_settings clears the cache and reconstructs it; existing references
   retain their old values. Reload at a controlled boundary: cache clearing is
   not a coordinated configuration rollout across threads or worker processes.
   If reconstruction fails, callers receive the error; there is no automatic
   fallback to the previous snapshot in this example.

5. Immutability and diagnostics
   frozen=True prevents field reassignment. Nested models are separately frozen;
   frozen models are not deeply immutable if you add mutable lists or dicts.
   hide_input_in_errors hides input values in formatted validation messages;
   structured errors can still include inputs. Avoid logging entire settings or
   error payloads containing credentials. Keep secret files outside the repo.

EXAMPLE WALKTHROUGH
-------------------
With JSON port=8100, dotenv port=8200, and environment APP_PORT=8300, the result
is 8300. Settings(port=8400) wins over all three. JSON pool_size=10 survives an
environment override of database.host. workers=4 and pool_size=50 exceed the
100-connection budget and fail. Production without an API key also fails.

TESTING AND PRACTICE
--------------------
Control every source when testing: use a clean environment, _env_file=None,
a temporary secrets directory, and a temporary JSON path (via a Settings
subclass with its own model_config). Disabling dotenv does not disable JSON,
secrets, or environment loading. Clear get_settings.cache_clear() around tests
that change environment variables. Check successful precedence, invalid budgets,
and secret masking without printing the underlying key.

Try changing APP_PORT after calling get_settings(): the cached instance stays
unchanged until reload_settings(). Then compare both object identity and port.
For another extension, register a custom source that reads a deployment service;
keep network access, credentials, timeouts, and failure policy explicit there.

Expert settings example: layered sources and application lifecycle.

Requires Python 3.10+:
    python3 -m pip install 'pydantic-settings>=2,<3'
    python3 3_expert.py

Optional config.3.json beside this script (JSON keys use Python field names):
    {
      "port": 8100,
      "database": {"host": "db.internal", "pool_size": 10}
    }

Optional .env beside this script:
    APP_PORT=8200
    APP_DATABASE__POOL_SIZE=15

Try environment overrides and validation:
    APP_PORT=8300 APP_DATABASE__HOST=db.example.com python3 3_expert.py
    APP_DATABASE__POOL_SIZE=50 APP_WORKERS=4 python3 3_expert.py
    APP_ENVIRONMENT=production python3 3_expert.py
    APP_ENVIRONMENT=production APP_API_KEY=practice-only python3 3_expert.py

To load a file secret, create a private directory outside the repository,
put a practice key in a file named APP_API_KEY, then run:
    APP_SECRETS_DIR=/absolute/path/to/private-secrets python3 3_expert.py

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
