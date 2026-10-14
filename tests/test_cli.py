from __future__ import annotations

import pytest
from typer.testing import CliRunner

from f1i import __version__, cli
from f1i.config import Settings
from f1i.doctor import CheckResult, Status

runner = CliRunner()


@pytest.fixture(autouse=True)
def _use_test_settings(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: settings)


def test_version() -> None:
    result = runner.invoke(cli.app, ["--version"])

    assert result.exit_code == 0
    assert __version__ in result.output


def test_config_masks_secrets() -> None:
    result = runner.invoke(cli.app, ["config"])

    assert result.exit_code == 0
    assert "db_port" in result.output
    assert "test-password" not in result.output


@pytest.mark.parametrize(
    ("statuses", "exit_code"),
    [((Status.OK, Status.WARN), 0), ((Status.OK, Status.FAIL), 1)],
)
def test_doctor_exit_code_reflects_failures(
    monkeypatch: pytest.MonkeyPatch, statuses: tuple[Status, ...], exit_code: int
) -> None:
    fake = [CheckResult(f"check{i}", status, "detail") for i, status in enumerate(statuses)]
    monkeypatch.setattr(cli, "run_checks", lambda _settings, offline: fake)

    result = runner.invoke(cli.app, ["doctor", "--offline"])

    assert result.exit_code == exit_code
    expected_tag = "[FAIL]" if exit_code else "[WARN]"
    assert expected_tag in result.output
