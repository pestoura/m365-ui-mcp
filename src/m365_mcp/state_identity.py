"""Application-neutral state identity for CORE-037.

State identity is scoped by application and semantic resource hierarchy rather
than one Planner-specific external id. External identifiers are normalized into
SHA-256 digests immediately; raw Microsoft resource ids are never projected by
this model.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.application_registry import ApplicationKey


class StateIdentityLevel(StrEnum):
    """Closed hierarchy levels supported by stateful execution records."""

    ACCOUNT = "ACCOUNT"
    CONTAINER = "CONTAINER"
    RESOURCE = "RESOURCE"


def _digest_external_id(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("external identity must not be empty")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _validate_semantic_kind(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized or any(char.isspace() for char in normalized):
        raise ValueError(f"{field_name} must be a non-empty semantic token")
    return normalized


@dataclass(frozen=True)
class StateIdentity:
    """Canonical identity for one account, container, or resource state target."""

    application: ApplicationKey
    account_scope: str
    level: StateIdentityLevel
    container_kind: str | None = None
    container_id_digest: str | None = None
    resource_kind: str | None = None
    resource_id_digest: str | None = None

    def __post_init__(self) -> None:
        _validate_semantic_kind(self.account_scope, field_name="account_scope")

        if self.level is StateIdentityLevel.ACCOUNT:
            if any(
                value is not None
                for value in (
                    self.container_kind,
                    self.container_id_digest,
                    self.resource_kind,
                    self.resource_id_digest,
                )
            ):
                raise ValueError("account identity cannot carry container/resource fields")
            return

        if self.container_kind is None or self.container_id_digest is None:
            raise ValueError("container/resource identity requires container identity")
        _validate_semantic_kind(self.container_kind, field_name="container_kind")
        _validate_digest(self.container_id_digest, field_name="container_id_digest")

        if self.level is StateIdentityLevel.CONTAINER:
            if self.resource_kind is not None or self.resource_id_digest is not None:
                raise ValueError("container identity cannot carry resource fields")
            return

        if self.resource_kind is None or self.resource_id_digest is None:
            raise ValueError("resource identity requires resource identity fields")
        _validate_semantic_kind(self.resource_kind, field_name="resource_kind")
        _validate_digest(self.resource_id_digest, field_name="resource_id_digest")

    def canonical_payload(self) -> dict[str, str]:
        """Return deterministic identity metadata without raw external ids."""
        payload = {
            "application": self.application.value,
            "account_scope": self.account_scope,
            "level": self.level.value,
        }
        if self.container_kind is not None:
            payload["container_kind"] = self.container_kind
        if self.container_id_digest is not None:
            payload["container_id_digest"] = self.container_id_digest
        if self.resource_kind is not None:
            payload["resource_kind"] = self.resource_kind
        if self.resource_id_digest is not None:
            payload["resource_id_digest"] = self.resource_id_digest
        return payload

    @property
    def identity_digest(self) -> str:
        """Hash the canonical scoped identity for persistence/indexing."""
        encoded = json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def _validate_digest(value: str, *, field_name: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{field_name} must be lowercase SHA-256 hex")


def account_state_identity(
    application: ApplicationKey,
    *,
    account_scope: str,
) -> StateIdentity:
    """Construct an account-scoped state identity."""
    return StateIdentity(
        application=application,
        account_scope=account_scope,
        level=StateIdentityLevel.ACCOUNT,
    )


def container_state_identity(
    application: ApplicationKey,
    *,
    account_scope: str,
    container_kind: str,
    external_container_id: str,
) -> StateIdentity:
    """Construct a container identity while discarding the raw external id."""
    return StateIdentity(
        application=application,
        account_scope=account_scope,
        level=StateIdentityLevel.CONTAINER,
        container_kind=container_kind,
        container_id_digest=_digest_external_id(external_container_id),
    )


def resource_state_identity(
    application: ApplicationKey,
    *,
    account_scope: str,
    container_kind: str,
    external_container_id: str,
    resource_kind: str,
    external_resource_id: str,
) -> StateIdentity:
    """Construct a resource identity scoped through its parent container."""
    return StateIdentity(
        application=application,
        account_scope=account_scope,
        level=StateIdentityLevel.RESOURCE,
        container_kind=container_kind,
        container_id_digest=_digest_external_id(external_container_id),
        resource_kind=resource_kind,
        resource_id_digest=_digest_external_id(external_resource_id),
    )


def planner_external_id_identity(
    external_id: str,
    *,
    resource_kind: str,
    container_id: str | None = None,
) -> StateIdentity:
    """Compatibility bridge for existing Planner external-id assumptions.

    Account-level Planner reads use the historical external id as an opaque
    account-scope discriminator. Plan/task state is represented as a container
    or resource identity without retaining the original identifier.
    """
    if container_id is None:
        return container_state_identity(
            ApplicationKey.PLANNER,
            account_scope="professional_session",
            container_kind=resource_kind,
            external_container_id=external_id,
        )
    return resource_state_identity(
        ApplicationKey.PLANNER,
        account_scope="professional_session",
        container_kind="plan",
        external_container_id=container_id,
        resource_kind=resource_kind,
        external_resource_id=external_id,
    )


__all__ = [
    "StateIdentity",
    "StateIdentityLevel",
    "account_state_identity",
    "container_state_identity",
    "planner_external_id_identity",
    "resource_state_identity",
]
