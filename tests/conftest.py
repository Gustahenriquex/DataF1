from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from f1i.config import Settings, get_settings
from f1i.log import _OWNED_MARKER

# Captured before any test strips them; used only by `live_settings`.
_REAL_F1I_ENV = {key: value for key, value in os.environ.items() if key.startswith("F1I_")}


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep the developer's F1I_* variables and logging handlers out of every test."""
    for key in list(os.environ):
        if key.startswith("F1I_"):
            monkeypatch.delenv(key)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, _OWNED_MARKER, False):
            root.removeHandler(handler)
            handler.close()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Settings that never read `.env` and write only inside a temp directory."""
    return Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        log_dir=tmp_path / "logs",
        db_password="test-password",
    )


@pytest.fixture
def live_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """The real configuration (environment + `.env`), for integration/network tests."""
    for key, value in _REAL_F1I_ENV.items():
        monkeypatch.setenv(key, value)
    return Settings()
