"""Sanitized primary-mailbox context model for OUT-005.

The model deliberately carries no mailbox address, tenant identifier, user
identifier or authenticated URL. It composes the already-sanitized CORE-024
account context with bounded Outlook shell observations and remains independent
from public tool registration or live-support promotion.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_browser_worker.account_context import AccountContext


class PrimaryMailboxContextState(StrEnum):
    """Closed outcomes for primary-mailbox context verification."""

    VERIFIED = "VERIFIED"
    ACCOUNT_CONTEXT_INVALID = "ACCOUNT_CONTEXT_INVALID"
    UNVERIFIED = "UNVERIFIED"
    AMBIGUOUS = "AMBIGUOUS"
    SHARED_MAILBOX_CONTEXT = "SHARED_MAILBOX_CONTEXT"
    REATTESTATION_REQUIRED = "REATTESTATION_REQUIRED"


@dataclass(frozen=True)
class PrimaryMailboxObservation:
    """Content-free evidence projected from a reviewed Outlook shell check."""

    primary_shell_observed: bool
    shared_mailbox_indicator: bool = False
    ambiguous_mailbox_context: bool = False
    evidence_digest: str | None = None

    def __post_init__(self) -> None:
        if self.evidence_digest is not None and (
            len(self.evidence_digest) != 64
            or any(char not in "0123456789abcdef" for char in self.evidence_digest)
        ):
            raise ValueError("primary mailbox evidence digest must be SHA-256 hex")
        if self.primary_shell_observed and self.evidence_digest is None:
            raise ValueError("observed primary mailbox shell requires evidence digest")
        if not self.primary_shell_observed and self.evidence_digest is not None:
            raise ValueError("unobserved primary mailbox shell cannot carry evidence digest")


@dataclass(frozen=True)
class PrimaryMailboxContext:
    """Sanitized verification result safe for policy/readiness projection."""

    state: PrimaryMailboxContextState
    account_context_verified: bool
    primary_shell_verified: bool
    evidence_digest: str | None = None

    @property
    def valid(self) -> bool:
        return (
            self.state is PrimaryMailboxContextState.VERIFIED
            and self.account_context_verified
            and self.primary_shell_verified
            and self.evidence_digest is not None
        )

    def to_dict(self) -> dict[str, object]:
        """Return only bounded verification state, never mailbox identity."""
        return {
            "state": self.state.value,
            "account_context_verified": self.account_context_verified,
            "primary_shell_verified": self.primary_shell_verified,
            "evidence_present": self.evidence_digest is not None,
            "valid": self.valid,
        }


def verify_primary_mailbox_context(
    account_context: AccountContext,
    observation: PrimaryMailboxObservation,
    *,
    reattestation_required: bool = False,
) -> PrimaryMailboxContext:
    """Verify primary-mailbox context without accepting identity-bearing inputs."""
    if not account_context.valid:
        return PrimaryMailboxContext(
            state=PrimaryMailboxContextState.ACCOUNT_CONTEXT_INVALID,
            account_context_verified=False,
            primary_shell_verified=False,
        )

    if reattestation_required:
        return PrimaryMailboxContext(
            state=PrimaryMailboxContextState.REATTESTATION_REQUIRED,
            account_context_verified=True,
            primary_shell_verified=False,
        )

    if observation.ambiguous_mailbox_context:
        return PrimaryMailboxContext(
            state=PrimaryMailboxContextState.AMBIGUOUS,
            account_context_verified=True,
            primary_shell_verified=False,
        )

    if observation.shared_mailbox_indicator:
        return PrimaryMailboxContext(
            state=PrimaryMailboxContextState.SHARED_MAILBOX_CONTEXT,
            account_context_verified=True,
            primary_shell_verified=False,
        )

    if not observation.primary_shell_observed:
        return PrimaryMailboxContext(
            state=PrimaryMailboxContextState.UNVERIFIED,
            account_context_verified=True,
            primary_shell_verified=False,
        )

    return PrimaryMailboxContext(
        state=PrimaryMailboxContextState.VERIFIED,
        account_context_verified=True,
        primary_shell_verified=True,
        evidence_digest=observation.evidence_digest,
    )


__all__ = [
    "PrimaryMailboxContext",
    "PrimaryMailboxContextState",
    "PrimaryMailboxObservation",
    "verify_primary_mailbox_context",
]
