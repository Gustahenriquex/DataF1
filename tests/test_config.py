from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from f1i.config import PROJECT_ROOT, Settings


def test_defaults(settings: Settings) -> None:
    assert settings.env == "dev"
    assert settings.db_port == 5432
    assert settings.jolpica_base_url == "https://api.jolpi.ca/ergast/f1"
    assert settings.raw_dir == settings.data_dir / "raw"
    assert settings.fastf1_cache_path == settings.data_dir / "cache" / "fastf1"


def test_environment_variables_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("F1I_DB_PORT", "6543")
    monkeypatch.setenv("F1I_JOLPICA_BASE_URL", "https://example.test/f1/")

    settings = Settings(_env_file=None)

    assert settings.db_port == 6543
    assert settings.jolpica_base_url == "https://example.test/f1"


def test_relative_paths_resolve_against_project_root() -> None:
    settings = Settings(_env_file=None, data_dir=Path("some/data"), fastf1_cache_dir=Path("c"))

    assert settings.data_dir == (PROJECT_ROOT / "some" / "data").resolve()
    assert settings.fastf1_cache_path == (PROJECT_ROOT / "c").resolve()


def test_absolute_paths_are_kept(tmp_path: Path) -> None:
    assert Settings(_env_file=None, data_dir=tmp_path).data_dir == tmp_path


def test_database_url_never_renders_the_password(settings: Settings) -> None:
    url = settings.database_url

    assert url.drivername == "postgresql+psycopg"
    assert url.password == "test-password"
    assert "test-password" not in str(url)


@pytest.mark.parametrize(
    "overrides",
    [
        {"jolpica_max_requests_per_hour": 600},
        {"jolpica_max_requests_per_second": 5},
        {"db_port": 0},
        {"log_level": "VERBOSE"},
    ],
)
def test_invalid_values_are_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **overrides)
