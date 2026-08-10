from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import compliance_error_mapping
from m365_mcp.tool_registry import default_tool_registry


def test_compliance_mapping_is_sanitized_and_non_retryable() -> None:
    mapping = compliance_error_mapping.map_compliance_blocker(
        compliance_error_mapping.ComplianceBlockerCode.RETENTION_LOCKED
    )
    projection = mapping.to_projection()
    assert mapping.category is compliance_error_mapping.ComplianceBlockerCategory.RETENTION
    assert mapping.retryable is False
    assert projection["raw_error_exported"] is False
    assert projection["live_support_state"] == "UNOBSERVED"
    assert projection["operator_action"] == "respect-retention-lock"


def test_compliance_mapping_rejects_unclosed_raw_input() -> None:
    with pytest.raises(ValueError, match="closed ComplianceBlockerCode"):
        compliance_error_mapping.map_compliance_blocker("raw tenant error")  # type: ignore[arg-type]


def test_out129_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
