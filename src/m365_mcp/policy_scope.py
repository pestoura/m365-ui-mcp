"""Typed scope model and fail-closed scope validation for CORE-033.

Scope values are semantic classes only. They never contain mailbox addresses,
tenant identifiers, browser profile paths, cookies, tokens or storage state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.capability_registry import (
    CapabilityRegistry,
    ScopedCapability,
    default_capability_registry,
)
from m365_mcp.tool_registry import ToolDefinition


class AccountScope(StrEnum):
    """Closed account-context classes accepted by policy."""

    PRODUCT_CONTEXT = "product_context"
    PROFESSIONAL_SESSION = "professional_session"


class MailboxScope(StrEnum):
    """Closed mailbox classes; Outlook activation is governed elsewhere."""

    NONE = "none"
    PRIMARY = "primary"
    SHARED = "shared"


class ResourceScope(StrEnum):
    """Closed semantic resource granularity."""

    ACCOUNT = "account"
    CONTAINER = "container"
    RESOURCE = "resource"


_ALLOWED_CONTAINER_SCOPES = frozenset(
    {
        "account",
        "plan",
        "mailbox",
        "folder",
        "calendar",
        "task_list",
    }
)
_CONTAINER_SPECIFICITY = {
    "account": 0,
    "mailbox": 1,
    "plan": 1,
    "folder": 2,
    "calendar": 2,
    "task_list": 2,
}


@dataclass(frozen=True)
class PolicyScope:
    """Sanitized scope classes presented to the metadata policy engine."""

    application: str
    surface: str
    account_scope: AccountScope
    container_scope: str | None = None
    mailbox_scope: MailboxScope = MailboxScope.NONE
    resource_scope: ResourceScope | None = None

    def __post_init__(self) -> None:
        for field_name in ("application", "surface"):
            value = getattr(self, field_name)
            if not value or value != value.strip() or any(char.isspace() for char in value):
                raise ValueError(f"invalid policy scope {field_name}: {value!r}")
        if (
            self.container_scope is not None
            and self.container_scope not in _ALLOWED_CONTAINER_SCOPES
        ):
            raise ValueError(f"unknown policy container scope: {self.container_scope!r}")
        if self.application != "outlook" and self.mailbox_scope is not MailboxScope.NONE:
            raise ValueError("mailbox scope is only valid for Outlook")


@dataclass(frozen=True)
class ScopeAssessment:
    """One deterministic scope decision without tenant/session content."""

    allowed: bool
    reason: str
    effective_scope: PolicyScope
    derived: bool


def _matching_capabilities(
    definition: ToolDefinition,
    registry: CapabilityRegistry,
) -> tuple[ScopedCapability, ...]:
    keys = set(definition.capability_keys)
    return tuple(
        capability
        for capability in registry.by_application(definition.application)
        if capability.capability in keys and capability.surface == definition.surface
    )


def _resource_scope(
    definition: ToolDefinition,
    container_scope: str | None,
) -> ResourceScope | None:
    required = tuple(definition.input_schema.get("required", ()))
    if "task_id" in required:
        return ResourceScope.RESOURCE
    if "plan_id" in required:
        return ResourceScope.CONTAINER
    if container_scope == "account":
        return ResourceScope.ACCOUNT
    if container_scope is not None:
        return ResourceScope.CONTAINER
    return None


def canonical_policy_scope(
    definition: ToolDefinition,
    registry: CapabilityRegistry | None = None,
) -> PolicyScope:
    """Derive the narrowest canonical semantic scope from reviewed metadata."""
    capabilities = _matching_capabilities(
        definition,
        registry or default_capability_registry(),
    )
    if capabilities:
        account_scopes = {capability.account_scope for capability in capabilities}
        if account_scopes != {AccountScope.PROFESSIONAL_SESSION.value}:
            raise ValueError("capability metadata has incompatible account scopes")
        container_scope = max(
            (capability.container_scope for capability in capabilities),
            key=lambda item: _CONTAINER_SPECIFICITY.get(item, -1),
        )
        account_scope = AccountScope.PROFESSIONAL_SESSION
    else:
        container_scope = None
        account_scope = AccountScope.PRODUCT_CONTEXT

    mailbox_scope = (
        MailboxScope.PRIMARY
        if definition.application == "outlook" and capabilities
        else MailboxScope.NONE
    )
    return PolicyScope(
        application=definition.application,
        surface=definition.surface,
        account_scope=account_scope,
        container_scope=container_scope,
        mailbox_scope=mailbox_scope,
        resource_scope=_resource_scope(definition, container_scope),
    )


def assess_policy_scope(
    definition: ToolDefinition,
    requested_scope: PolicyScope | None,
    registry: CapabilityRegistry | None = None,
) -> ScopeAssessment:
    """Validate explicit scope or derive the current compatibility scope."""
    canonical = canonical_policy_scope(definition, registry)
    if requested_scope is None:
        return ScopeAssessment(True, "CANONICAL_SCOPE_DERIVED", canonical, True)

    checks = (
        (requested_scope.application == canonical.application, "SCOPE_APPLICATION_MISMATCH"),
        (requested_scope.surface == canonical.surface, "SCOPE_SURFACE_MISMATCH"),
        (requested_scope.account_scope is canonical.account_scope, "SCOPE_ACCOUNT_MISMATCH"),
        (
            requested_scope.container_scope == canonical.container_scope,
            "SCOPE_CONTAINER_MISMATCH",
        ),
        (requested_scope.mailbox_scope is canonical.mailbox_scope, "SCOPE_MAILBOX_MISMATCH"),
        (
            requested_scope.resource_scope is canonical.resource_scope,
            "SCOPE_RESOURCE_MISMATCH",
        ),
    )
    for matches, reason in checks:
        if not matches:
            return ScopeAssessment(False, reason, requested_scope, False)

    return ScopeAssessment(True, "SCOPE_VERIFIED", requested_scope, False)


__all__ = [
    "AccountScope",
    "MailboxScope",
    "PolicyScope",
    "ResourceScope",
    "ScopeAssessment",
    "assess_policy_scope",
    "canonical_policy_scope",
]
