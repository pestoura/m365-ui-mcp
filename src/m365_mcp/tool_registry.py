"""Canonical semantic Tool Registry for the M365 control plane.

CORE-008 establishes validated tool metadata as a product-level source of
truth. It intentionally does not perform FastMCP registration; metadata-driven
projection is introduced by CORE-009 after parity with the existing explicit
Planner wrappers is proven.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from m365_mcp.application_registry import ApplicationKey
from m365_mcp.version import PRODUCT_VERSION


class MutationClass(StrEnum):
    """Closed semantic mutation classes used by policy/execution layers."""

    READ = "READ"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    HIGH_IMPACT = "HIGH_IMPACT"


class ImplementationState(StrEnum):
    """Evidence-based implementation states required by the transition plan."""

    IMPLEMENTED_LIVE = "IMPLEMENTED_LIVE"
    IMPLEMENTED_MOCK_ONLY = "IMPLEMENTED_MOCK_ONLY"
    IMPLEMENTED_NOT_ATTESTED = "IMPLEMENTED_NOT_ATTESTED"
    SPECIFIED_ONLY = "SPECIFIED_ONLY"
    PLANNED = "PLANNED"
    DEPRECATED = "DEPRECATED"
    BLOCKED = "BLOCKED"


class CompatibilityRequirement(StrEnum):
    """Public compatibility disposition for a semantic tool."""

    PRESERVE = "PRESERVE"
    VERSION = "VERSION"
    DEPRECATE_LATER = "DEPRECATE_LATER"
    INTERNAL_ONLY = "INTERNAL_ONLY"


_EMPTY_INPUT: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "required": [],
    "additionalProperties": False,
}

_COMMON_READ_OUTPUT: dict[str, Any] = {
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


def _id_input(field: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {field: {"type": "string", "minLength": 1}},
        "required": [field],
        "additionalProperties": False,
    }


@dataclass(frozen=True)
class ToolDefinition:
    """Canonical metadata required to govern and project one semantic tool."""

    name: str
    version: str
    application: str
    surface: str
    domain: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    mutation_class: MutationClass
    risk_class: str
    implementation_state: ImplementationState
    capability_keys: tuple[str, ...]
    ui_contract_dependencies: tuple[str, ...]
    read_back_strategy: str
    idempotency_semantics: str
    approval_requirement: str
    compatibility_requirement: CompatibilityRequirement

    def __post_init__(self) -> None:
        if not self.name or not self.version:
            raise ValueError("tool name and version are required")
        if self.application == "core":
            prefix = "m365_"
        elif self.application in {key.value for key in ApplicationKey}:
            prefix = f"{self.application}_"
        else:
            raise ValueError(f"unknown tool application: {self.application}")
        if not self.name.startswith(prefix):
            raise ValueError(
                f"tool name {self.name!r} does not match application prefix {prefix!r}"
            )
        if not self.surface.strip() or not self.domain.strip() or not self.risk_class.strip():
            raise ValueError("tool surface, domain and risk class are required")
        if self.input_schema.get("type") != "object":
            raise ValueError("tool input schema must be an object schema")
        if self.output_schema.get("type") != "object":
            raise ValueError("tool output schema must be an object schema")
        if not self.read_back_strategy or not self.idempotency_semantics:
            raise ValueError("read-back and idempotency semantics are required")
        if not self.approval_requirement:
            raise ValueError("approval requirement is required")


class ToolRegistry:
    """Immutable-by-interface validated registry of semantic tool definitions."""

    def __init__(self, definitions: tuple[ToolDefinition, ...]) -> None:
        by_name: dict[str, ToolDefinition] = {}
        for definition in definitions:
            if definition.name in by_name:
                raise ValueError(f"duplicate tool definition: {definition.name}")
            by_name[definition.name] = definition
        if not by_name:
            raise ValueError("tool registry must not be empty")
        self._definitions = by_name

    def get(self, name: str) -> ToolDefinition:
        """Return a definition by exact public semantic tool name."""
        return self._definitions[name]

    def names(self) -> tuple[str, ...]:
        """Return tool names in deterministic canonical order."""
        return tuple(self._definitions)

    def by_application(self, application: str) -> tuple[ToolDefinition, ...]:
        """Return definitions for one application/core scope."""
        return tuple(
            definition
            for definition in self._definitions.values()
            if definition.application == application
        )

    def snapshot(self) -> tuple[dict[str, object], ...]:
        """Return governance metadata without implementation callables or secrets."""
        return tuple(
            {
                "name": definition.name,
                "version": definition.version,
                "application": definition.application,
                "surface": definition.surface,
                "domain": definition.domain,
                "mutation_class": definition.mutation_class.value,
                "risk_class": definition.risk_class,
                "implementation_state": definition.implementation_state.value,
                "capability_keys": definition.capability_keys,
                "ui_contract_dependencies": definition.ui_contract_dependencies,
                "read_back_strategy": definition.read_back_strategy,
                "idempotency_semantics": definition.idempotency_semantics,
                "approval_requirement": definition.approval_requirement,
                "compatibility_requirement": definition.compatibility_requirement.value,
            }
            for definition in self._definitions.values()
        )


def _read_tool(
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
    input_schema: dict[str, Any] | None = None,
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        version=PRODUCT_VERSION,
        application=ApplicationKey.PLANNER.value,
        surface=surface,
        domain=domain,
        input_schema=dict(input_schema or _EMPTY_INPUT),
        output_schema=dict(_COMMON_READ_OUTPUT),
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


def default_tool_registry() -> ToolRegistry:
    """Return the canonical registry for the current 0.1.0 public surface."""
    return ToolRegistry(
        (
            _read_tool(
                "planner_health",
                surface="control_plane",
                domain="system",
                risk_class="READ_ONLY",
                implementation_state=ImplementationState.IMPLEMENTED_NOT_ATTESTED,
            ),
            _read_tool(
                "planner_readiness",
                surface="control_plane",
                domain="system",
                risk_class="READ_ONLY",
                implementation_state=ImplementationState.IMPLEMENTED_NOT_ATTESTED,
                ui_contract_dependencies=("GLOBAL_UI_CONTRACT_ATTESTATION",),
            ),
            _read_tool(
                "planner_capabilities",
                surface="capability",
                domain="capability",
                risk_class="READ_ONLY",
                implementation_state=ImplementationState.IMPLEMENTED_MOCK_ONLY,
                capability_keys=_PLANNER_CAPABILITY_KEYS,
                ui_contract_dependencies=("GLOBAL_UI_CONTRACT_ATTESTATION",),
            ),
            _read_tool(
                "planner_agent_card",
                surface="control_plane",
                domain="system",
                risk_class="READ_ONLY",
                implementation_state=ImplementationState.IMPLEMENTED_NOT_ATTESTED,
            ),
            _read_tool(
                "planner_ui_contract_status",
                surface="ui_contract",
                domain="ui_contract",
                risk_class="READ_ONLY",
                implementation_state=ImplementationState.IMPLEMENTED_NOT_ATTESTED,
                ui_contract_dependencies=("GLOBAL_UI_CONTRACT_ATTESTATION",),
            ),
            _read_tool(
                "planner_auth_status",
                surface="browser_auth",
                domain="auth",
                risk_class="SESSION_OBSERVATION",
                implementation_state=ImplementationState.IMPLEMENTED_MOCK_ONLY,
                ui_contract_dependencies=("auth.login_email_input", "auth.mfa_number_display"),
            ),
            _read_tool(
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
                "planner_auth_resume",
                surface="browser_auth",
                domain="auth",
                risk_class="SESSION_INTERACTION",
                implementation_state=ImplementationState.IMPLEMENTED_MOCK_ONLY,
                ui_contract_dependencies=("auth.mfa_number_display",),
                read_back_strategy="AUTH_STATE_RE_READ",
            ),
            _read_tool(
                "planner_auth_session_info",
                surface="browser_auth",
                domain="auth",
                risk_class="SESSION_METADATA",
                implementation_state=ImplementationState.IMPLEMENTED_NOT_ATTESTED,
            ),
            _read_tool(
                "planner_plan_list",
                surface="planner_web",
                domain="planner",
                risk_class="M365_CONTENT_READ",
                implementation_state=ImplementationState.IMPLEMENTED_MOCK_ONLY,
                capability_keys=("plans.read",),
                ui_contract_dependencies=("plan.list_container", "plan.list_item", "plan.title"),
            ),
            _read_tool(
                "planner_plan_get",
                surface="planner_web",
                domain="planner",
                risk_class="M365_CONTENT_READ",
                implementation_state=ImplementationState.IMPLEMENTED_MOCK_ONLY,
                capability_keys=("plans.read",),
                ui_contract_dependencies=("plan.list_item", "plan.title"),
                input_schema=_id_input("plan_id"),
            ),
            _read_tool(
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
                input_schema=_id_input("plan_id"),
            ),
            _read_tool(
                "planner_task_get",
                surface="planner_web",
                domain="planner",
                risk_class="M365_CONTENT_READ",
                implementation_state=ImplementationState.IMPLEMENTED_MOCK_ONLY,
                capability_keys=("tasks.read",),
                ui_contract_dependencies=("task.list_item", "task.title", "task.bucket"),
                input_schema=_id_input("task_id"),
            ),
            _read_tool(
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
                input_schema=_id_input("plan_id"),
            ),
            _read_tool(
                "planner_account_context",
                surface="browser_account",
                domain="auth",
                risk_class="ACCOUNT_CONTEXT_READ",
                implementation_state=ImplementationState.IMPLEMENTED_MOCK_ONLY,
                ui_contract_dependencies=("account.context_menu",),
            ),
            _read_tool(
                "planner_license_capabilities",
                surface="capability",
                domain="capability",
                risk_class="ACCOUNT_CONTEXT_READ",
                implementation_state=ImplementationState.IMPLEMENTED_MOCK_ONLY,
                capability_keys=_PLANNER_CAPABILITY_KEYS,
                ui_contract_dependencies=("GLOBAL_UI_CONTRACT_ATTESTATION",),
            ),
            _read_tool(
                "planner_smoke_test",
                surface="control_plane",
                domain="system",
                risk_class="READ_ONLY",
                implementation_state=ImplementationState.IMPLEMENTED_MOCK_ONLY,
                ui_contract_dependencies=("GLOBAL_UI_CONTRACT_ATTESTATION",),
            ),
        )
    )
