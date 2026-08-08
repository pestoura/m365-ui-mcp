"""Enumerations that the specification treats as normative.

These mirror docs/governance.md, docs/authentication-and-mfa.md and
docs/planner-premium-capabilities.md. They exist so that tests and schema
validation have a single authoritative definition (backlog P-004, P-005).
"""

from enum import StrEnum


class MutationClass(StrEnum):
    """Blast radius of a tool call."""

    READ = "READ"
    SAFE_WRITE = "SAFE_WRITE"
    GOVERNED_WRITE = "GOVERNED_WRITE"
    DESTRUCTIVE = "DESTRUCTIVE"


class TrustLevel(StrEnum):
    """How much tenant reach a tool is granted."""

    INTROSPECTION = "INTROSPECTION"
    TENANT_READ = "TENANT_READ"
    TENANT_WRITE = "TENANT_WRITE"
    PRIVILEGED = "PRIVILEGED"


class IdempotencyClass(StrEnum):
    """How repeat execution is made safe."""

    PURE_READ = "PURE_READ"
    NATURAL_IDEMPOTENT = "NATURAL_IDEMPOTENT"
    KEYED_IDEMPOTENT = "KEYED_IDEMPOTENT"
    READ_BACK_GUARDED = "READ_BACK_GUARDED"
    NON_IDEMPOTENT = "NON_IDEMPOTENT"


class ApprovalRequirement(StrEnum):
    NONE = "NONE"
    POLICY_CONDITIONAL = "POLICY_CONDITIONAL"
    ALWAYS = "ALWAYS"


class PolicyDecision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class AuthState(StrEnum):
    UNKNOWN = "UNKNOWN"
    READY = "READY"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    MFA_REQUIRED = "MFA_REQUIRED"
    WAITING_FOR_MFA = "WAITING_FOR_MFA"
    AUTHENTICATED = "AUTHENTICATED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    AUTH_FAILED = "AUTH_FAILED"


class AttestationStatus(StrEnum):
    """Evidence backing the UI surface a tool depends on."""

    UNVERIFIED_LIVE = "UNVERIFIED_LIVE"
    DISCOVERED = "DISCOVERED"
    UI_ATTESTED = "UI_ATTESTED"
    READ_ATTESTED = "READ_ATTESTED"
    MUTATION_ATTESTED = "MUTATION_ATTESTED"
    SUPPORTED = "SUPPORTED"


class CapabilityState(StrEnum):
    UNVERIFIED_LIVE = "UNVERIFIED_LIVE"
    DISCOVERED = "DISCOVERED"
    UI_ATTESTED = "UI_ATTESTED"
    READ_ATTESTED = "READ_ATTESTED"
    MUTATION_ATTESTED = "MUTATION_ATTESTED"
    SUPPORTED = "SUPPORTED"
    UI_DRIFT = "UI_DRIFT"
    BLOCKED_CONDITIONAL_ACCESS = "BLOCKED_CONDITIONAL_ACCESS"
    UNSUPPORTED_TENANT = "UNSUPPORTED_TENANT"


#: Terminal authentication states: no further automated progress is attempted.
TERMINAL_AUTH_STATES: frozenset[AuthState] = frozenset({AuthState.AUTH_FAILED})

#: Mutation classes that may never execute without a persistent approval record.
APPROVAL_REQUIRED_CLASSES: frozenset[MutationClass] = frozenset(
    {MutationClass.GOVERNED_WRITE, MutationClass.DESTRUCTIVE}
)
