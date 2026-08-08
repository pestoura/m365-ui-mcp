"""Structured JSON logging with redaction."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from .redaction import redact

_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__)


class JsonFormatter(logging.Formatter):
    """Emit one redacted JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_type"] = getattr(record.exc_info[0], "__name__", "Exception")
        return json.dumps(redact(payload), default=str, sort_keys=True)


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON handler on the root logger (idempotent)."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
