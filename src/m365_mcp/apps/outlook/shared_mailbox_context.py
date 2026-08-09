"""Sanitized shared-mailbox scoped context model for OUT-006.

The model proves only that execution is scoped to one reviewed shared-mailbox
context. Raw mailbox addresses, tenant/user identifiers and authenticated URLs
are deliberately excluded. Outlook remains RESERVED; this module does not
register public tools or browser operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.mailbox_context import PrimaryMailboxContext


class SharedMailboxContextState(StrEnum):
    """Closed outcomes for shared-mailbox scope verification."""

    VERIFIED = "VERIFIED"
    PRIMARY_CONTEXT_INVALID = "PRIMARY_CONTEXT_INVALID"
    UNVERIFIED = "UNVERIFIED"
    AMBIGUOUS = "AMBIGUOUS"
    PRIMARY_MAILBOX_CONTEXT = "PRIMARY_MAILBOX_CONTEXT"
    REATTESTATION_REQUIRED = "REATTESTATION_REQUIRED"


@dataclass(frozen=True)
class SharedMailboxObservation:
    """Identity-free observation of one reviewed shared-mailbox shell."""

    shared_shell_observed: bool
    primary_mailbox_indicator: bool = False
    ambiguous_mailbox_context: bool = False
    scope_digest: str | None = None
    evidence_digest: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("scope_digest", "evidence_digest"):
            value = getattr(self, field_name)
            if value is not None and (
                len(value) != 64 or any(char not in "0123456789abcdef" for char in value)
            ):
                raise ValueError(f"shared mailbox {field_name} must be SHA-256 hex")
        if self.shared_shell_observed and (
            self.scope_digest is None or self.evidence_digest is None
        ):
            raise ValueError("observed shared mailbox shell requires scope and evidence digests")
        if not self.shared_shell_observed and (
            self.scope_digest is not None or self.evidence_digest is not None
        ):
            raise ValueError("unobserved shared mailbox shell cannot carry scope evidence")


@dataclass(frozen=True)
class SharedMailboxContext:
    """Bounded shared-mailbox context safe for policy/readiness projection."""

    state: SharedMailboxContextState
    primary_context_verified: bool
    shared_shell_verified: bool
    scope_digest: str | None = None
    evidence_digest: str | None = None

    @property
    def valid(self) -> bool:
        return (
            self.state is SharedMailboxContextState.VERIFIED
            and self.primary_context_verified
            and self.shared_shell_verified
            and self.scope_digest is not None
            and self.evidence_digest is not None
        )

    def to_dict(self) -> dict[str, object]:
        """Project bounded state without revealing mailbox identity."""
        return {
            "state": self.state.value,
            "primary_context_verified": self.primary_context_verified,
            "shared_shell_verified": self.shared_shell_verified,
            "scope_present": self.scope_digest is not None,
            "evidence_present": self.evidence_digest is not None,
            "valid": self.valid,
        }


def verify_shared_mailbox_context(
    primary_context: PrimaryMailboxContext,
    observation: SharedMailboxObservation,
    *,
    reattestation_required: bool = False,
) -> SharedMailboxContext:
    """Verify a shared-mailbox scope without accepting identity-bearing inputs."""
    if not primary_context.valid:
        return SharedMailboxContext(
            state=SharedMailboxContextState.PRIMARY_CONTEXT_INVALID,
            primary_context_verified=False,
            shared_shell_verified=False,
        )

    if reattestation_required:
        return SharedMailboxContext(
            state=SharedMailboxContextState.REATTESTATION_REQUIRED,
            primary_context_verified=True,
            shared_shell_verified=False,
        )

    if observation.ambiguous_mailbox_context:
        return SharedMailboxContext(
            state=SharedMailboxContextState.AMBIGUOUS,
            primary_context_verified=True,
            shared_shell_verified=False,
        )

    if observation.primary_mailbox_indicator:
        return SharedMailboxContext(
            state=SharedMailboxContextState.PRIMARY_MAILBOX_CONTEXT,
            primary_context_verified=True,
            shared_shell_verified=False,
        )

    if not observation.shared_shell_observed:
        return SharedMailboxContext(
            state=SharedMailboxContextState.UNVERIFIED,
            primary_context_verified=True,
            shared_shell_verified=False,
        )

    return SharedMailboxContext(
        state=SharedMailboxContextState.VERIFIED,
        primary_context_verified=True,
        shared_shell_verified=True,
        scope_digest=observation.scope_digest,
        evidence_digest=observation.evidence_digest,
    )


__all__ = [
    "SharedMailboxContext",
    "SharedMailboxContextState",
    "SharedMailboxObservation",
    "verify_shared_mailbox_context",
]
