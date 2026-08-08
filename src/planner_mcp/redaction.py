"""Redaction helpers. Never emit secrets, cookies, tokens or passwords."""

from __future__ import annotations

import re
from typing import Any

SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "cookie",
        "cookies",
        "set-cookie",
        "authorization",
        "api_key",
        "apikey",
        "client_secret",
        "session_id",
        "storage_state",
    }
)

REDACTED = "[REDACTED]"

_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/-]{10,}"),
    re.compile(r"(?i)\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
)


def redact_text(value: str) -> str:
    """Redact obvious secret-like and identity-like substrings."""
    out = value
    for pattern in _PATTERNS:
        out = pattern.sub(REDACTED, out)
    return out


def redact(value: Any) -> Any:
    """Recursively redact a JSON-like structure."""
    if isinstance(value, dict):
        return {
            k: (REDACTED if str(k).lower() in SENSITIVE_KEYS else redact(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value
