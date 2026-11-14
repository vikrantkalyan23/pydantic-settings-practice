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
    python3 -m pip install 'pydantic-settings>=2,<3'

Run with defaults:
    python3 1_basic.py

Override defaults using environment variables:
    APP_PORT=9000 APP_DEBUG=true python3 1_basic.py
HOW LOADING WORKS, STEP BY STEP
------------------------------
For APP_PORT=9000, calling Settings() performs these steps:
    1. Inspect the fields declared on Settings.
    2. Look for constructor values, then matching environment values.
    3. Use a field default if no configured source supplied a value.
    4. Convert compatible values and validate their types.
    5. Return an object whose attributes application code can use directly.
Field declarations describe a contract; they do not read the environment when
the class is defined. Settings() performs the loading. Importing this module
therefore defines the class without constructing an application configuration.

WHY THIS HELPS
--------------
Manual configuration commonly looks like this:
    port = int(os.environ.get("APP_PORT", "8000"))
    debug = os.environ.get("APP_DEBUG", "false").lower() == "true"
This spreads parsing rules throughout the application. In particular,
bool("false") is True because any non-empty string is truthy. A bool settings
field parses supported text values such as true/false, yes/no, on/off, and 1/0.
Use a settings object once near startup and pass its values to your components.

TYPES, DEFAULTS, AND EMPTY VALUES
--------------------------------
These declarations have different contracts:
    name: str = "Practice API"   # optional input, non-null result
    name: str                    # required input, non-null result
    name: str | None             # required input, nullable result
    name: str | None = None      # optional input, nullable result
A shell variable is text: APP_NAME=null is normally the string "null", not None.
An empty string also counts as a supplied value by default: APP_PORT= fails
integer validation rather than falling back to 8000. env_ignore_empty=True is
an explicit alternative when empty deployment variables should be ignored.
Python annotations enable validation here because BaseSettings processes them;
an annotation on an ordinary Python variable does not enforce its type.

An int annotation checks integer compatibility, not a port's valid range.
The intermediate lesson adds numeric constraints. For example, this basic
lesson accepts APP_PORT=-1 as an integer even though it is not a valid TCP port.
Coercion is deliberate for environment input; globally enabling strict=True
can reject text values that would otherwise convert successfully.

WORKED COMMANDS (POSIX SHELL)
----------------------------
    python3 1_basic.py
    APP_APP_NAME="Orders API" APP_PORT=9000 python3 1_basic.py
    APP_DEBUG=false python3 1_basic.py
    APP_PORT=hello python3 1_basic.py
APP_APP_NAME contains APP_ plus the complete field name app_name. Prefixes do
not remove repeated words. A variable assigned before the command applies to
that child process; export APP_PORT=9000 persists it in the current shell.
For PowerShell use $env:APP_PORT = "9000", then python 1_basic.py.

READING ERRORS AND INSPECTING OUTPUT
-----------------------------------
A ValidationError identifies the field, the failed rule, and often the input.
Read the field location first, then fix the source that supplied that value.
In application startup code you may catch ValidationError to format a concise
message; do not silently replace broken configuration with defaults.
settings.model_dump() returns a dictionary; settings.model_dump_json() returns
JSON. Inspecting this basic object is fine, but later lessons contain secrets
and should print only selected fields. model_dump() does not update sources.
Changing settings.port on a mutable instance does not write to the environment
and, by default, assignments are not revalidated. Prefer rebuilding settings.

Reference: https://docs.pydantic.dev/latest/concepts/pydantic_settings/

"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Read environment variables starting with APP_.
    model_config = SettingsConfigDict(env_prefix="APP_")

    app_name: str = "Practice API"
    port: int = 8000
    debug: bool = False


def main() -> None:
    """Load configuration at the script boundary and demonstrate its behavior."""
    # Load defaults and apply environment overrides, converting strings to types.
    settings = Settings()

    print(f"App name: {settings.app_name}")
    print(f"Port: {settings.port}")
    print(f"Debug: {settings.debug}")

    # Explicit values override both environment variables and defaults.
    custom_settings = Settings(port=7000)
    print(f"Explicit port override: {custom_settings.port}")


if __name__ == "__main__":
    main()
