from m365_mcp.application_registry import ApplicationKey, ApplicationState
from m365_mcp.apps.outlook.manifest import foundation_manifest
from m365_mcp.tool_registry import default_tool_registry
from m365_mcp.xapp_dag_contract import DagOperationNode
from m365_mcp.xapp_m365_dag import build_m365_dag_plan


def test_m365_dag_composes_planner_and_outlook_topologically() -> None:
    nodes = (
        DagOperationNode(
            "planner-project",
            ApplicationKey.PLANNER,
            "planner_project_snapshot",
        ),
        DagOperationNode(
            "outlook-context",
            ApplicationKey.OUTLOOK,
            "xapp_outlook_daily_work_context",
        ),
        DagOperationNode(
            "combined-view",
            ApplicationKey.PLANNER,
            "planner_project_snapshot",
            depends_on=("outlook-context", "planner-project"),
        ),
    )

    plan = build_m365_dag_plan("cross-app-context", nodes, max_parallel=2)

    assert plan.planner_node_count == 2
    assert plan.outlook_node_count == 1
    assert plan.schedule.waves[0] == ("outlook-context", "planner-project")
    assert plan.schedule.waves[1] == ("combined-view",)
    assert plan.schedule.execution_performed is False
    assert plan.execution_performed is False
    assert plan.request.aggregate_authorization_available is False


def test_m365_dag_rejects_outlook_mutation_while_reserved() -> None:
    nodes = (
        DagOperationNode(
            "planner-project",
            ApplicationKey.PLANNER,
            "planner_project_snapshot",
        ),
        DagOperationNode(
            "outlook-write",
            ApplicationKey.OUTLOOK,
            "outlook_internal_mutation",
            mutation=True,
        ),
    )

    try:
        build_m365_dag_plan("unsafe-dag", nodes)
    except ValueError as exc:
        assert "non-mutating" in str(exc)
    else:
        raise AssertionError("reserved Outlook mutation must be rejected")


def test_outlook_boundary_remains_reserved_and_private() -> None:
    assert foundation_manifest().state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
