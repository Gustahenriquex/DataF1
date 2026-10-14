"""Environment health checks behind `f1i doctor`.

Each check returns a `CheckResult` instead of raising, so the CLI can print a
full report and a failing database does not hide a full disk.
"""

from __future__ import annotations

import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import NamedTuple

import httpx
from sqlalchemy import create_engine, text

from f1i.config import PROJECT_ROOT, Settings

MIN_PYTHON = (3, 12)
KEY_PACKAGES = ("fastf1", "pandas", "sqlalchemy", "psycopg", "dbt-core", "streamlit")
DISK_WARN_BELOW_GB = 10.0
DISK_FAIL_BELOW_GB = 2.0


class Status(StrEnum):
    OK = "OK"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: Status
    detail: str


class _DiskUsage(NamedTuple):
    total: int
    used: int
    free: int


def check_python(version_info: tuple[int, int, int] | None = None) -> CheckResult:
    version_info = version_info or sys.version_info[:3]
    found = ".".join(map(str, version_info))
    if version_info[:2] >= MIN_PYTHON:
        return CheckResult("python", Status.OK, f"Python {found}")
    wanted = ".".join(map(str, MIN_PYTHON))
    return CheckResult("python", Status.FAIL, f"Python {found} found, >= {wanted} required")


def check_packages(packages: tuple[str, ...] = KEY_PACKAGES) -> CheckResult:
    found, missing = [], []
    for name in packages:
        try:
            found.append(f"{name} {version(name)}")
        except PackageNotFoundError:
            missing.append(name)
    if missing:
        return CheckResult(
            "packages", Status.FAIL, f"missing: {', '.join(missing)} (run `uv sync`)"
        )
    return CheckResult("packages", Status.OK, ", ".join(found))


def check_writable_dir(name: str, path: Path) -> CheckResult:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return CheckResult(name, Status.FAIL, f"{path} is not writable: {exc}")
    return CheckResult(name, Status.OK, str(path))


def check_disk_space(
    path: Path,
    *,
    warn_below_gb: float = DISK_WARN_BELOW_GB,
    fail_below_gb: float = DISK_FAIL_BELOW_GB,
    usage_fn: Callable[[Path], _DiskUsage] = shutil.disk_usage,
) -> CheckResult:
    existing = next(p for p in (path, *path.parents) if p.exists())
    usage = usage_fn(existing)
    free_gb = usage.free / 1024**3
    pct_used = 100 * usage.used / usage.total if usage.total else 0.0
    detail = f"{free_gb:.1f} GB free ({pct_used:.0f}% used) on {existing.anchor or existing}"
    if free_gb < fail_below_gb:
        return CheckResult("disk", Status.FAIL, detail)
    if free_gb < warn_below_gb:
        return CheckResult(
            "disk", Status.WARN, f"{detail}; a multi-season FastF1 cache needs several GB"
        )
    return CheckResult("disk", Status.OK, detail)


def check_database(settings: Settings, *, connect_timeout_s: int = 3) -> CheckResult:
    if not settings.db_password.get_secret_value():
        return CheckResult("postgres", Status.FAIL, "F1I_DB_PASSWORD is not set (see .env.example)")
    engine = create_engine(
        settings.database_url, connect_args={"connect_timeout": connect_timeout_s}
    )
    try:
        with engine.connect() as conn:
            server_version = conn.execute(text("SHOW server_version")).scalar_one()
    except Exception as exc:  # report any driver/network error instead of crashing
        reason = str(exc).splitlines()[0][:160]
        return CheckResult(
            "postgres",
            Status.FAIL,
            f"cannot connect to {settings.database_url}: {reason} "
            "(start it with `docker compose up -d postgres`)",
        )
    finally:
        engine.dispose()
    return CheckResult(
        "postgres", Status.OK, f"PostgreSQL {server_version} at {settings.database_url}"
    )


def check_jolpica(settings: Settings, *, client: httpx.Client | None = None) -> CheckResult:
    url = f"{settings.jolpica_base_url}/seasons/"
    owns_client = client is None
    client = client or httpx.Client(timeout=settings.http_timeout_seconds)
    try:
        response = client.get(url, params={"limit": 1})
        response.raise_for_status()
        total = response.json()["MRData"]["total"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        return CheckResult("jolpica", Status.FAIL, f"{url}: {exc}")
    finally:
        if owns_client:
            client.close()
    return CheckResult("jolpica", Status.OK, f"reachable, {total} seasons listed")


def run_checks(settings: Settings, *, offline: bool = False) -> list[CheckResult]:
    results = [
        check_python(),
        check_packages(),
        check_writable_dir("data_dir", settings.data_dir),
        check_writable_dir("fastf1_cache", settings.fastf1_cache_path),
        check_disk_space(settings.data_dir if settings.data_dir.exists() else PROJECT_ROOT),
        check_database(settings),
    ]
    if not offline:
        results.append(check_jolpica(settings))
    return results
