"""Canonical runbook serialization and digest for XAPP-012.

Only semantic node metadata is serializable. No callable, code, browser
primitive, selector, URL, secret, or arbitrary execution payload is accepted.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

_MAX_NODES = 100
_MAX_BINDINGS = 100


def _token(field: str, value: str) -> None:
    invalid = (
        not value
        or value != value.strip()
        or any(char.isspace() for char in value)
        or "://" in value
    )
    if invalid:
        raise ValueError(f"{field} must be a non-empty semantic token")


@dataclass(frozen=True)
class CanonicalRunbookNode:
    node_id: str
    tool_name: str
    depends_on: tuple[str, ...] = ()
    input_binding_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _token("node_id", self.node_id)
        _token("tool_name", self.tool_name)
        if self.node_id in self.depends_on:
            raise ValueError("runbook node cannot depend on itself")
        if len(self.depends_on) != len(set(self.depends_on)):
            raise ValueError("runbook dependencies must be unique")
        if len(self.input_binding_keys) > _MAX_BINDINGS:
            raise ValueError("runbook input bindings exceed bounded size")
        if len(self.input_binding_keys) != len(set(self.input_binding_keys)):
            raise ValueError("runbook input binding keys must be unique")
        for value in (*self.depends_on, *self.input_binding_keys):
            _token("runbook reference", value)

    def canonical_projection(self) -> dict[str, object]:
        return {
            "node_id": self.node_id,
            "tool_name": self.tool_name,
            "depends_on": sorted(self.depends_on),
            "input_binding_keys": sorted(self.input_binding_keys),
        }


@dataclass(frozen=True)
class CanonicalRunbook:
    runbook_key: str
    version: str
    nodes: tuple[CanonicalRunbookNode, ...]

    def __post_init__(self) -> None:
        _token("runbook_key", self.runbook_key)
        _token("version", self.version)
        if not self.nodes:
            raise ValueError("runbook requires at least one node")
        if len(self.nodes) > _MAX_NODES:
            raise ValueError("runbook exceeds bounded node count")
        ids = tuple(node.node_id for node in self.nodes)
        if len(ids) != len(set(ids)):
            raise ValueError("runbook node ids must be unique")
        known = set(ids)
        for node in self.nodes:
            if set(node.depends_on) - known:
                raise ValueError("runbook dependency references unknown node")

    def canonical_projection(self) -> dict[str, object]:
        return {
            "runbook_key": self.runbook_key,
            "version": self.version,
            "nodes": [
                node.canonical_projection()
                for node in sorted(self.nodes, key=lambda item: item.node_id)
            ],
        }


def canonical_runbook_json(runbook: CanonicalRunbook) -> str:
    """Return deterministic JSON for semantic runbook metadata only."""
    return json.dumps(
        runbook.canonical_projection(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def canonical_runbook_digest(runbook: CanonicalRunbook) -> str:
    """Return lowercase SHA-256 over canonical UTF-8 runbook JSON."""
    encoded = canonical_runbook_json(runbook).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "CanonicalRunbook",
    "CanonicalRunbookNode",
    "canonical_runbook_digest",
    "canonical_runbook_json",
]
