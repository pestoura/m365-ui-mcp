"""Application-owned Planner semantic JSON schemas for PLN-MIG-001.

This module captures the complete current Planner public input/output schema
surface without changing public tool names or behavior. PLN-MIG-002 can move
Tool Registry ownership onto the Planner application module using this exact
catalog rather than re-declaring schemas in the generic core.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from m365_mcp.version import PRODUCT_VERSION


@dataclass(frozen=True)
class PlannerSemanticSchema:
    """One Planner public tool's bounded semantic input/output schemas."""

    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


def empty_input_schema() -> dict[str, Any]:
    """Return a fresh empty-object input schema."""
    return {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }


def id_input_schema(field: str) -> dict[str, Any]:
    """Return a fresh single opaque identifier input schema."""
    if field not in {"plan_id", "task_id"}:
        raise ValueError(f"unsupported Planner identifier field: {field}")
    return {
        "type": "object",
        "properties": {field: {"type": "string", "minLength": 1}},
        "required": [field],
        "additionalProperties": False,
    }


def common_read_output_schema() -> dict[str, Any]:
    """Return the current Planner read envelope schema as a fresh object."""
    return {
        "type": "object",
        "required": [
            "tool",
            "product_version",
            "contract_version",
            "schema_version",
            "read_only",
            "graph_api_used",
            "data",
        ],
        "properties": {
            "tool": {"type": "string"},
            "product_version": {"const": PRODUCT_VERSION},
            "contract_version": {"const": PRODUCT_VERSION},
            "schema_version": {"const": PRODUCT_VERSION},
            "read_only": {"const": True},
            "graph_api_used": {"const": False},
            "data": {},
        },
        "additionalProperties": True,
    }


_EMPTY_INPUT_TOOLS = (
    "planner_health",
    "planner_readiness",
    "planner_capabilities",
    "planner_agent_card",
    "planner_ui_contract_status",
    "planner_auth_status",
    "planner_auth_start",
    "planner_auth_resume",
    "planner_auth_session_info",
    "planner_plan_list",
    "planner_account_context",
    "planner_license_capabilities",
    "planner_smoke_test",
)

_PLAN_ID_TOOLS = (
    "planner_plan_get",
    "planner_task_list",
    "planner_project_snapshot",
)

_TASK_ID_TOOLS = ("planner_task_get",)


def planner_semantic_schemas() -> dict[str, PlannerSemanticSchema]:
    """Return the complete 17-tool Planner schema catalog in canonical order."""
    catalog: dict[str, PlannerSemanticSchema] = {}

    for name in _EMPTY_INPUT_TOOLS:
        catalog[name] = PlannerSemanticSchema(
            input_schema=empty_input_schema(),
            output_schema=common_read_output_schema(),
        )

    for name in _PLAN_ID_TOOLS:
        catalog[name] = PlannerSemanticSchema(
            input_schema=id_input_schema("plan_id"),
            output_schema=common_read_output_schema(),
        )

    for name in _TASK_ID_TOOLS:
        catalog[name] = PlannerSemanticSchema(
            input_schema=id_input_schema("task_id"),
            output_schema=common_read_output_schema(),
        )

    return deepcopy(catalog)


__all__ = [
    "PlannerSemanticSchema",
    "common_read_output_schema",
    "empty_input_schema",
    "id_input_schema",
    "planner_semantic_schemas",
]
