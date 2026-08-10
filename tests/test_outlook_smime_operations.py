from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import (
    draft_models,
    readiness,
    smime_capability_status,
    smime_operations,
)
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


def test_smime_operation_is_governed_non_executable_and_unbound() -> None:
    capability = smime_capability_status.read_smime_capability_status(readiness=_ready())
    intent = smime_operations.prepare_smime_operation(
        draft_models.default_synthetic_drafts(),
        smime_operations.SmimeOperationRequest(
            "draft-001",
            smime_operations.SmimeOperation.SIGN_AND_ENCRYPT,
        ),
        capability=capability,
        readiness=_ready(),
    )
    assert intent.executable is False
    assert intent.dispatched is False
    assert intent.certificate_binding_present is False
    assert intent.to_projection()["approval_required"] is True
    assert intent.to_projection()["live_support_state"] == "UNOBSERVED"


def test_smime_operation_rejects_missing_draft() -> None:
    capability = smime_capability_status.read_smime_capability_status(readiness=_ready())
    with pytest.raises(ValueError, match="synthetic draft_key not found"):
        smime_operations.prepare_smime_operation(
            draft_models.default_synthetic_drafts(),
            smime_operations.SmimeOperationRequest(
                "draft-missing",
                smime_operations.SmimeOperation.SIGN,
            ),
            capability=capability,
            readiness=_ready(),
        )


def test_out127_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
