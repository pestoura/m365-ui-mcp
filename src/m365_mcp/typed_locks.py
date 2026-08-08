"""Application-neutral typed lock identities for CORE-039.

The model defines a closed lock hierarchy for profile, account, application,
container and resource scopes. Opaque account/profile keys and CORE-037 state
identities are reduced to SHA-256 digests so lock metadata never needs raw
Microsoft identifiers, mailbox addresses or browser profile paths.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import IntEnum

from m365_mcp.application_registry import ApplicationKey
from m365_mcp.state_identity import StateIdentity, StateIdentityLevel


class LockScope(IntEnum):
    """Closed lock scopes ordered from broadest to narrowest."""

    PROFILE = 0
    ACCOUNT = 1
    APPLICATION = 2
    CONTAINER = 3
    RESOURCE = 4


def _opaque_digest(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _validate_digest(value: str, *, field_name: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{field_name} must be lowercase SHA-256 hex")


@dataclass(frozen=True)
class TypedLock:
    """Canonical lock target carrying only bounded scope and digest metadata."""

    scope: LockScope
    account_key_digest: str | None = None
    profile_key_digest: str | None = None
    application: ApplicationKey | None = None
    state_identity_digest: str | None = None

    def __post_init__(self) -> None:
        if self.account_key_digest is not None:
            _validate_digest(self.account_key_digest, field_name="account_key_digest")
        if self.profile_key_digest is not None:
            _validate_digest(self.profile_key_digest, field_name="profile_key_digest")
        if self.state_identity_digest is not None:
            _validate_digest(
                self.state_identity_digest,
                field_name="state_identity_digest",
            )

        if self.scope is LockScope.PROFILE:
            if self.profile_key_digest is None:
                raise ValueError("profile lock requires profile_key_digest")
            if any(
                value is not None
                for value in (
                    self.account_key_digest,
                    self.application,
                    self.state_identity_digest,
                )
            ):
                raise ValueError("profile lock cannot carry narrower lock fields")
            return

        if self.account_key_digest is None:
            raise ValueError("account/application/resource lock requires account_key_digest")

        if self.scope is LockScope.ACCOUNT:
            if any(
                value is not None
                for value in (
                    self.profile_key_digest,
                    self.application,
                    self.state_identity_digest,
                )
            ):
                raise ValueError("account lock cannot carry narrower lock fields")
            return

        if self.application is None:
            raise ValueError("application/container/resource lock requires application")
        if self.profile_key_digest is not None:
            raise ValueError("non-profile lock cannot carry profile_key_digest")

        if self.scope is LockScope.APPLICATION:
            if self.state_identity_digest is not None:
                raise ValueError("application lock cannot carry state identity")
            return

        if self.state_identity_digest is None:
            raise ValueError("container/resource lock requires state identity")

    def canonical_payload(self) -> dict[str, str]:
        """Return deterministic, non-sensitive lock identity metadata."""
        payload = {"scope": self.scope.name}
        if self.profile_key_digest is not None:
            payload["profile_key_digest"] = self.profile_key_digest
        if self.account_key_digest is not None:
            payload["account_key_digest"] = self.account_key_digest
        if self.application is not None:
            payload["application"] = self.application.value
        if self.state_identity_digest is not None:
            payload["state_identity_digest"] = self.state_identity_digest
        return payload

    @property
    def lock_key(self) -> str:
        """Return one stable key suitable for an in-process or persisted lock map."""
        encoded = json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @property
    def order_key(self) -> tuple[int, str]:
        """Provide a deterministic global acquisition order."""
        return (int(self.scope), self.lock_key)


def profile_lock(profile_key: str) -> TypedLock:
    """Create a profile-wide lock without retaining a profile path/name."""
    return TypedLock(
        scope=LockScope.PROFILE,
        profile_key_digest=_opaque_digest(profile_key, field_name="profile_key"),
    )


def account_lock(account_key: str) -> TypedLock:
    """Create an account-wide lock from an opaque local account assertion key."""
    return TypedLock(
        scope=LockScope.ACCOUNT,
        account_key_digest=_opaque_digest(account_key, field_name="account_key"),
    )


def application_lock(account_key: str, application: ApplicationKey) -> TypedLock:
    """Create one application lock beneath an account boundary."""
    return TypedLock(
        scope=LockScope.APPLICATION,
        account_key_digest=_opaque_digest(account_key, field_name="account_key"),
        application=application,
    )


def state_lock(account_key: str, identity: StateIdentity) -> TypedLock:
    """Create a container/resource lock directly from CORE-037 state identity."""
    if identity.level is StateIdentityLevel.ACCOUNT:
        raise ValueError("account-level StateIdentity cannot create container/resource lock")
    scope = (
        LockScope.CONTAINER
        if identity.level is StateIdentityLevel.CONTAINER
        else LockScope.RESOURCE
    )
    return TypedLock(
        scope=scope,
        account_key_digest=_opaque_digest(account_key, field_name="account_key"),
        application=identity.application,
        state_identity_digest=identity.identity_digest,
    )


def canonical_lock_order(locks: tuple[TypedLock, ...]) -> tuple[TypedLock, ...]:
    """Return unique locks in one global broad-to-narrow acquisition order."""
    by_key: dict[str, TypedLock] = {}
    for lock in locks:
        by_key[lock.lock_key] = lock
    return tuple(sorted(by_key.values(), key=lambda lock: lock.order_key))


def legacy_planner_lock_scope(lock_type: str) -> LockScope:
    """Map historical Planner lock names to the new lock hierarchy.

    This string-only compatibility bridge avoids making the generic M365 core
    import the legacy Planner package.
    """
    mapping = {
        "browser_profile": LockScope.PROFILE,
        "session": LockScope.ACCOUNT,
        "plan": LockScope.CONTAINER,
        "bucket": LockScope.RESOURCE,
        "task": LockScope.RESOURCE,
    }
    try:
        return mapping[lock_type]
    except KeyError as exc:
        raise ValueError("unknown legacy Planner lock type") from exc


__all__ = [
    "LockScope",
    "TypedLock",
    "account_lock",
    "application_lock",
    "canonical_lock_order",
    "legacy_planner_lock_scope",
    "profile_lock",
    "state_lock",
]
