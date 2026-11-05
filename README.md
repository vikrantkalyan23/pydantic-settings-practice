# Pydantic Settings: Basic to Advanced

A practical guide to typed application configuration with **Pydantic v2** and
**pydantic-settings v2**. Examples are independent unless stated otherwise; save a
Python example as `settings.py` to run its accompanying shell command.

## Contents

1. [Installation and first settings](#1-installation-and-first-settings)
2. [Environment variables and dotenv](#2-environment-variables-and-dotenv)
3. [Source priority](#3-source-priority)
4. [Types and validation](#4-types-and-validation)
5. [Aliases and nested settings](#5-aliases-and-nested-settings)
6. [Secrets](#6-secrets)
7. [Custom sources](#7-custom-sources)
8. [Command-line settings](#8-command-line-settings)
9. [Application lifecycle and testing](#9-application-lifecycle-and-testing)
10. [Troubleshooting and practice](#10-troubleshooting-and-practice)

## 1. Installation and first settings

Use Python 3.10+ for the syntax in this guide. Create an isolated environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install 'pydantic-settings>=2,<3'
```

On Windows, activate with `.venv\Scripts\Activate.ps1` in PowerShell.

`BaseModel` validates supplied data; `BaseSettings` also gathers configuration
from settings sources. This lets application code use `settings.port` as an
integer instead of repeatedly parsing strings from `os.environ`.

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Practice API"
    port: int = 8000
    debug: bool = False


settings = Settings()
print(settings.port, settings.debug)
```

```bash
PORT=9000 DEBUG=true python settings.py
# 9000 True
```

A field without a default is required: `api_key: str`. A nullable field still
needs a default to be optional at startup: `api_key: str | None = None`.

## 2. Environment variables and dotenv

A prefix gives the application its own configuration namespace. Dotenv files
are convenient for local development:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
    )

    port: int = 8000
    debug: bool = False


settings = Settings()
print(settings.port, settings.debug)
```

Create `.env` alongside the working directory from which you run Python:

```dotenv
APP_PORT=9000
APP_DEBUG=true
```

Dotenv paths are relative to the current working directory; parent directories
are not searched automatically. For a path tied to your module, use
`Path(__file__).resolve().parent / ".env"` from `pathlib`.

Override the configured file with `Settings(_env_file=".env.test")`, or disable
it with `Settings(_env_file=None)`. Multiple files can be configured as
`env_file=(".env", ".env.local")`; later files override earlier files.

Environment names are case-insensitive by default. With `case_sensitive=True`,
the spelling must match the configured prefix and field or alias. Windows
environment lookup remains case-insensitive.

Use `extra="ignore"` for a deliberately shared dotenv file. The default
`extra="forbid"` catches undeclared dotenv entries, including entries outside
your prefix. Unrelated process environment variables are ignored.

## 3. Source priority

Under the default source order, the first available value wins:

| Priority | Source | Example |
| --- | --- | --- |
| Highest, when enabled | CLI arguments | `--port 9100` |
| 2 | Constructor arguments | `Settings(port=9200)` |
| 3 | Process environment | `APP_PORT=9300` |
| 4 | Dotenv file | `APP_PORT=9400` in `.env` |
| 5 | Secrets directory | A file named `APP_PORT` |
| Lowest | Field default | `port: int = 8000` |

For the preceding `Settings`, `Settings(port=9200)` uses `9200` even when `.env`
contains `APP_PORT=9400`. Explicit custom sources can change this order.
See the [official settings source reference](https://docs.pydantic.dev/latest/concepts/pydantic_settings/#field-value-priority).

## 4. Types and validation

Treat configuration as an application contract: constrain ports, enumerate
supported modes, and reject inconsistent combinations before serving requests.

```python
from typing import Literal

from pydantic import Field, HttpUrl, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_")

    environment: Literal["development", "test", "production"] = "development"
    port: int = Field(default=8000, ge=1, le=65535)
    debug: bool = False
    service_url: HttpUrl = HttpUrl("https://example.com")
    allowed_hosts: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_production(self) -> "Settings":
        if self.environment == "production" and self.debug:
            raise ValueError("debug must be disabled in production")
        return self


settings = Settings()
print(settings.port, settings.allowed_hosts)
```

```bash
APP_PORT=8080 APP_ALLOWED_HOSTS='["localhost", "example.com"]' python settings.py
```

Lists, dictionaries, and nested objects use JSON in environment variables by
default. `localhost,example.com` is not a JSON list. A malformed source value can
raise `SettingsError`; a parsed value that violates a field constraint raises
`ValidationError`. Settings defaults are validated too.

Keep coercion in mind: environment values start as text, so enabling strict
validation globally can reject otherwise useful conversions such as text to
integers. Prefer focused constraints for ordinary environment configuration.

## 5. Aliases and nested settings

Aliases support deployment names that differ from Python attribute names.
Nested models keep related configuration together:

```python
from pydantic import AliasChoices, BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    host: str = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_nested_delimiter="__",
    )

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    api_key: SecretStr = Field(
        validation_alias=AliasChoices("APP_API_KEY", "LEGACY_API_KEY")
    )


settings = Settings()
print(settings.database.host, settings.database.port)
```

```bash
APP_API_KEY=local-demo APP_DATABASE__HOST=db.internal python settings.py
```

The alias names above are complete environment names: the default alias
behavior does not add `env_prefix`. `AliasChoices` checks the listed names in
order. `validation_alias` changes accepted input names while keeping the Python
attribute `api_key`.

An entire object can also be supplied as JSON:

```bash
APP_API_KEY=local-demo \
APP_DATABASE='{"host":"db.internal","port":5432}' \
APP_DATABASE__PORT=6543 python settings.py
# db.internal 6543
```

The nested variable overrides the matching value inside the JSON object. Use
`BaseModel` for nested sections so the outer settings class controls loading.

## 6. Secrets

Use required fields for credentials and `SecretStr` to reduce accidental
exposure in ordinary representations:

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        secrets_dir="./local-secrets",
    )

    api_key: SecretStr


settings = Settings()
print(settings.api_key)  # **********
# Pass settings.api_key.get_secret_value() only to the client that needs it.
```

For this example, create `local-secrets/APP_API_KEY` containing a local practice
value. A mounted secrets directory works the same way; configure its actual
path in deployment. Environment and dotenv values outrank secret files.

`SecretStr` masks output; it does not encrypt the value. Keep real `.env` and
secret files out of version control, commit a placeholder `.env.example`, and
avoid dumping entire settings objects into logs.

## 7. Custom sources

Suppose an application ships a non-secret JSON file while deployments retain
environment overrides. Register the file source explicitly:

```python
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        json_file="config.json",
    )
    port: int = 8000

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            JsonConfigSettingsSource(settings_cls),
        )


print(Settings().port)
```

Create `config.json` with `{"port": 8100}`. Running `python settings.py` prints
`8100`; `APP_PORT=8200 python settings.py` prints `8200`.

The returned tuple runs from highest to lowest priority; field defaults remain
the fallback. Setting `json_file` alone does not register the JSON source. TOML
and YAML sources follow a similar registration pattern; YAML requires the
optional dependency installed with `pip install 'pydantic-settings[yaml]'`.

## 8. Command-line settings

Small scripts can reuse settings validation for CLI arguments:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(cli_parse_args=True)
    port: int = 8000
    debug: bool = False


settings = Settings()
print(settings.port, settings.debug)
```

```bash
python settings.py --port 9000 --debug true
python settings.py --help
```

By default, booleans take a value. Enable `cli_implicit_flags=True` for flag
syntax such as `--debug` and `--no-debug`. Enable argument parsing at the script
entry point; parsing process arguments in a reusable library can interfere with
its host application's CLI or test runner.

## 9. Application lifecycle and testing

Construct settings during application startup so invalid configuration fails
early. A small cached provider avoids repeated file reads:

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_")
    port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Settings are snapshots, not live watchers. Changing the environment does not
update an existing instance. The cache is per process and shares the same
instance among callers; avoid mutating it. Reconstruct settings when an explicit
reload is needed.

With `pytest` installed, test the loading behavior using its `monkeypatch`
fixture. Put the provider above in `settings.py` and this in `test_settings.py`:

```python
from settings import Settings, get_settings


def test_environment_port(monkeypatch):
    monkeypatch.setenv("APP_PORT", "9123")
    assert Settings(_env_file=None).port == 9123


def test_cached_settings_reload(monkeypatch):
    get_settings.cache_clear()
    try:
        monkeypatch.setenv("APP_PORT", "9123")
        first = get_settings()
        monkeypatch.setenv("APP_PORT", "9234")
        assert get_settings() is first
        get_settings.cache_clear()
        assert get_settings().port == 9234
    finally:
        get_settings.cache_clear()
```

`_env_file=None` disables dotenv only; it does not isolate process environment
variables or other configured sources. Control those separately in tests.

## 10. Troubleshooting and practice

| Symptom | Check |
| --- | --- |
| `BaseSettings` import error | Import it from `pydantic_settings`, not `pydantic`. |
| Required field missing | Check the prefix, alias, working directory, and active environment. |
| Dotenv extra input error | Declare the entry, remove it, or deliberately use `extra="ignore"`. |
| List fails to load | Supply a JSON array with correct shell quoting. |
| Nested value stays at default | Check `env_nested_delimiter` and the full variable name. |
| Updated environment has no effect | Rebuild the instance and clear any provider cache. |

Practice in stages:

1. Load a port and debug flag from the environment.
2. Add `.env` and demonstrate each source overriding the next.
3. Reject a port outside `1..65535` and production debug mode.
4. Override a database host and port with nested variables.
5. Load a required secret from a file without printing its raw value.
6. Add JSON defaults, then verify environment overrides still win.
7. Add a CLI and tests that demonstrate cache reload behavior.

For deeper reference, consult the [Pydantic Settings documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
and the [settings API](https://docs.pydantic.dev/latest/api/pydantic_settings/).
