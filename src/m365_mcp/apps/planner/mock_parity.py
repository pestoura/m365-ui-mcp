"""Planner mock parity normalization for PLN-MIG-008.

The parity contract compares *normalized* Planner mock outputs against a frozen
canonical baseline so the platform extraction cannot silently change any
preserved Planner semantic response for an unchanged contract.

Normalization removes only values that are legitimately non-deterministic
between two identical mock executions (timestamps, durations, absolute paths and
generated identifiers). It never removes semantic payload, never removes
governance flags and never converts a mock result into a live-support claim.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Any

VOLATILE_KEYS: frozenset[str] = frozenset(
    {
        "expires_at",
        "generated_at",
        "timestamp",
        "ts",
        "duration_s",
        "duration_ms",
        "started_at",
        "completed_at",
        "operation_id",
    }
)

VOLATILE_PLACEHOLDER = "[VOLATILE]"


def normalize(value: Any) -> Any:
    """Return a deterministic projection of one mock tool payload."""
    if isinstance(value, Mapping):
        return {
            key: (VOLATILE_PLACEHOLDER if key in VOLATILE_KEYS else normalize(item))
            for key, item in sorted(value.items())
        }
    if isinstance(value, (str, bytes)):
        return value
    if isinstance(value, Sequence):
        return [normalize(item) for item in value]
    return value


def normalize_envelope(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize one full Planner tool envelope."""
    normalized = normalize(envelope)
    if not isinstance(normalized, dict):  # pragma: no cover - defensive
        raise TypeError("planner tool envelope must normalize to a mapping")
    return normalized


def parity_snapshot(results: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Normalize an ordered ``tool name -> envelope`` mapping."""
    return {name: normalize_envelope(envelope) for name, envelope in results.items()}


def parity_digest(snapshot: Mapping[str, Any]) -> str:
    """Return a stable digest for a normalized parity snapshot."""
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    return f"sha256:{sha256(payload.encode('utf-8')).hexdigest()}"


__all__ = [
    "VOLATILE_KEYS",
    "VOLATILE_PLACEHOLDER",
    "normalize",
    "normalize_envelope",
    "parity_digest",
    "parity_snapshot",
]
