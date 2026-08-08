from __future__ import annotations

import pytest

from m365_mcp.apps.planner import id_input_schema, planner_semantic_schemas
from m365_mcp.tool_registry import default_tool_registry


def test_planner_application_schema_catalog_matches_current_public_registry() -> None:
    registry = default_tool_registry()
    current = registry.by_application("planner")
    catalog = planner_semantic_schemas()

    assert tuple(catalog) == tuple(definition.name for definition in current)
    assert len(catalog) == 17

    for definition in current:
        schema = catalog[definition.name]
        assert schema.input_schema == definition.input_schema
        assert schema.output_schema == definition.output_schema


def test_planner_schema_catalog_returns_isolated_schema_objects() -> None:
    first = planner_semantic_schemas()
    second = planner_semantic_schemas()

    first["planner_plan_list"].input_schema["properties"]["unexpected"] = {
        "type": "string"
    }
    assert "unexpected" not in second["planner_plan_list"].input_schema["properties"]


def test_planner_identifier_schema_rejects_unreviewed_identifier_kinds() -> None:
    with pytest.raises(ValueError, match="unsupported Planner identifier field"):
        id_input_schema("mailbox_id")
