from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import calendar_permission_mutations, readiness
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


def test_permission_grant_upgrade_and_revoke_are_read_back() -> None:
    grants, first = calendar_permission_mutations.apply_calendar_permission_mutation(
        (),
        calendar_permission_mutations.PermissionMutationRequest(
            calendar_permission_mutations.PermissionAction.GRANT,
            "calendar-alpha",
            "grantee-alpha",
            calendar_permission_mutations.CalendarRole.READ,
        ),
        readiness=_ready(),
    )
    assert first.previous_role is calendar_permission_mutations.CalendarRole.NONE
    assert first.read_back_role is calendar_permission_mutations.CalendarRole.READ
    assert first.changed is True
    grants, upgraded = calendar_permission_mutations.apply_calendar_permission_mutation(
        grants,
        calendar_permission_mutations.PermissionMutationRequest(
            calendar_permission_mutations.PermissionAction.GRANT,
            "calendar-alpha",
            "grantee-alpha",
            calendar_permission_mutations.CalendarRole.WRITE,
        ),
        readiness=_ready(),
    )
    assert upgraded.previous_role is calendar_permission_mutations.CalendarRole.READ
    assert upgraded.read_back_role is calendar_permission_mutations.CalendarRole.WRITE
    _, revoked = calendar_permission_mutations.apply_calendar_permission_mutation(
        grants,
        calendar_permission_mutations.PermissionMutationRequest(
            calendar_permission_mutations.PermissionAction.REVOKE,
            "calendar-alpha",
            "grantee-alpha",
        ),
        readiness=_ready(),
    )
    assert revoked.read_back_role is calendar_permission_mutations.CalendarRole.NONE
    assert revoked.verified is True


def test_permission_grant_and_revoke_are_idempotent() -> None:
    grant = calendar_permission_mutations.CalendarPermissionGrant(
        "calendar-alpha",
        "grantee-alpha",
        calendar_permission_mutations.CalendarRole.READ,
    )
    grants, result = calendar_permission_mutations.apply_calendar_permission_mutation(
        (grant,),
        calendar_permission_mutations.PermissionMutationRequest(
            calendar_permission_mutations.PermissionAction.GRANT,
            "calendar-alpha",
            "grantee-alpha",
            calendar_permission_mutations.CalendarRole.READ,
        ),
        readiness=_ready(),
    )
    assert result.changed is False
    assert grants == (grant,)
    _, absent = calendar_permission_mutations.apply_calendar_permission_mutation(
        (),
        calendar_permission_mutations.PermissionMutationRequest(
            calendar_permission_mutations.PermissionAction.REVOKE,
            "calendar-alpha",
            "grantee-alpha",
        ),
        readiness=_ready(),
    )
    assert absent.changed is False


def test_permission_delegate_policy_fails_closed() -> None:
    request = calendar_permission_mutations.PermissionMutationRequest(
        calendar_permission_mutations.PermissionAction.GRANT,
        "calendar-alpha",
        "grantee-alpha",
        calendar_permission_mutations.CalendarRole.DELEGATE,
    )
    with pytest.raises(ValueError, match="forbids DELEGATE"):
        calendar_permission_mutations.apply_calendar_permission_mutation(
            (),
            request,
            readiness=_ready(),
            policy=calendar_permission_mutations.PermissionPolicy(
                allow_delegate_role=False
            ),
        )
    existing = (
        calendar_permission_mutations.CalendarPermissionGrant(
            "calendar-alpha",
            "grantee-existing",
            calendar_permission_mutations.CalendarRole.DELEGATE,
        ),
    )
    with pytest.raises(ValueError, match="additional DELEGATE"):
        calendar_permission_mutations.apply_calendar_permission_mutation(
            existing,
            request,
            readiness=_ready(),
            policy=calendar_permission_mutations.PermissionPolicy(max_delegates=1),
        )


def test_permission_state_is_sorted_and_rejects_identity_shape() -> None:
    grants = (
        calendar_permission_mutations.CalendarPermissionGrant(
            "calendar-alpha",
            "grantee-bravo",
            calendar_permission_mutations.CalendarRole.WRITE,
        ),
        calendar_permission_mutations.CalendarPermissionGrant(
            "calendar-alpha",
            "grantee-alpha",
            calendar_permission_mutations.CalendarRole.READ,
        ),
    )
    state = calendar_permission_mutations.read_calendar_permissions(
        grants,
        calendar_key="calendar-alpha",
        readiness=_ready(),
    )
    assert tuple(item.grantee_key for item in state.grants) == (
        "grantee-alpha",
        "grantee-bravo",
    )
    with pytest.raises(ValueError, match="address identity"):
        calendar_permission_mutations.CalendarPermissionGrant(
            "calendar-alpha",
            "someone@example.invalid",
            calendar_permission_mutations.CalendarRole.READ,
        )


def test_out096_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()


def test_out096_result_contains_no_live_or_browser_material() -> None:
    _, result = calendar_permission_mutations.apply_calendar_permission_mutation(
        (),
        calendar_permission_mutations.PermissionMutationRequest(
            calendar_permission_mutations.PermissionAction.GRANT,
            "calendar-alpha",
            "grantee-alpha",
            calendar_permission_mutations.CalendarRole.READ,
        ),
        readiness=_ready(),
    )
    rendered = repr(result).lower()
    for marker in (
        "https://",
        "http://",
        "selector",
        "xpath",
        "css=",
        "cookie",
        "token",
        "graph.microsoft",
        "@",
    ):
        assert marker not in rendered
