"""Logging configuration for the FinAlly backend.

Format: `<ISO UTC timestamp> <level> <logger> <message>`. Single line, plain
text — Docker captures stdout, no JSON wrapping needed at this scale.

Level: INFO by default; DEBUG when the `LOG_LEVEL` env var is set to
"debug" (case-insensitive).
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone


class _UtcIsoFormatter(logging.Formatter):
    """Formatter that emits a ISO 8601 UTC timestamp with millisecond precision."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: N802 - logging API
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        # Always use millisecond precision so log lines line up visually.
        return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{int(dt.microsecond / 1000):03d}Z"


def configure_logging() -> None:
    """Configure the root logger. Safe to call multiple times.

    The function is idempotent: it removes any handlers previously attached
    to the root logger and installs a single stdout handler with our format.
    """
    level_name = os.environ.get("LOG_LEVEL", "").strip().lower()
    level = logging.DEBUG if level_name == "debug" else logging.INFO

    root = logging.getLogger()
    root.setLevel(level)

    # Drop any pre-existing handlers (e.g. when uvicorn imports the app twice
    # during reload). We re-add our own to keep the output consistent.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(
        _UtcIsoFormatter(fmt="%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root.addHandler(handler)

    # Quiet a couple of noisy libraries unless we're explicitly in DEBUG.
    if level == logging.INFO:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
