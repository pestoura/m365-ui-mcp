from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import forwarding_settings, readiness
from m365_mcp.idempotency_v2 import reserve_operation
from m365_mcp.state_identity import resource_state_identity
from m365_mcp.tool_registry import default_tool_registry
from m365_mcp.typed_locks import state_lock


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


def test_forwarding_enable_requires_explicit_policy_and_uses_semantic_destination() -> None:
    current = forwarding_settings.default_synthetic_forwarding_settings()
    desired = forwarding_settings.SyntheticForwardingSettings(
        enabled=True,
        destination_key="recipient-approved",
        keep_copy=True,
    )
    request = forwarding_settings.ForwardingMutationRequest(desired)

    with pytest.raises(PermissionError, match="explicit policy allowance"):
        forwarding_settings.mutate_forwarding_settings(
            current,
            request,
            readiness=_ready(),
        )

    updated, result = forwarding_settings.mutate_forwarding_settings(
        current,
        request,
        readiness=_ready(),
        allow_forwarding_configuration=True,
    )
    assert updated == desired
    assert result.read_back == desired
    assert result.verified is True
    assert result.sensitive_configuration is True
    assert "@" not in str(result.read_back.to_projection())


def test_forwarding_disable_is_allowed_without_reconfiguration_allowance() -> None:
    current = forwarding_settings.SyntheticForwardingSettings(
        enabled=True,
        destination_key="recipient-approved",
        keep_copy=True,
    )
    desired = forwarding_settings.SyntheticForwardingSettings(
        enabled=False,
        destination_key="recipient-approved",
        keep_copy=True,
    )
    updated, result = forwarding_settings.mutate_forwarding_settings(
        current,
        forwarding_settings.ForwardingMutationRequest(desired),
        readiness=_ready(),
    )
    assert updated.enabled is False
    assert result.changed is True
    assert result.sensitive_configuration is False


def test_real_email_shape_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not contain an email address"):
        forwarding_settings.SyntheticForwardingSettings(
            enabled=True,
            destination_key="someone@example.invalid",
        )


def test_forwarding_request_binds_to_idempotency_and_lock() -> None:
    request = forwarding_settings.ForwardingMutationRequest(
        forwarding_settings.SyntheticForwardingSettings(
            enabled=True,
            destination_key="recipient-approved",
            keep_copy=True,
        )
    )
    identity = resource_state_identity(
        ApplicationKey.OUTLOOK,
        account_scope="professional_session",
        container_kind="mail_settings",
        external_container_id="forwarding",
        resource_kind="forwarding_settings",
        external_resource_id="primary",
    )
    record = reserve_operation(
        "outlook_forwarding_settings",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out069_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
