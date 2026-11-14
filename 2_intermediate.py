"""INTERMEDIATE: structure configuration and enforce application rules.

THEORY
------
Build on 1_basic.py by loading a dotenv file, grouping database options, and
validating both individual values and relationships between values.

1. Dotenv and source priority
   env_file loads key=value pairs from a file; it does not need shell export.
   This example anchors .env to the script directory using Path(__file__), so
   running from another working directory still finds the same file.
   Constructor > process environment > dotenv > file secrets > defaults is the
   default order when CLI parsing is disabled. This example has no secrets
   directory configured. Settings(_env_file=None) disables dotenv loading only;
   it still reads the process environment.

2. Nested settings and complex values
   DatabaseSettings is a BaseModel: it groups values but does not independently
   read the environment. The outer Settings loads APP_DATABASE__HOST and uses
   env_nested_delimiter="__" to build the nested database object.
   Lists use JSON, for example APP_ALLOWED_HOSTS='["localhost", "example.com"]'.
   A comma-separated string is not a JSON list. Nested environment variables
   override matching values in an APP_DATABASE JSON object.

3. Validation
   Field(ge=1, le=65535) constrains ports; Literal limits environment names.
   A mode="after" model validator receives parsed fields and rejects production
   debug mode. It returns self when valid. Invalid values raise ValidationError;
   malformed complex environment values can raise SettingsError during loading.
   Settings defaults are validated too.

4. Secrets and extra fields
   SecretStr masks ordinary display; it neither encrypts nor securely stores
   passwords. Call get_secret_value() only where a client needs the credential.
   The default password below is a local demonstration value.
   extra="ignore" permits unrelated entries in the shared dotenv file, but can
   hide dotenv typos. Use extra="forbid" for a dedicated, strictly checked file.
   Keep real secrets out of source control.

EXAMPLE WALKTHROUGH
-------------------
With the dotenv example below, port is 9000 and database.host is db.local.
Setting APP_PORT=9100 in the shell changes only the port; constructor port=7000
still has highest priority. APP_DATABASE__PORT=5433 converts to a nested integer.
APP_PORT=70000 fails its field constraint. Production with debug enabled fails
the model validator even though both individual fields have valid types.

PRACTICE
--------
1. Add a database timeout constrained to a positive number.
2. Load allowed_hosts from JSON and try malformed JSON to compare errors.
3. Run with _env_file=None and explain which overrides still apply.

Intermediate pydantic-settings usage (Python 3.10+, Pydantic v2).

Install:
    python3 -m pip install 'pydantic-settings>=2,<3'

Run with defaults:
    python3 2_intermediate.py

Optionally create .env beside this script (use practice secrets only):
    APP_ENVIRONMENT=development
    APP_PORT=9000
    APP_DATABASE__HOST=db.local
    APP_DATABASE__PASSWORD=practice-password
    APP_ALLOWED_HOSTS=["localhost", "example.com"]

Process environment variables override .env values:
    APP_PORT=9100 APP_DATABASE__PORT=5433 python3 2_intermediate.py

Try invalid configurations to see startup validation errors:
    APP_PORT=70000 python3 2_intermediate.py
    APP_ENVIRONMENT=production APP_DEBUG=true python3 2_intermediate.py

Default priority: constructor arguments > environment > .env > secrets > defaults.
FOLLOW A VALUE THROUGH THE SOURCES
----------------------------------
Suppose defaults declare port=8000, .env contains APP_PORT=9000, and the shell
sets APP_PORT=9100. Settings().port is 9100; Settings(port=7000).port is 7000.
Changing .env does not change either existing object. Construct another Settings
instance to read it again. Loading dotenv supplies configuration to the settings
object; it does not export those entries into the parent shell environment.

To layer local files deliberately, configure:
    env_file=(BASE_DIR / ".env", BASE_DIR / ".env.local")
Later files override earlier files, but process environment still outranks both.
Missing dotenv files are ignored. A relative path uses the working directory;
the absolute path in this lesson avoids that ambiguity.

NESTED JSON VERSUS NESTED VARIABLES
---------------------------------
Try this single command:
    APP_DATABASE='{"host":"json-db","port":5432}' APP_DATABASE__PORT=5433 python3 2_intermediate.py
The result is host=json-db, port=5433, and the remaining database defaults.
The JSON object supplies the whole nested mapping, and the exploded variable
refines its port. Nested mappings from different sources can also merge.
A list override replaces the list; it does not append to the default list.

Field(default_factory=DatabaseSettings) constructs a nested default when needed.
Field(default_factory=lambda: ["localhost"]) expresses a fresh default list for
each instance. Pydantic also handles many mutable defaults safely, but a factory
makes ownership explicit. A nested BaseModel normally has validate_default=False;
BaseSettings validates its own defaults by default. Set validate_default=True on
a nested model if its defaults also need validation rather than trusting them.

ALIASES: WHEN DEPLOYMENT NAMES DIFFER FROM PYTHON NAMES
----------------------------------------------------
A separate settings class can accept an existing deployment variable:
    from pydantic import AliasChoices

    class ServiceSettings(BaseSettings):
        model_config = SettingsConfigDict(env_prefix="APP_")
        service_url: str = Field(
            default="https://example.com",
            validation_alias=AliasChoices("SERVICE_URL", "LEGACY_SERVICE_URL"),
        )

SERVICE_URL is checked before LEGACY_SERVICE_URL. An explicit validation alias
is the complete input name; APP_ is not automatically added to it. The Python
attribute remains service_url. validation_alias affects input lookup while an
alias can also affect serialization when by_alias=True. If constructors must
accept the Python field name too, configure populate_by_name=True.
AliasChoices selects the first matching name within a source; source priority
still decides which source wins.

VALIDATOR ORDER AND ERROR TYPES
-------------------------------
A field_validator(mode="before") receives raw input and is useful for custom
normalization. A field_validator(mode="after") receives the parsed field value.
A model_validator(mode="after") receives the assembled model and checks rules
involving several fields. Prefer built-in types and Field constraints when they
already express the rule; use validators for application-specific requirements.

For a text field you could add:
    from pydantic import field_validator

    @field_validator("app_name")
    @classmethod
    def reject_blank_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("app_name must not be blank")
        return value

A malformed APP_ALLOWED_HOSTS value can fail JSON decoding in the settings
source before field validators run. Catch SettingsError separately from
ValidationError when presenting startup failures. Avoid logging raw inputs:
validation errors can contain credentials before SecretStr has wrapped them.

COMMON MISTAKES AND HOW TO DIAGNOSE THEM
--------------------------------------
* An unrelated process variable is ignored; extra="forbid" does not police the
  entire operating-system environment. Dotenv extra entries behave differently.
* APP_ALLOWED_HOSTS=localhost,example.com is not JSON. Quote the JSON array so
  the shell passes it as one value, including its internal double quotes.
* case_sensitive=True requires exact spelling. With lowercase fields and APP_
  prefix, the default expected name is APP_port, not APP_PORT. On Windows,
  process environment lookups remain case-insensitive.
* Changing an environment variable after construction requires a new instance.
* Use _env_file=None for a temporary override; avoid modifying model_config on
  a shared class during runtime or concurrently running tests.

Reference: https://docs.pydantic.dev/latest/concepts/pydantic_settings/

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


def main() -> None:
    """Load configuration at the script boundary and demonstrate its behavior."""
    settings = Settings()

    print(f"App: {settings.app_name} ({settings.environment})")
    print(f"Port: {settings.port}; debug: {settings.debug}")
    print(f"Database: {settings.database.host}:{settings.database.port}")
    # SecretStr masks the password when printed; it does not encrypt it.
    print(f"Database password: {settings.database.password}")
    print(f"Allowed hosts: {settings.allowed_hosts}")

    custom_settings = Settings(port=7000)
    print(f"Constructor port override: {custom_settings.port}")


if __name__ == "__main__":
    main()
