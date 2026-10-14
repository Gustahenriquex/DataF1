"""Logging setup: readable (or JSON) console output plus a rotating JSON-lines file.

Usage:
    configure_logging(get_settings())
    logger = logging.getLogger(__name__)
    logger.info("loaded session", extra={"season": 2025, "round": 3, "rows": 1180})

Fields passed through `extra=` are kept as structured keys in JSON output, which
makes ingestion runs auditable (row counts, durations, parameters).
"""

from __future__ import annotations

import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from f1i.config import Settings

TEXT_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FILE_NAME = "f1i.log"

# Attributes every LogRecord has; anything else was passed via `extra=`.
_BLANK_RECORD = logging.LogRecord("", logging.INFO, "", 0, "", None, None)
_STANDARD_ATTRS = frozenset(_BLANK_RECORD.__dict__) | {"message", "asctime"}

# Marks handlers we own, so reconfiguring never removes handlers added by others
# (e.g. pytest's caplog) and never duplicates ours.
_OWNED_MARKER = "_f1i_owned"

_NOISY_LOGGERS = ("httpx", "httpcore", "urllib3", "requests_cache", "matplotlib")


class JsonFormatter(logging.Formatter):
    """One JSON object per line, including any `extra=` fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(settings: Settings, *, log_to_file: bool = True) -> None:
    """Install console (+ optional file) handlers on the root logger. Idempotent."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, _OWNED_MARKER, False):
            root.removeHandler(handler)
            handler.close()

    console = logging.StreamHandler(sys.stderr)
    text_formatter = logging.Formatter(TEXT_FORMAT, DATE_FORMAT)
    console.setFormatter(JsonFormatter() if settings.log_format == "json" else text_formatter)
    handlers: list[logging.Handler] = [console]

    if log_to_file:
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            settings.log_dir / LOG_FILE_NAME, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(JsonFormatter())
        handlers.append(file_handler)

    for handler in handlers:
        setattr(handler, _OWNED_MARKER, True)
        root.addHandler(handler)
    root.setLevel(settings.log_level)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
