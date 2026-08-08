"""Planner-owned Tool Registry definitions for PLN-MIG-002."""

from __future__ import annotations

from m365_mcp.application_registry import ApplicationKey
from m365_mcp.apps.planner.schemas import PlannerSemanticSchema, planner_semantic_schemas
from m365_mcp.tool_registry import (
    CompatibilityRequirement,
    ImplementationState,
    MutationClass,
    ToolDefinition,
)
from m365_mcp.version import PRODUCT_VERSION

_PLANNER_CAPABILITY_KEYS = (
    "plans.read",
    "tasks.read",
    "buckets.read",
    "dependencies.read",
    "scheduling.read",
    "goals.read",
    "sprints.read",
    "resources.read",
    "custom_fields.read",
    "portfolios.read",
    "project_snapshot.read",
)


def _read_tool(
    schemas: dict[str, PlannerSemanticSchema],
    name: str,
    *,
    surface: str,
    domain: str,
    risk_class: str,
    implementation_state: ImplementationState,
    capability_keys: tuple[str, ...] = (),
    ui_contract_dependencies: tuple[str, ...] = (),
    read_back_strategy: str = "NONE_READ_ONLY",
    idempotency_semantics: str = "naturally_idempotent",
) -> ToolDefinition:
    schema = schemas[name]
    return ToolDefinition(
        name=name,
        version=PRODUCT_VERSION,
        application=ApplicationKey.PLANNER.value,
        surface=surface,
        domain=domain,
        input_schema=schema.input_schema,
        output_schema=schema.output_schema,
        mutation_class=MutationClass.READ,
        risk_class=risk_class,
        implementation_state=implementation_state,
        capability_keys=capability_keys,
        ui_contract_dependencies=ui_contract_dependencies,
        read_back_strategy=read_back_strategy,
        idempotency_semantics=idempotency_semantics,
        approval_requirement="none",
        compatibility_requirement=CompatibilityRequirement.PRESERVE,
    )


