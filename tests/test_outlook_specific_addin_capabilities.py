from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import readiness, specific_addin_capabilities
from m365_mcp.tool_registry import default_tool_registry


def _ready() -> readiness.OutlookReadinessReport:
    return readiness.OutlookReadinessReport(
        state=readiness.OutlookReadinessState.DISCOVERY_READY,
        primary_context_verified=True,
        shared_context_verified=False,
        candidate_count=1,
        observed_count=1,
        blocked_count=0,
        reattestation_count=0,
    )


def _catalog() -> specific_addin_capabilities.SpecificAddinCapabilityCatalog:
    return specific_addin_capabilities.SpecificAddinCapabilityCatalog(
        capabilities=(
            specific_addin_capabilities.SpecificAddinCapability(
                addin_key="addin-security-review",
                capability_key="message-assessment",
                surface=specific_addin_capabilities.AddinSurface.MAIL_READ,
                mode=specific_addin_capabilities.AddinCapabilityMode.READ_ONLY,
            ),
            specific_addin_capabilities.SpecificAddinCapability(
                addin_key="addin-calendar-helper",
                capability_key="meeting-preparation",
                surface=specific_addin_capabilities.AddinSurface.CALENDAR_COMPOSE,
                mode=specific_addin_capabilities.AddinCapabilityMode.PREPARE_ONLY,
            ),
        )
    )


def test_specific_capabilities_list_and_resolve_without_generic_executor() -> None:
    catalog = _catalog()
    listed = specific_addin_capabilities.list_specific_addin_capabilities(
        catalog,
        readiness=_ready(),
    )
    resolved = specific_addin_capabilities.get_specific_addin_capability(
        catalog,
        addin_key="addin-calendar-helper",
        capability_key="meeting-preparation",
        readiness=_ready(),
    )
    assert tuple(item.addin_key for item in listed) == (
        "addin-calendar-helper",
        "addin-security-review",
    )
    assert resolved.mode is specific_addin_capabilities.AddinCapabilityMode.PREPARE_ONLY
    assert catalog.generic_executor_available is False
    assert resolved.generic_executor_available is False
    assert catalog.to_projection()["live_support_state"] == "UNOBSERVED"


def test_framework_fails_closed_for_unknown_or_unsafe_keys() -> None:
    catalog = _catalog()
    with pytest.raises(ValueError, match="resolve exactly once"):
        specific_addin_capabilities.get_specific_addin_capability(
            catalog,
            addin_key="addin-security-review",
            capability_key="not-declared",
            readiness=_ready(),
        )
    with pytest.raises(ValueError, match="opaque semantic token"):
        specific_addin_capabilities.SpecificAddinCapability(
            addin_key="https://addin.example",
            capability_key="review",
            surface=specific_addin_capabilities.AddinSurface.MAIL_READ,
            mode=specific_addin_capabilities.AddinCapabilityMode.READ_ONLY,
        )
    with pytest.raises(ValueError, match="generic add-in execution"):
        specific_addin_capabilities.SpecificAddinCapabilityCatalog(
            capabilities=(),
            generic_executor_available=True,
        )


def test_projection_exposes_no_generic_execution_material() -> None:
    projection = _catalog().capabilities[0].to_projection()
    assert projection == {
        "addin_key": "addin-security-review",
        "capability_key": "message-assessment",
        "surface": "MAIL_READ",
        "mode": "READ_ONLY",
        "generic_executor_available": False,
        "synthetic": True,
        "live_support_state": "UNOBSERVED",
    }
    assert not {"url", "manifest", "payload", "script", "selector", "executor"} & set(
        projection
    )


def test_out140_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
