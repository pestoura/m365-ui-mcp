from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import readiness, smime_capability_status
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


def test_smime_status_never_exports_certificate_or_private_key_material() -> None:
    status = smime_capability_status.read_smime_capability_status(readiness=_ready())
    projection = status.to_projection()
    assert status.signing_mode_present is True
    assert status.encryption_mode_present is True
    assert status.certificate_status is smime_capability_status.SmimeCertificateStatus.NOT_MODELED
    assert projection["certificate_material_exported"] is False
    assert projection["private_key_material_exported"] is False
    assert projection["live_support_state"] == "UNOBSERVED"


def test_smime_status_fails_closed_when_readiness_is_not_ready() -> None:
    blocked = readiness.OutlookReadinessReport(
        state=readiness.OutlookReadinessState.BLOCKED,
        primary_context_verified=False,
        shared_context_verified=False,
        candidate_count=0,
        observed_count=0,
        blocked_count=1,
        reattestation_count=0,
    )
    with pytest.raises(ValueError, match="read-only discovery is not ready"):
        smime_capability_status.read_smime_capability_status(readiness=blocked)


def test_out126_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
