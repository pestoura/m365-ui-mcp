from m365_mcp.application_registry import ApplicationState
from m365_mcp.apps.outlook.manifest import foundation_manifest
from m365_mcp.tool_registry import default_tool_registry
from m365_mcp.xapp_meeting_preparation_runbook import build_meeting_preparation_runbook
from m365_mcp.xapp_runbook_serialization import canonical_runbook_digest


def test_meeting_preparation_runbook_is_deterministic_and_non_executing() -> None:
    first = build_meeting_preparation_runbook()
    second = build_meeting_preparation_runbook()

    assert first.definition_reference_id == second.definition_reference_id
    assert first.definition_reference_id == canonical_runbook_digest(first.runbook)
    assert first.execution_performed is False
    assert tuple(node.node_id for node in first.runbook.nodes) == (
        "project-context",
        "person-context",
        "daily-work-context",
        "meeting-brief",
    )
    assert all("://" not in node.tool_name for node in first.runbook.nodes)


def test_outlook_boundary_remains_reserved_and_private() -> None:
    assert foundation_manifest().state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
