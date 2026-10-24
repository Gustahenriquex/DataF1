"""Prevent idle system sleep during long jobs (Windows only; no-op elsewhere).

Uses SetThreadExecutionState, which lasts only while the calling process runs and
changes no system settings. A closed laptop lid or an explicit Sleep still suspends.
"""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Iterator

_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001


@contextlib.contextmanager
def keep_awake() -> Iterator[None]:
    if sys.platform != "win32":
        yield
        return
    import ctypes

    kernel32 = ctypes.windll.kernel32
    kernel32.SetThreadExecutionState(_ES_CONTINUOUS | _ES_SYSTEM_REQUIRED)
    try:
        yield
    finally:
        kernel32.SetThreadExecutionState(_ES_CONTINUOUS)
