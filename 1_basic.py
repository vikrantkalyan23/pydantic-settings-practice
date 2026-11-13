"""BASIC: turn application configuration into typed Python objects.

THEORY
------
Configuration varies between deployments: a port, app name, or debug flag.
Environment variables always start as strings. BaseSettings reads those values
and asks Pydantic to convert and validate them using your field annotations.
BaseModel validates supplied data; BaseSettings additionally reads configuration
sources. In Pydantic v2, import BaseSettings from pydantic_settings.

A field with a default can be omitted. A field without a default is required:
    api_key: str                 # missing value raises ValidationError
    api_key: str | None = None   # explicitly permits omission and None
The annotation str | None alone does not make a field optional at startup.

SettingsConfigDict configures loading behavior. env_prefix="APP_" maps port to
APP_PORT. Names are case-insensitive by default. This example reads process
environment variables; it does not configure a dotenv file.

For the sources used here, priority is constructor > environment > defaults.
Settings(port=7000) wins even if APP_PORT=9000. Text "9000" becomes int 9000;
"true" becomes bool True. APP_PORT=hello raises a ValidationError when Settings
is constructed, so bad configuration fails before application work begins.
A settings instance is a snapshot: later environment changes require a new one.

EXAMPLES AND EXPECTED RESULTS
-----------------------------
With no APP_* variables set, the script prints:
    App name: Practice API
    Port: 8000
    Debug: False
    Explicit port override: 7000

With APP_PORT=9000 APP_DEBUG=true, port becomes 9000 and debug becomes True.
With APP_PORT=hello, construction fails instead of returning an invalid port.

PRACTICE
--------
1. Add host: str = "localhost" and override it using APP_HOST.
2. Add a required field and observe the missing-field error.
3. Compare type(settings.port) with the text supplied by your shell.

Basic pydantic-settings usage.

Install:
    python3 -m pip install pydantic-settings

Run with defaults:
    python3 1_basic.py

Override defaults using environment variables:
    APP_PORT=9000 APP_DEBUG=true python3 1_basic.py
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
