"""Desired-state reconciliation primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DesiredResource:
    """A desired resource keyed by a stable external id."""

    external_id: str
    kind: str
    spec: dict[str, Any]
    source_id: str | None = None


@dataclass(frozen=True)
class Diff:
    """The difference between desired and observed state."""

    external_id: str
    action: str
    fields: dict[str, Any]


def diff(desired: DesiredResource, observed: dict[str, Any] | None) -> Diff | None:
    """Compute a minimal diff. Returns None when already converged."""
    if observed is None:
        return Diff(desired.external_id, "create", dict(desired.spec))
    changed = {k: v for k, v in desired.spec.items() if observed.get(k) != v}
    if not changed:
        return None
    return Diff(desired.external_id, "update", changed)
