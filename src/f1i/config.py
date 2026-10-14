"""Typed application settings.

Values come from (highest priority first): environment variables, the `.env`
file at the project root, then the defaults below. Every variable uses the
`F1I_` prefix, e.g. `F1I_DB_PORT=5433`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="F1I_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["dev", "test", "prod"] = "dev"

    # Paths
    data_dir: Path = Path("data")
    fastf1_cache_dir: Path | None = None
    log_dir: Path = Path("logs")

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["text", "json"] = "text"

    # PostgreSQL
    db_host: str = "127.0.0.1"  # not "localhost": on Windows it tries IPv6 first and stalls
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str = "f1i"
    db_user: str = "f1i"
    db_password: SecretStr = SecretStr("")

    # Jolpica-F1 (public limits: 4 req/s burst, 500 req/h sustained)
    jolpica_base_url: str = "https://api.jolpi.ca/ergast/f1"
    jolpica_max_requests_per_second: float = Field(default=3.0, gt=0, le=4)
    jolpica_max_requests_per_hour: int = Field(default=450, gt=0, le=500)
    http_timeout_seconds: float = Field(default=30.0, gt=0)

    @field_validator("data_dir", "fastf1_cache_dir", "log_dir")
    @classmethod
    def _resolve_against_project_root(cls, value: Path | None) -> Path | None:
        if value is None or value.is_absolute():
            return value
        return (PROJECT_ROOT / value).resolve()

    @field_validator("jolpica_base_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def raw_dir(self) -> Path:
        """Immutable copies of source payloads (JSON / Parquet)."""
        return self.data_dir / "raw"

    @property
    def fastf1_cache_path(self) -> Path:
        return self.fastf1_cache_dir or self.data_dir / "cache" / "fastf1"

    @property
    def database_url(self) -> URL:
        """SQLAlchemy URL; `str()` of it masks the password."""
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.db_user,
            password=self.db_password.get_secret_value() or None,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings singleton. Tests build `Settings(...)` directly instead."""
    return Settings()
