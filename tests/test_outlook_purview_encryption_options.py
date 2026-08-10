from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import draft_models, purview_encryption_options, readiness
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


def test_purview_option_is_governed_and_non_executable() -> None:
    intent = purview_encryption_options.prepare_purview_protection(
        draft_models.default_synthetic_drafts(),
        purview_encryption_options.PurviewProtectionRequest(
            "draft-001",
            purview_encryption_options.PurviewProtectionOption.DO_NOT_FORWARD,
        ),
        readiness=_ready(),
    )
    assert intent.protection_key == "purview-do-not-forward-draft-001"
    assert intent.executable is False
    assert intent.dispatched is False
    assert intent.to_projection()["approval_required"] is True
    assert intent.to_projection()["live_support_state"] == "UNOBSERVED"


def test_purview_option_rejects_unknown_draft() -> None:
    with pytest.raises(ValueError, match="synthetic draft_key not found"):
        purview_encryption_options.prepare_purview_protection(
            draft_models.default_synthetic_drafts(),
            purview_encryption_options.PurviewProtectionRequest(
                "draft-missing",
                purview_encryption_options.PurviewProtectionOption.ENCRYPT,
            ),
            readiness=_ready(),
        )


def test_out125_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
