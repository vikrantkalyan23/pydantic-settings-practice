"""Intermediate pydantic-settings usage (Python 3.10+, Pydantic v2).

Install:
    python3 -m pip install 'pydantic-settings>=2,<3'

Run with defaults:
    python3 2_practice.py

Optionally create .env beside this script (use practice secrets only):
    APP_ENVIRONMENT=development
    APP_PORT=9000
    APP_DATABASE__HOST=db.local
    APP_DATABASE__PASSWORD=practice-password
    APP_ALLOWED_HOSTS=["localhost", "example.com"]

Process environment variables override .env values:
    APP_PORT=9100 APP_DATABASE__PORT=5433 python3 2_practice.py

Try invalid configurations to see startup validation errors:
    APP_PORT=70000 python3 2_practice.py
    APP_ENVIRONMENT=production APP_DEBUG=true python3 2_practice.py

Default priority: constructor arguments > environment > .env > secrets > defaults.
"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    host: str = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)
    username: str = "practice"
    password: SecretStr = SecretStr("local-demo-only")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=Path(__file__).resolve().parent / ".env",
        env_file_encoding="utf-8",
        # APP_DATABASE__HOST sets database.host.
        env_nested_delimiter="__",
        # Allow a shared .env file to contain settings for other examples.
        extra="ignore",
    )

    app_name: str = "Practice API"
    environment: Literal["development", "test", "production"] = "development"
    port: int = Field(default=8000, ge=1, le=65535)
    debug: bool = False
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    # Complex environment values such as lists use JSON syntax.
    allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost"])

    @model_validator(mode="after")
    def validate_production_debug(self) -> "Settings":
        if self.environment == "production" and self.debug:
            raise ValueError("debug must be disabled in production")
        return self


if __name__ == "__main__":
    settings = Settings()

    print(f"App: {settings.app_name} ({settings.environment})")
    print(f"Port: {settings.port}; debug: {settings.debug}")
    print(f"Database: {settings.database.host}:{settings.database.port}")
    # SecretStr masks the password when printed; it does not encrypt it.
    print(f"Database password: {settings.database.password}")
    print(f"Allowed hosts: {settings.allowed_hosts}")

    custom_settings = Settings(port=7000)
    print(f"Constructor port override: {custom_settings.port}")