def planner_tool_definitions() -> tuple[ToolDefinition, ...]:
    """Return all 17 preserved Planner definitions in canonical public order."""
    schemas = planner_semantic_schemas()
    return (
        _read_tool(
            schemas,
            "planner_health",
            surface="control_plane",
            domain="system",
            risk_class="READ_ONLY",
            implementation_state=ImplementationState.IMPLEMENTED_NOT_ATTESTED,
        ),
        _read_tool(
            schemas,
            "planner_readiness",
            surface="control_plane",
            domain="system",
            risk_class="READ_ONLY",
            implementation_state=ImplementationState.IMPLEMENTED_NOT_ATTESTED,
            ui_contract_dependencies=("GLOBAL_UI_CONTRACT_ATTESTATION",),
        ),
        _read_tool(
            schemas,
            "planner_capabilities",
            surface="capability",
            domain="capability",
            risk_class="READ_ONLY",
            implementation_state=ImplementationState.IMPLEMENTED_MOCK_ONLY,
            capability_keys=_PLANNER_CAPABILITY_KEYS,
            ui_contract_dependencies=("GLOBAL_UI_CONTRACT_ATTESTATION",),
        ),
        _read_tool(
            schemas,
            "planner_agent_card",
            surface="control_plane",
            domain="system",
            risk_class="READ_ONLY",
            implementation_state=ImplementationState.IMPLEMENTED_NOT_ATTESTED,
        ),
        _read_tool(
            schemas,
            "planner_ui_contract_status",
            surface="ui_contract",
            domain="ui_contract",
            risk_class="READ_ONLY",
            implementation_state=ImplementationState.IMPLEMENTED_NOT_ATTESTED,
            ui_contract_dependencies=("GLOBAL_UI_CONTRACT_ATTESTATION",),
        ),
        _read_tool(
            schemas,
            "planner_auth_status",
            surface="browser_auth",
            domain="auth",
            risk_class="SESSION_OBSERVATION",
            implementation_state=ImplementationState.IMPLEMENTED_MOCK_ONLY,
            ui_contract_dependencies=("auth.login_email_input", "auth.mfa_number_display"),
        ),
        _read_tool(
            schemas,
            "planner_auth_start",
            surface="browser_auth",
            domain="auth",
            risk_class="SESSION_INTERACTION",
            implementation_state=ImplementationState.IMPLEMENTED_MOCK_ONLY,
            ui_contract_dependencies=("auth.login_email_input", "auth.mfa_number_display"),
            read_back_strategy="AUTH_STATE_RE_READ",
            idempotency_semantics="key_required",
        ),
        _read_tool(
            schemas,
            "planner_auth_resume",
            surface="browser_auth",
            domain="auth",
            risk_class="SESSION_INTERACTION",
            implementation_state=ImplementationState.IMPLEMENTED_MOCK_ONLY,
            ui_contract_dependencies=("auth.mfa_number_display",),
            read_back_strategy="AUTH_STATE_RE_READ",
        ),
        _read_tool(
            schemas,
            "planner_auth_session_info",
            surface="browser_auth",
            domain="auth",
            risk_class="SESSION_METADATA",
            implementation_state=ImplementationState.IMPLEMENTED_NOT_ATTESTED,
        ),
        _read_tool(
            schemas,
            "planner_plan_list",
            surface="planner_web",
            domain="planner",
            risk_class="M365_CONTENT_READ",
            implementation_state=ImplementationState.IMPLEMENTED_MOCK_ONLY,
            capability_keys=("plans.read",),
            ui_contract_dependencies=("plan.list_container", "plan.list_item", "plan.title"),
        ),
        _read_tool(
            schemas,
            "planner_plan_get",
            surface="planner_web",
            domain="planner",
            risk_class="M365_CONTENT_READ",
            implementation_state=ImplementationState.IMPLEMENTED_MOCK_ONLY,
            capability_keys=("plans.read",),
            ui_contract_dependencies=("plan.list_item", "plan.title"),
        ),
        _read_tool(
            schemas,
            "planner_task_list",
            surface="planner_web",
            domain="planner",
            risk_class="M365_CONTENT_READ",
            implementation_state=ImplementationState.IMPLEMENTED_MOCK_ONLY,
            capability_keys=("tasks.read",),
            ui_contract_dependencies=(
                "task.list_container",
                "task.list_item",
                "task.title",
                "task.bucket",
            ),
        ),
        _read_tool(
            schemas,
            "planner_task_get",
            surface="planner_web",
            domain="planner",
            risk_class="M365_CONTENT_READ",
            implementation_state=ImplementationState.IMPLEMENTED_MOCK_ONLY,
            capability_keys=("tasks.read",),
            ui_contract_dependencies=("task.list_item", "task.title", "task.bucket"),
        ),
        _read_tool(
            schemas,
            "planner_project_snapshot",
            surface="planner_web",
            domain="planner",
            risk_class="M365_CONTENT_READ",
            implementation_state=ImplementationState.IMPLEMENTED_MOCK_ONLY,
            capability_keys=("project_snapshot.read", "plans.read", "tasks.read"),
            ui_contract_dependencies=(
                "plan.title",
                "task.list_container",
                "task.list_item",
                "task.title",
                "task.bucket",
            ),
        ),
        _read_tool(
            schemas,
            "planner_account_context",
            surface="browser_account",
            domain="auth",
            risk_class="ACCOUNT_CONTEXT_READ",
            implementation_state=ImplementationState.IMPLEMENTED_MOCK_ONLY,
            ui_contract_dependencies=("account.context_menu",),
        ),
        _read_tool(
            schemas,
            "planner_license_capabilities",
            surface="capability",
            domain="capability",
            risk_class="ACCOUNT_CONTEXT_READ",
            implementation_state=ImplementationState.IMPLEMENTED_MOCK_ONLY,
            capability_keys=_PLANNER_CAPABILITY_KEYS,
            ui_contract_dependencies=("GLOBAL_UI_CONTRACT_ATTESTATION",),
        ),
        _read_tool(
            schemas,
            "planner_smoke_test",
            surface="control_plane",
            domain="system",
            risk_class="READ_ONLY",
            implementation_state=ImplementationState.IMPLEMENTED_MOCK_ONLY,
            ui_contract_dependencies=("GLOBAL_UI_CONTRACT_ATTESTATION",),
        ),
    )


__all__ = ["planner_tool_definitions"]
