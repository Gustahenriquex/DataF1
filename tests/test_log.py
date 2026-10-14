from __future__ import annotations

import json
import logging

from f1i.config import Settings
from f1i.log import _OWNED_MARKER, LOG_FILE_NAME, JsonFormatter, configure_logging


def _owned_handlers() -> list[logging.Handler]:
    return [h for h in logging.getLogger().handlers if getattr(h, _OWNED_MARKER, False)]


def test_json_formatter_keeps_extra_fields() -> None:
    record = logging.LogRecord("f1i.test", logging.INFO, __file__, 1, "loaded %d rows", (42,), None)
    record.season = 2025

    payload = json.loads(JsonFormatter().format(record))

    assert payload["msg"] == "loaded 42 rows"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "f1i.test"
    assert payload["season"] == 2025


def test_configure_logging_is_idempotent(settings: Settings) -> None:
    configure_logging(settings)
    configure_logging(settings)

    assert len(_owned_handlers()) == 2  # console + file, not duplicated


def test_log_file_is_json_lines(settings: Settings) -> None:
    configure_logging(settings)

    logging.getLogger("f1i.test").info("ingest finished", extra={"rows": 7})
    for handler in _owned_handlers():
        handler.flush()

    last_line = (settings.log_dir / LOG_FILE_NAME).read_text(encoding="utf-8").splitlines()[-1]
    payload = json.loads(last_line)
    assert payload["msg"] == "ingest finished"
    assert payload["rows"] == 7


def test_file_logging_can_be_disabled(settings: Settings) -> None:
    configure_logging(settings, log_to_file=False)

    assert len(_owned_handlers()) == 1
    assert not (settings.log_dir / LOG_FILE_NAME).exists()
