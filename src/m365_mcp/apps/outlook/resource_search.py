"""Synthetic-only Outlook room/resource search for OUT-093.

Resources are opaque tenant-neutral semantic keys. The model performs bounded,
deterministic filtering only and carries no mailbox identity, address, location,
URL, selector, session material or live Microsoft 365 evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_RESOURCES = 200
_MAX_LIMIT = 100


class ResourceKind(StrEnum):
    """Closed synthetic resource kinds."""

    ROOM = "ROOM"
    EQUIPMENT = "EQUIPMENT"


class ResourceCapability(StrEnum):
    """Closed structural capabilities safe for synthetic matching."""

    VIDEO = "VIDEO"
    AUDIO = "AUDIO"
    ACCESSIBLE = "ACCESSIBLE"
    WHITEBOARD = "WHITEBOARD"


def _validate_key(field_name: str, value: str) -> None:
    invalid = (
        not value
        or value != value.strip()
        or any(char.isspace() for char in value)
    )
    if invalid:
        raise ValueError(f"{field_name} must be a non-empty semantic token")
    if "@" in value:
        raise ValueError(f"{field_name} must not encode an address identity")


@dataclass(frozen=True)
class SyntheticResource:
    """One synthetic room or equipment record."""

    resource_key: str
    kind: ResourceKind
    capacity: int
    capabilities: tuple[ResourceCapability, ...] = ()

    def __post_init__(self) -> None:
        _validate_key("resource_key", self.resource_key)
        if not isinstance(self.kind, ResourceKind):
            raise ValueError("kind must be a closed ResourceKind")
        if self.capacity < 0:
            raise ValueError("capacity must be non-negative")
        if any(not isinstance(item, ResourceCapability) for item in self.capabilities):
            raise ValueError("capabilities must contain closed ResourceCapability values")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError("capabilities must be unique")

    def to_projection(self) -> dict[str, object]:
        return {
            "resource_key": self.resource_key,
            "kind": self.kind.value,
            "capacity": self.capacity,
            "capabilities": [item.value for item in self.capabilities],
            "synthetic": True,
        }


@dataclass(frozen=True)
class ResourceSearchRequest:
    """Bounded synthetic resource search request."""

    kind: ResourceKind | None = None
    minimum_capacity: int = 0
    required_capabilities: tuple[ResourceCapability, ...] = ()
    offset: int = 0
    limit: int = 25

    def __post_init__(self) -> None:
        if self.kind is not None and not isinstance(self.kind, ResourceKind):
            raise ValueError("kind must be a closed ResourceKind")
        if self.minimum_capacity < 0:
            raise ValueError("minimum_capacity must be non-negative")
        if self.offset < 0:
            raise ValueError("offset must be non-negative")
        if self.limit <= 0 or self.limit > _MAX_LIMIT:
            raise ValueError("limit must be a bounded positive count")
        if any(
            not isinstance(item, ResourceCapability)
            for item in self.required_capabilities
        ):
            raise ValueError(
                "required_capabilities must contain closed ResourceCapability values"
            )
        if len(set(self.required_capabilities)) != len(self.required_capabilities):
            raise ValueError("required_capabilities must be unique")


@dataclass(frozen=True)
class ResourceSearchResult:
    """Deterministic bounded search projection."""

    items: tuple[SyntheticResource, ...]
    offset: int
    limit: int
    total_matching: int
    has_more: bool
    synthetic: bool


def default_synthetic_resources() -> tuple[SyntheticResource, ...]:
    """Return an explicit synthetic catalog with no tenant-derived values."""
    return (
        SyntheticResource(
            resource_key="equipment-cart-01",
            kind=ResourceKind.EQUIPMENT,
            capacity=0,
            capabilities=(ResourceCapability.VIDEO, ResourceCapability.AUDIO),
        ),
        SyntheticResource(
            resource_key="room-alpha",
            kind=ResourceKind.ROOM,
            capacity=8,
            capabilities=(
                ResourceCapability.VIDEO,
                ResourceCapability.WHITEBOARD,
                ResourceCapability.ACCESSIBLE,
            ),
        ),
        SyntheticResource(
            resource_key="room-bravo",
            kind=ResourceKind.ROOM,
            capacity=4,
            capabilities=(ResourceCapability.WHITEBOARD,),
        ),
        SyntheticResource(
            resource_key="room-charlie",
            kind=ResourceKind.ROOM,
            capacity=12,
            capabilities=(ResourceCapability.AUDIO, ResourceCapability.ACCESSIBLE),
        ),
    )


def _validate_catalog(resources: tuple[SyntheticResource, ...]) -> None:
    if len(resources) > _MAX_RESOURCES:
        raise ValueError("resource catalog exceeds bounded size")
    keys = tuple(item.resource_key for item in resources)
    if len(set(keys)) != len(keys):
        raise ValueError("resource catalog contains duplicate resource_key")


def search_synthetic_resources(
    request: ResourceSearchRequest,
    *,
    readiness: OutlookReadinessReport,
    resources: tuple[SyntheticResource, ...] | None = None,
) -> ResourceSearchResult:
    """Filter a bounded synthetic resource catalog, failing closed."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not isinstance(request, ResourceSearchRequest):
        raise ValueError("request must be a bounded ResourceSearchRequest")

    catalog = default_synthetic_resources() if resources is None else resources
    _validate_catalog(catalog)
    required = set(request.required_capabilities)
    matched = tuple(
        sorted(
            (
                item
                for item in catalog
                if (request.kind is None or item.kind is request.kind)
                and item.capacity >= request.minimum_capacity
                and required.issubset(set(item.capabilities))
            ),
            key=lambda item: item.resource_key,
        )
    )
    start = request.offset
    end = start + request.limit
    selected = matched[start:end]
    return ResourceSearchResult(
        items=selected,
        offset=request.offset,
        limit=request.limit,
        total_matching=len(matched),
        has_more=end < len(matched),
        synthetic=True,
    )


__all__ = [
    "ResourceCapability",
    "ResourceKind",
    "ResourceSearchRequest",
    "ResourceSearchResult",
    "SyntheticResource",
    "default_synthetic_resources",
    "search_synthetic_resources",
]
