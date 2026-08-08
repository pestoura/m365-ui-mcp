"""Redaction and structured logging tests."""

from __future__ import annotations

import json
import logging

from planner_mcp.logging_setup import JsonFormatter
from planner_mcp.redaction import REDACTED, redact


def test_redacts_sensitive_keys() -> None:
    out = redact({"password": "hunter2", "cookie": "abc", "nested": {"token": "x"}})
    assert out["password"] == REDACTED
    assert out["cookie"] == REDACTED
    assert out["nested"]["token"] == REDACTED


def test_redacts_jwt_and_email() -> None:
    text = "bearer eyJhbGciOi.eyJzdWIiOm.Sflkxwsd for user someone@example.com"
    out = redact(text)
    assert "example.com" not in out
    assert "eyJhbGciOi" not in out


def test_json_formatter_redacts() -> None:
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "hello", None, None)
    record.token = "supersecret"  # type: ignore[attr-defined]  # noqa: S105
    payload = json.loads(JsonFormatter().format(record))
    assert payload["token"] == REDACTED
    assert payload["level"] == "INFO"
