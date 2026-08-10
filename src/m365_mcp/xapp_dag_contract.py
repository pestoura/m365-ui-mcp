"""Typed bounded DAG contract for XAPP-005."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.application_registry import ApplicationKey

_MAX_DAG_NODES = 100


def _token(field: str, value: str) -> None:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{field} must be a non-empty semantic token")
    if "://" in value:
        raise ValueError(f"{field} must not encode a URL")


@dataclass(frozen=True)
class DagOperationNode:
    node_id: str
    application: ApplicationKey
    tool_name: str
    depends_on: tuple[str, ...] = ()
    mutation: bool = False

    def __post_init__(self) -> None:
        _token("node_id", self.node_id)
        _token("tool_name", self.tool_name)
        if self.node_id in self.depends_on:
            raise ValueError("DAG node cannot depend on itself")
        if len(self.depends_on) != len(set(self.depends_on)):
            raise ValueError("DAG dependencies must be unique")
        for dependency in self.depends_on:
            _token("dependency", dependency)


@dataclass(frozen=True)
class DagRequest:
    dag_key: str
    nodes: tuple[DagOperationNode, ...]
    aggregate_authorization_available: bool = False

    def __post_init__(self) -> None:
        _token("dag_key", self.dag_key)
        if not self.nodes:
            raise ValueError("DAG requires at least one node")
        if len(self.nodes) > _MAX_DAG_NODES:
            raise ValueError("DAG exceeds bounded node count")
        ids = tuple(node.node_id for node in self.nodes)
        if len(ids) != len(set(ids)):
            raise ValueError("DAG node ids must be unique")
        known = set(ids)
        for node in self.nodes:
            if set(node.depends_on) - known:
                raise ValueError("DAG dependency references unknown node")
        if self.aggregate_authorization_available:
            raise ValueError("DAG cannot use aggregate authorization")

    def to_projection(self) -> dict[str, object]:
        return {
            "dag_key": self.dag_key,
            "node_count": len(self.nodes),
            "node_ids": tuple(node.node_id for node in self.nodes),
            "aggregate_authorization_available": False,
        }


__all__ = ["DagOperationNode", "DagRequest"]
