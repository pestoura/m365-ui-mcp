"""Synthetic domain block/safe-list management for OUT-123."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


MAX_DOMAIN_KEYS = 200


class DomainSafetyAction(StrEnum):
    BLOCK = "BLOCK"
    UNBLOCK = "UNBLOCK"
    SAFE_ADD = "SAFE_ADD"
    SAFE_REMOVE = "SAFE_REMOVE"


def _domain_key(value: str) -> str:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError("domain_key must be a non-empty semantic token")
    if any(token in value for token in ("@", ".", "/", "://")):
        raise ValueError("domain_key must be opaque and must not encode a real domain or URL")
    return value


@dataclass(frozen=True)
class DomainSafetyState:
    blocked_domain_keys: tuple[str, ...] = ()
    safe_domain_keys: tuple[str, ...] = ()
    synthetic: bool = True

    def __post_init__(self) -> None:
        if not self.synthetic:
            raise ValueError("domain safety state is synthetic-only")
        if len(self.blocked_domain_keys) > MAX_DOMAIN_KEYS:
            raise ValueError("blocked domain list exceeds bounded synthetic limit")
        if len(self.safe_domain_keys) > MAX_DOMAIN_KEYS:
            raise ValueError("safe domain list exceeds bounded synthetic limit")
        if len(self.blocked_domain_keys) != len(set(self.blocked_domain_keys)):
            raise ValueError("blocked domain keys must be unique")
        if len(self.safe_domain_keys) != len(set(self.safe_domain_keys)):
            raise ValueError("safe domain keys must be unique")
        for key in self.blocked_domain_keys + self.safe_domain_keys:
            _domain_key(key)
        overlap = set(self.blocked_domain_keys) & set(self.safe_domain_keys)
        if overlap:
            raise ValueError("a domain cannot be both blocked and safe")


@dataclass(frozen=True)
class DomainSafetyMutationResult:
    domain_key: str
    action: DomainSafetyAction
    changed: bool
    read_back_verified: bool = True
    dispatched: bool = False
    synthetic: bool = True


def apply_domain_safety_action(
    state: DomainSafetyState,
    domain_key: str,
    action: DomainSafetyAction,
) -> tuple[DomainSafetyState, DomainSafetyMutationResult]:
    """Apply one local synthetic domain trust-list mutation with read-back."""
    key = _domain_key(domain_key)
    if not isinstance(action, DomainSafetyAction):
        raise ValueError("action must be a closed DomainSafetyAction")

    blocked = set(state.blocked_domain_keys)
    safe = set(state.safe_domain_keys)
    before = (frozenset(blocked), frozenset(safe))

    if action is DomainSafetyAction.BLOCK:
        safe.discard(key)
        blocked.add(key)
    elif action is DomainSafetyAction.UNBLOCK:
        blocked.discard(key)
    elif action is DomainSafetyAction.SAFE_ADD:
        blocked.discard(key)
        safe.add(key)
    else:
        safe.discard(key)

    updated = DomainSafetyState(
        blocked_domain_keys=tuple(sorted(blocked)),
        safe_domain_keys=tuple(sorted(safe)),
    )
    changed = before != (frozenset(blocked), frozenset(safe))
    result = DomainSafetyMutationResult(key, action, changed)
    if result.dispatched or not result.read_back_verified:
        raise RuntimeError("synthetic domain safety mutation failed closed")
    return updated, result


__all__ = [
    "DomainSafetyAction",
    "DomainSafetyMutationResult",
    "DomainSafetyState",
    "MAX_DOMAIN_KEYS",
    "apply_domain_safety_action",
]
