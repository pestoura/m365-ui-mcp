"""Synthetic-only shared-mailbox discovery/open semantics for OUT-111."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.shared_mailbox_context import SharedMailboxContext

_MAX_SHARED_MAILBOXES = 25


@dataclass(frozen=True)
class SyntheticSharedMailboxCandidate:
    mailbox_key: str
    context: SharedMailboxContext

    def __post_init__(self) -> None:
        if (
            not self.mailbox_key
            or self.mailbox_key != self.mailbox_key.strip()
            or "@" in self.mailbox_key
            or any(char.isspace() for char in self.mailbox_key)
        ):
            raise ValueError("mailbox_key must be an opaque semantic token")


@dataclass(frozen=True)
class SharedMailboxDiscoveryResult:
    mailbox_keys: tuple[str, ...]
    candidate_count: int
    synthetic: bool = True


@dataclass(frozen=True)
class OpenedSharedMailbox:
    mailbox_key: str
    scope_verified: bool
    evidence_verified: bool
    synthetic: bool = True


def discover_shared_mailboxes(
    candidates: tuple[SyntheticSharedMailboxCandidate, ...],
) -> SharedMailboxDiscoveryResult:
    """Return only candidates whose sanitized shared context is valid."""
    if len(candidates) > _MAX_SHARED_MAILBOXES:
        raise ValueError("shared mailbox catalog exceeds bounded size")
    keys = tuple(item.mailbox_key for item in candidates)
    if len(set(keys)) != len(keys):
        raise ValueError("shared mailbox keys must be unique")
    verified = tuple(sorted(item.mailbox_key for item in candidates if item.context.valid))
    return SharedMailboxDiscoveryResult(
        mailbox_keys=verified,
        candidate_count=len(verified),
    )


def open_shared_mailbox(
    candidates: tuple[SyntheticSharedMailboxCandidate, ...],
    mailbox_key: str,
) -> OpenedSharedMailbox:
    """Open one opaque candidate only when its reviewed context is valid."""
    discovered = discover_shared_mailboxes(candidates)
    if mailbox_key not in discovered.mailbox_keys:
        raise ValueError("verified synthetic shared mailbox not found")
    candidate = next(item for item in candidates if item.mailbox_key == mailbox_key)
    if not candidate.context.valid:
        raise RuntimeError("shared mailbox context became invalid after discovery")
    return OpenedSharedMailbox(
        mailbox_key=mailbox_key,
        scope_verified=candidate.context.scope_digest is not None,
        evidence_verified=candidate.context.evidence_digest is not None,
    )


__all__ = [
    "OpenedSharedMailbox",
    "SharedMailboxDiscoveryResult",
    "SyntheticSharedMailboxCandidate",
    "discover_shared_mailboxes",
    "open_shared_mailbox",
]
