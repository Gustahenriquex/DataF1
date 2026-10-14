from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from f1i.config import PROJECT_ROOT, get_settings


@pytest.mark.integration
@pytest.mark.usefixtures("live_settings")
def test_dashboard_renders_without_exceptions() -> None:
    get_settings.cache_clear()  # pick up the live configuration
    at = AppTest.from_file(str(PROJECT_ROOT / "app" / "streamlit_app.py"), default_timeout=60)

    at.run()

    assert not at.exception, [e.value for e in at.exception]
