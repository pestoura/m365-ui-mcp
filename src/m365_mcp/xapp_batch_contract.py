"""Bounded BATCH request contract for XAPP-002."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.application_registry import ApplicationKey

_MAX_BATCH_NODES = 50
_MAX_REFERENCES = 32


def _token(field: str, value: str) -> None:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{field} must be a non-empty semantic token")
    if "://" in value:
        raise ValueError(f"{field} must not encode a URL")


@dataclass(frozen=True)
class BatchOperationRequest:
    node_id: str
    application: ApplicationKey
    tool_name: str
    mutation: bool = False
    input_reference_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _token("node_id", self.node_id)
        _token("tool_name", self.tool_name)
        if len(self.input_reference_ids) > _MAX_REFERENCES:
            raise ValueError("BATCH input references exceed bounded size")
        if len(set(self.input_reference_ids)) != len(self.input_reference_ids):
            raise ValueError("BATCH input references must be unique")
        for value in self.input_reference_ids:
            _token("input_reference_id", value)


@dataclass(frozen=True)
class BatchRequest:
    batch_key: str
    nodes: tuple[BatchOperationRequest, ...]
    aggregate_authorization_available: bool = False

    def __post_init__(self) -> None:
        _token("batch_key", self.batch_key)
        if not self.nodes:
            raise ValueError("BATCH requires at least one node")
        if len(self.nodes) > _MAX_BATCH_NODES:
            raise ValueError("BATCH exceeds bounded node count")
        node_ids = tuple(node.node_id for node in self.nodes)
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("BATCH node ids must be unique")
        if self.aggregate_authorization_available:
            raise ValueError("BATCH cannot use aggregate authorization")

    def to_projection(self) -> dict[str, object]:
        return {
            "batch_key": self.batch_key,
            "node_count": len(self.nodes),
            "node_ids": tuple(node.node_id for node in self.nodes),
            "aggregate_authorization_available": False,
        }


__all__ = ["BatchOperationRequest", "BatchRequest"]
