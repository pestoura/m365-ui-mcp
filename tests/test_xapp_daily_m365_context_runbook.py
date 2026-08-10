from m365_mcp.application_registry import ApplicationState
from m365_mcp.apps.outlook.manifest import foundation_manifest
from m365_mcp.tool_registry import default_tool_registry
from m365_mcp.xapp_daily_m365_context_runbook import build_daily_m365_context_runbook
from m365_mcp.xapp_runbook_serialization import canonical_runbook_digest


def test_daily_m365_context_runbook_is_deterministic_and_non_executing() -> None:
    first = build_daily_m365_context_runbook()
    second = build_daily_m365_context_runbook()

    assert first.definition_reference_id == second.definition_reference_id
    assert first.definition_reference_id == canonical_runbook_digest(first.runbook)
    assert first.execution_performed is False
    assert first.outlook_live_observed is False
    assert tuple(node.node_id for node in first.runbook.nodes) == (
        "planner-context",
        "outlook-context",
        "daily-context",
    )
    assert first.runbook.nodes[-1].depends_on == (
        "outlook-context",
        "planner-context",
    )
    assert all("://" not in node.tool_name for node in first.runbook.nodes)


def test_outlook_boundary_remains_reserved_and_private() -> None:
    manifest = foundation_manifest()
    assert manifest.state is ApplicationState.RESERVED
    assert manifest.public_tools_enabled is False
    assert manifest.browser_operations_enabled is False
    assert default_tool_registry().by_application("outlook") == ()
