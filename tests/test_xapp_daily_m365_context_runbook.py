import pytest

from m365_mcp.application_registry import ApplicationState
from m365_mcp.apps.outlook.manifest import foundation_manifest
from m365_mcp.tool_registry import default_tool_registry
from m365_mcp.xapp_daily_m365_context_runbook import (
    DailyM365ContextRunbook,
    build_daily_m365_context_runbook,
)
from m365_mcp.xapp_runbook_serialization import canonical_runbook_digest


def test_daily_m365_context_runbook_is_deterministic_and_non_executing() -> None:
    first = build_daily_m365_context_runbook()
    second = build_daily_m365_context_runbook()

    assert first.definition_reference_id == second.definition_reference_id
    assert first.definition_reference_id == canonical_runbook_digest(first.runbook)
    assert first.execution_performed is False
    assert tuple(node.node_id for node in first.runbook.nodes) == (
        "project-context",
        "inbox-digest",
        "daily-work-context",
        "daily-context-projection",
    )
    assert all("://" not in node.tool_name for node in first.runbook.nodes)


def test_daily_m365_context_runbook_composes_without_new_primitives() -> None:
    runbook = build_daily_m365_context_runbook().runbook
    by_id = {node.node_id: node for node in runbook.nodes}

    assert by_id["daily-work-context"].depends_on == ("inbox-digest",)
    assert set(by_id["daily-context-projection"].depends_on) == {
        "daily-work-context",
        "project-context",
    }
    assert by_id["daily-context-projection"].input_binding_keys == (
        "project-ref",
        "digest-ref",
        "work-ref",
    )


def test_daily_m365_context_runbook_rejects_execution_and_digest_drift() -> None:
    built = build_daily_m365_context_runbook()

    with pytest.raises(ValueError):
        DailyM365ContextRunbook(
            runbook=built.runbook,
            definition_reference_id=built.definition_reference_id,
            execution_performed=True,
        )
    with pytest.raises(ValueError):
        DailyM365ContextRunbook(
            runbook=built.runbook,
            definition_reference_id="0" * 64,
        )


def test_daily_m365_context_runbook_version_changes_digest() -> None:
    assert (
        build_daily_m365_context_runbook(version="1.0.0").definition_reference_id
        != build_daily_m365_context_runbook(version="1.1.0").definition_reference_id
    )


def test_outlook_boundary_remains_reserved_and_private() -> None:
    assert foundation_manifest().state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
