from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import retention_archive_controls
from m365_mcp.tool_registry import default_tool_registry


def test_archive_preference_is_idempotent_and_policy_respecting() -> None:
    current = retention_archive_controls.RetentionArchiveState()
    updated, result = retention_archive_controls.set_archive_preference(
        current,
        retention_archive_controls.ArchivePreference.ARCHIVE_WHEN_ELIGIBLE,
    )
    assert (
        updated.archive_preference
        is retention_archive_controls.ArchivePreference.ARCHIVE_WHEN_ELIGIBLE
    )
    assert updated.tenant_policy_enforced is True
    assert result.policy_respected is True
    assert result.dispatched is False
    assert result.changed is True

    same, again = retention_archive_controls.set_archive_preference(
        updated,
        retention_archive_controls.ArchivePreference.ARCHIVE_WHEN_ELIGIBLE,
    )
    assert same == updated
    assert again.changed is False


def test_locked_policy_fails_closed() -> None:
    locked = retention_archive_controls.RetentionArchiveState(policy_locked=True)
    with pytest.raises(ValueError, match="policy is locked"):
        retention_archive_controls.set_archive_preference(
            locked,
            retention_archive_controls.ArchivePreference.ARCHIVE_WHEN_ELIGIBLE,
        )


def test_policy_enforcement_cannot_be_disabled() -> None:
    with pytest.raises(ValueError, match="cannot be disabled"):
        retention_archive_controls.RetentionArchiveState(tenant_policy_enforced=False)


def test_out128_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
