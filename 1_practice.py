"""Basic pydantic-settings usage.

Install:
    python3 -m pip install pydantic-settings

Run with defaults:
    python3 1_practice.py

Override defaults using environment variables:
    APP_PORT=9000 APP_DEBUG=true python3 1_practice.py
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Read environment variables starting with APP_.
    model_config = SettingsConfigDict(env_prefix="APP_")

    app_name: str = "Practice API"
    port: int = 8000
    debug: bool = False


if __name__ == "__main__":
    # Load defaults and apply environment overrides, converting strings to types.
    settings = Settings()

    print(f"App name: {settings.app_name}")
    print(f"Port: {settings.port}")
    print(f"Debug: {settings.debug}")

    # Explicit values override both environment variables and defaults.
    custom_settings = Settings(port=7000)
    print(f"Explicit port override: {custom_settings.port}")
