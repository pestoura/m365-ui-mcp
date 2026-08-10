"""Synthetic tenant-policy-respecting retention/archive controls for OUT-128."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ArchivePreference(StrEnum):
    DEFAULT = "DEFAULT"
    ARCHIVE_WHEN_ELIGIBLE = "ARCHIVE_WHEN_ELIGIBLE"


@dataclass(frozen=True)
class RetentionArchiveState:
    archive_preference: ArchivePreference = ArchivePreference.DEFAULT
    retention_policy_key: str = "retention-default"
    archive_policy_key: str = "archive-default"
    policy_locked: bool = False
    tenant_policy_enforced: bool = True
    synthetic: bool = True
    live_support_state: str = "UNOBSERVED"

    def __post_init__(self) -> None:
        if not isinstance(self.archive_preference, ArchivePreference):
            raise ValueError("archive_preference must be a closed ArchivePreference")
        for name in ("retention_policy_key", "archive_policy_key"):
            value = getattr(self, name)
            if not value or value != value.strip() or any(char.isspace() for char in value):
                raise ValueError(f"{name} must be a non-empty semantic token")
            if "@" in value or "://" in value or "/" in value:
                raise ValueError(f"{name} must not encode an address or URL")
        if not self.tenant_policy_enforced:
            raise ValueError("tenant compliance policy enforcement cannot be disabled")
        if not self.synthetic or self.live_support_state != "UNOBSERVED":
            raise ValueError("retention/archive state must remain synthetic and live-unobserved")


@dataclass(frozen=True)
class RetentionArchiveResult:
    changed: bool
    read_back: RetentionArchiveState
    policy_respected: bool = True
    dispatched: bool = False
    synthetic: bool = True


def set_archive_preference(
    current: RetentionArchiveState,
    preference: ArchivePreference,
) -> tuple[RetentionArchiveState, RetentionArchiveResult]:
    """Change only the synthetic archive preference; never override retention policy."""
    if not isinstance(preference, ArchivePreference):
        raise ValueError("preference must be a closed ArchivePreference")
    if current.policy_locked and preference is not current.archive_preference:
        raise ValueError("tenant retention/archive policy is locked")

    updated = RetentionArchiveState(
        archive_preference=preference,
        retention_policy_key=current.retention_policy_key,
        archive_policy_key=current.archive_policy_key,
        policy_locked=current.policy_locked,
        tenant_policy_enforced=True,
    )
    result = RetentionArchiveResult(
        changed=updated != current,
        read_back=updated,
    )
    if not result.policy_respected or result.dispatched:
        raise RuntimeError("retention/archive control failed closed")
    return updated, result


__all__ = [
    "ArchivePreference",
    "RetentionArchiveResult",
    "RetentionArchiveState",
    "set_archive_preference",
]
