from m365_mcp.application_registry import ApplicationKey, ApplicationState
from m365_mcp.apps.outlook.manifest import foundation_manifest
from m365_mcp.tool_registry import default_tool_registry
from m365_mcp.xapp_batch_contract import BatchOperationRequest
from m365_mcp.xapp_m365_batch import build_m365_batch_plan


def test_m365_batch_composes_planner_and_outlook_without_execution() -> None:
    nodes = (
        BatchOperationRequest(
            "planner-project",
            ApplicationKey.PLANNER,
            "planner_project_snapshot",
        ),
        BatchOperationRequest(
            "outlook-context",
            ApplicationKey.OUTLOOK,
            "xapp_outlook_daily_work_context",
        ),
    )

    plan = build_m365_batch_plan("daily-m365", nodes, max_parallel=2)

    assert plan.planner_node_count == 1
    assert plan.outlook_node_count == 1
    assert plan.schedule.node_count == 2
    assert plan.schedule.execution_performed is False
    assert plan.execution_performed is False
    assert plan.request.aggregate_authorization_available is False


def test_m365_batch_rejects_outlook_mutation_while_reserved() -> None:
    nodes = (
        BatchOperationRequest(
            "planner-project",
            ApplicationKey.PLANNER,
            "planner_project_snapshot",
        ),
        BatchOperationRequest(
            "outlook-write",
            ApplicationKey.OUTLOOK,
            "outlook_internal_mutation",
            mutation=True,
        ),
    )

    try:
        build_m365_batch_plan("unsafe-batch", nodes)
    except ValueError as exc:
        assert "non-mutating" in str(exc)
    else:
        raise AssertionError("reserved Outlook mutation must be rejected")


def test_outlook_boundary_remains_reserved_and_private() -> None:
    assert foundation_manifest().state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
