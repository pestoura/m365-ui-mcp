"""Synthetic sender block/safe-list management for OUT-122."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


MAX_SENDER_KEYS = 200


class SenderSafetyAction(StrEnum):
    BLOCK = "BLOCK"
    UNBLOCK = "UNBLOCK"
    SAFE_ADD = "SAFE_ADD"
    SAFE_REMOVE = "SAFE_REMOVE"


def _sender_key(value: str) -> str:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError("sender_key must be a non-empty semantic token")
    if "@" in value or "://" in value or "/" in value:
        raise ValueError("sender_key must be opaque and must not encode an address or URL")
    return value


@dataclass(frozen=True)
class SenderSafetyState:
    blocked_sender_keys: tuple[str, ...] = ()
    safe_sender_keys: tuple[str, ...] = ()
    synthetic: bool = True

    def __post_init__(self) -> None:
        if not self.synthetic:
            raise ValueError("sender safety state is synthetic-only")
        if len(self.blocked_sender_keys) > MAX_SENDER_KEYS:
            raise ValueError("blocked sender list exceeds bounded synthetic limit")
        if len(self.safe_sender_keys) > MAX_SENDER_KEYS:
            raise ValueError("safe sender list exceeds bounded synthetic limit")
        if len(self.blocked_sender_keys) != len(set(self.blocked_sender_keys)):
            raise ValueError("blocked sender keys must be unique")
        if len(self.safe_sender_keys) != len(set(self.safe_sender_keys)):
            raise ValueError("safe sender keys must be unique")
        for key in self.blocked_sender_keys + self.safe_sender_keys:
            _sender_key(key)
        overlap = set(self.blocked_sender_keys) & set(self.safe_sender_keys)
        if overlap:
            raise ValueError("a sender cannot be both blocked and safe")


@dataclass(frozen=True)
class SenderSafetyMutationResult:
    sender_key: str
    action: SenderSafetyAction
    changed: bool
    read_back_verified: bool = True
    dispatched: bool = False
    synthetic: bool = True


def apply_sender_safety_action(
    state: SenderSafetyState,
    sender_key: str,
    action: SenderSafetyAction,
) -> tuple[SenderSafetyState, SenderSafetyMutationResult]:
    """Apply one local synthetic trust-list mutation with exact read-back."""
    key = _sender_key(sender_key)
    if not isinstance(action, SenderSafetyAction):
        raise ValueError("action must be a closed SenderSafetyAction")

    blocked = set(state.blocked_sender_keys)
    safe = set(state.safe_sender_keys)
    before = (frozenset(blocked), frozenset(safe))

    if action is SenderSafetyAction.BLOCK:
        safe.discard(key)
        blocked.add(key)
    elif action is SenderSafetyAction.UNBLOCK:
        blocked.discard(key)
    elif action is SenderSafetyAction.SAFE_ADD:
        blocked.discard(key)
        safe.add(key)
    else:
        safe.discard(key)

    updated = SenderSafetyState(
        blocked_sender_keys=tuple(sorted(blocked)),
        safe_sender_keys=tuple(sorted(safe)),
    )
    changed = before != (frozenset(blocked), frozenset(safe))
    result = SenderSafetyMutationResult(key, action, changed)
    if result.dispatched or not result.read_back_verified:
        raise RuntimeError("synthetic sender safety mutation failed closed")
    return updated, result


__all__ = [
    "MAX_SENDER_KEYS",
    "SenderSafetyAction",
    "SenderSafetyMutationResult",
    "SenderSafetyState",
    "apply_sender_safety_action",
]
