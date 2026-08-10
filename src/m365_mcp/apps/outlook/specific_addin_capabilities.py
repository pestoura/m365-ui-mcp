"""Specific synthetic add-in capability framework for OUT-140.

The framework describes narrowly declared add-in capabilities only. It does not
expose a generic add-in executor, manifest loader, arbitrary payload, URL,
selector, script, or browser primitive.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_CAPABILITIES = 100


class AddinSurface(StrEnum):
    """Closed Outlook surfaces that a specific capability may describe."""

    MAIL_READ = "MAIL_READ"
    MAIL_COMPOSE = "MAIL_COMPOSE"
    CALENDAR_READ = "CALENDAR_READ"
    CALENDAR_COMPOSE = "CALENDAR_COMPOSE"


class AddinCapabilityMode(StrEnum):
    """Closed non-executing capability modes."""

    READ_ONLY = "READ_ONLY"
    PREPARE_ONLY = "PREPARE_ONLY"


def _validate_key(field: str, value: str) -> None:
    invalid = (
        not value
        or value != value.strip()
        or any(char.isspace() for char in value)
        or "@" in value
        or "://" in value
    )
    if invalid:
        raise ValueError(f"{field} must be an opaque semantic token")


@dataclass(frozen=True)
class SpecificAddinCapability:
    """One explicitly declared capability for one opaque add-in identity."""

    addin_key: str
    capability_key: str
    surface: AddinSurface
    mode: AddinCapabilityMode
    generic_executor_available: bool = False
    synthetic: bool = True
    live_support_state: str = "UNOBSERVED"

    def __post_init__(self) -> None:
        _validate_key("addin_key", self.addin_key)
        _validate_key("capability_key", self.capability_key)
        if not isinstance(self.surface, AddinSurface):
            raise ValueError("surface must be a closed AddinSurface")
        if not isinstance(self.mode, AddinCapabilityMode):
            raise ValueError("mode must be a closed AddinCapabilityMode")
        if self.generic_executor_available:
            raise ValueError("generic add-in execution is not available")
        if not self.synthetic or self.live_support_state != "UNOBSERVED":
            raise ValueError("add-in capability must remain synthetic and live-unobserved")

    def to_projection(self) -> dict[str, object]:
        return {
            "addin_key": self.addin_key,
            "capability_key": self.capability_key,
            "surface": self.surface.value,
            "mode": self.mode.value,
            "generic_executor_available": False,
            "synthetic": True,
            "live_support_state": self.live_support_state,
        }


@dataclass(frozen=True)
class SpecificAddinCapabilityCatalog:
    """Bounded catalog of explicitly declared add-in capabilities."""

    capabilities: tuple[SpecificAddinCapability, ...]
    generic_executor_available: bool = False
    synthetic: bool = True
    live_support_state: str = "UNOBSERVED"

    def __post_init__(self) -> None:
        if len(self.capabilities) > _MAX_CAPABILITIES:
            raise ValueError("add-in capability catalog exceeds bounded size")
        keys = tuple(
            (item.addin_key, item.capability_key) for item in self.capabilities
        )
        if len(keys) != len(set(keys)):
            raise ValueError("add-in capability catalog contains duplicate keys")
        if self.generic_executor_available:
            raise ValueError("generic add-in execution is not available")
        if not self.synthetic or self.live_support_state != "UNOBSERVED":
            raise ValueError("add-in catalog must remain synthetic and live-unobserved")

    def to_projection(self) -> dict[str, object]:
        return {
            "capability_count": len(self.capabilities),
            "generic_executor_available": False,
            "synthetic": True,
            "live_support_state": self.live_support_state,
        }


def _require_ready(readiness: OutlookReadinessReport) -> None:
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")


def list_specific_addin_capabilities(
    catalog: SpecificAddinCapabilityCatalog,
    *,
    readiness: OutlookReadinessReport,
    addin_key: str | None = None,
) -> tuple[SpecificAddinCapability, ...]:
    """List declared capabilities without executing or invoking an add-in."""
    _require_ready(readiness)
    if addin_key is not None:
        _validate_key("addin_key", addin_key)
    matches = tuple(
        item
        for item in catalog.capabilities
        if addin_key is None or item.addin_key == addin_key
    )
    return tuple(sorted(matches, key=lambda item: (item.addin_key, item.capability_key)))


def get_specific_addin_capability(
    catalog: SpecificAddinCapabilityCatalog,
    *,
    addin_key: str,
    capability_key: str,
    readiness: OutlookReadinessReport,
) -> SpecificAddinCapability:
    """Resolve exactly one explicitly declared capability and fail closed otherwise."""
    _require_ready(readiness)
    _validate_key("addin_key", addin_key)
    _validate_key("capability_key", capability_key)
    matches = tuple(
        item
        for item in catalog.capabilities
        if item.addin_key == addin_key and item.capability_key == capability_key
    )
    if len(matches) != 1:
        raise ValueError("specific add-in capability must resolve exactly once")
    return matches[0]


__all__ = [
    "AddinCapabilityMode",
    "AddinSurface",
    "SpecificAddinCapability",
    "SpecificAddinCapabilityCatalog",
    "get_specific_addin_capability",
    "list_specific_addin_capabilities",
]
