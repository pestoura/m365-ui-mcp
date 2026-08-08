"""Versioned contract models: manifests, tool descriptors and the agent card.

Declarative only: nothing here touches a browser, a tenant or a credential. The field
values mirror ``docs/schemas/*.schema.json`` exactly, so the Python objects and the
published JSON Schemas cannot drift (validated by ``scripts/validate_contracts.py``).

Implemented with dataclasses to keep the specification foundation dependency-free.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from planner_mcp.enums import (
    ApprovalRequirement,
    CapabilityState,
    IdempotencyClass,
    MutationClass,
    TrustLevel,
)
from planner_mcp.version import CONTRACT_VERSION, PRODUCT_VERSION, SCHEMA_VERSION

TOOL_NAME_RE = re.compile(r"^planner_[a-z0-9_]+$")


class ContractError(ValueError):
    """Raised when a contract object violates its own schema."""


@dataclass(frozen=True, slots=True)
class ToolManifest:
    """Minimal, client-facing description of a semantic tool."""

    name: str
    title: str
    description: str
    mutation_class: MutationClass

    def __post_init__(self) -> None:
        if not TOOL_NAME_RE.match(self.name):
            raise ContractError(f"invalid tool name: {self.name!r}")
        if not self.description.strip():
            raise ContractError(f"{self.name}: description must not be empty")


@dataclass(frozen=True, slots=True)
class ExtendedToolManifest:
    """Governance-bearing tool descriptor used by the policy engine and the catalogue."""

    name: str
    title: str
    description: str
    trust_level: TrustLevel
    mutation_class: MutationClass
    reversible: bool
    idempotency_class: IdempotencyClass
    approval_requirement: ApprovalRequirement
    attestation_status: CapabilityState
    policy_rule_id: str
    required_locks: tuple[str, ...] = ()
    read_back_strategy: str = "n/a"
    drift_behavior: str = "FAIL_CLOSED"
    capability_refs: tuple[str, ...] = ()
    ui_contract_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not TOOL_NAME_RE.match(self.name):
            raise ContractError(f"invalid tool name: {self.name!r}")
        if not self.description.strip():
            raise ContractError(f"{self.name}: description must not be empty")
        if self.drift_behavior != "FAIL_CLOSED":
            raise ContractError(f"{self.name}: drift_behavior must be FAIL_CLOSED")
        if self.mutation_class in (MutationClass.GOVERNED_WRITE, MutationClass.DESTRUCTIVE) and (
            self.approval_requirement is ApprovalRequirement.NONE
        ):
            raise ContractError(f"{self.name}: governed/destructive tools require approval")

    def as_dict(self) -> dict[str, object]:
        """Schema-shaped mapping, matching extended-tool-manifest.schema.json."""
        return {
            "name": self.name,
            "description": self.description,
            "trust_level": str(self.trust_level),
            "mutation_class": str(self.mutation_class),
            "reversible": self.reversible,
            "idempotency_class": str(self.idempotency_class),
            "approval_requirement": str(self.approval_requirement),
            "attestation_status": str(self.attestation_status),
            "policy_rule_id": self.policy_rule_id,
            "required_locks": list(self.required_locks),
            "read_back_strategy": self.read_back_strategy,
            "drift_behavior": self.drift_behavior,
        }


@dataclass(frozen=True, slots=True)
class CapabilityEntry:
    """One row of the capability matrix. State is decided by browser evidence only."""

    capability: str
    domain: str
    state: CapabilityState = CapabilityState.UNVERIFIED_LIVE
    ui_observed: bool = False
    read_validated: bool = False
    mutation_validated: bool = False
    required_mutation_class: MutationClass = MutationClass.READ
    read_back_strategy: str = "n/a"
    drift_behavior: str = "FAIL_CLOSED"
    evidence_refs: tuple[str, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        evidence_states = {
            CapabilityState.UI_ATTESTED,
            CapabilityState.READ_ATTESTED,
            CapabilityState.MUTATION_ATTESTED,
            CapabilityState.SUPPORTED,
        }
        if self.state in evidence_states and not self.evidence_refs:
            raise ContractError(f"{self.capability}: state {self.state} requires evidence_refs")
        if self.mutation_validated and self.state is CapabilityState.UNVERIFIED_LIVE:
            raise ContractError(f"{self.capability}: mutation_validated contradicts state")


@dataclass(frozen=True, slots=True)
class CapabilityManifest:
    """Everything the server claims it can do, plus the evidence state of each claim."""

    contract_version: str = CONTRACT_VERSION
    graph_is_functional_gate: bool = False
    capabilities: tuple[CapabilityEntry, ...] = ()
    tools: tuple[ExtendedToolManifest, ...] = field(default=())

    def __post_init__(self) -> None:
        if self.graph_is_functional_gate:
            raise ContractError("Microsoft Graph must never be a functional gate (ADR-006)")
        names = [tool.name for tool in self.tools]
        if len(names) != len(set(names)):
            raise ContractError("duplicate tool names in manifest")

    def supported(self) -> tuple[CapabilityEntry, ...]:
        return tuple(c for c in self.capabilities if c.state is CapabilityState.SUPPORTED)


@dataclass(frozen=True, slots=True)
class AgentCard:
    """Identity and boundary statement published to MCP clients."""

    name: str = "planner-mcp"
    contract_version: str = CONTRACT_VERSION
    product_version: str = PRODUCT_VERSION
    schema_version: str = SCHEMA_VERSION
    operating_mode: str = "browser-first"
    graph_is_functional_gate: bool = False
    human_in_the_loop: bool = True
    mfa_channel: str = "microsoft-authenticator-only"
    fails_closed_on: tuple[str, ...] = (
        "ui_drift",
        "unverified_selector",
        "ambiguous_identity",
        "undecidable_policy",
        "conditional_access_blocker",
    )
    never_does: tuple[str, ...] = (
        "store_or_transport_the_microsoft_password",
        "approve_or_relay_microsoft_mfa",
        "enrol_the_host_device_in_mdm_or_entra_device_registration",
        "bypass_or_spoof_conditional_access",
        "expose_generic_click_type_or_navigate_tools",
    )

    def __post_init__(self) -> None:
        if self.graph_is_functional_gate:
            raise ContractError("Microsoft Graph must never be a functional gate (ADR-006)")
        if self.mfa_channel != "microsoft-authenticator-only":
            raise ContractError("MFA approval channel is Microsoft Authenticator only (ADR-004)")


__all__ = [
    "AgentCard",
    "CapabilityEntry",
    "CapabilityManifest",
    "ContractError",
    "ExtendedToolManifest",
    "ToolManifest",
]
