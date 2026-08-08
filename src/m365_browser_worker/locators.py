"""Browser-worker view of the closed semantic locator model."""

from m365_mcp.locators import (
    LocatorCandidate,
    LocatorPlan,
    LocatorStrategy,
    locator_plan_from_metadata,
)

__all__ = [
    "LocatorCandidate",
    "LocatorPlan",
    "LocatorStrategy",
    "locator_plan_from_metadata",
]
