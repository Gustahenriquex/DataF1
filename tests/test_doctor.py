from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from f1i.config import Settings
from f1i.doctor import (
    Status,
    _DiskUsage,
    check_database,
    check_disk_space,
    check_jolpica,
    check_packages,
    check_python,
    check_writable_dir,
)

GB = 1024**3


@pytest.mark.parametrize(
    ("version", "expected"),
    [((3, 11, 9), Status.FAIL), ((3, 12, 0), Status.OK), ((3, 13, 2), Status.OK)],
)
def test_check_python(version: tuple[int, int, int], expected: Status) -> None:
    assert check_python(version).status is expected


def test_check_packages_reports_missing() -> None:
    result = check_packages(("pytest", "surely-not-installed-package"))

    assert result.status is Status.FAIL
    assert "surely-not-installed-package" in result.detail


def test_check_packages_lists_versions() -> None:
    result = check_packages(("pytest",))

    assert result.status is Status.OK
    assert result.detail.startswith("pytest ")


def test_check_writable_dir_creates_missing_directory(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "dir"

    assert check_writable_dir("data_dir", target).status is Status.OK
    assert target.is_dir()
    assert list(target.iterdir()) == []  # probe file cleaned up


@pytest.mark.parametrize(
    ("free_gb", "expected"), [(1, Status.FAIL), (5, Status.WARN), (50, Status.OK)]
)
def test_check_disk_space_thresholds(tmp_path: Path, free_gb: int, expected: Status) -> None:
    def fake_usage(_: Path) -> _DiskUsage:
        return _DiskUsage(total=100 * GB, used=(100 - free_gb) * GB, free=free_gb * GB)

    result = check_disk_space(tmp_path / "not" / "created", usage_fn=fake_usage)

    assert result.status is expected


def test_check_database_requires_password(settings: Settings) -> None:
    no_password = settings.model_copy(update={"db_password": SecretStr("")})

    result = check_database(no_password)

    assert result.status is Status.FAIL
    assert "F1I_DB_PASSWORD" in result.detail


def test_check_database_reports_unreachable_server(settings: Settings) -> None:
    unreachable = settings.model_copy(update={"db_host": "127.0.0.1", "db_port": 1})

    result = check_database(unreachable, connect_timeout_s=2)

    assert result.status is Status.FAIL
    assert "cannot connect" in result.detail
    assert "test-password" not in result.detail


@pytest.mark.integration
def test_check_database_live(live_settings: Settings) -> None:
    result = check_database(live_settings)

    assert result.status is Status.OK, result.detail
    assert result.detail.startswith("PostgreSQL ")


def _client(transport: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(transport=transport)


def test_check_jolpica_ok(settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/ergast/f1/seasons/"
        return httpx.Response(200, json={"MRData": {"total": "77"}})

    result = check_jolpica(settings, client=_client(httpx.MockTransport(handler)))

    assert result.status is Status.OK
    assert "77 seasons" in result.detail


@pytest.mark.parametrize(
    "response",
    [httpx.Response(503, text="maintenance"), httpx.Response(200, json={"unexpected": 1})],
)
def test_check_jolpica_failures(settings: Settings, response: httpx.Response) -> None:
    transport = httpx.MockTransport(lambda _request: response)

    assert check_jolpica(settings, client=_client(transport)).status is Status.FAIL


@pytest.mark.network
def test_check_jolpica_live(live_settings: Settings) -> None:
    result = check_jolpica(live_settings)

    assert result.status is Status.OK, result.detail
