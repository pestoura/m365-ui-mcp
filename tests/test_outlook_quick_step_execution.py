from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import quick_step_execution, quick_step_models, readiness
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


def _state() -> quick_step_execution.QuickStepMessageState:
    return quick_step_execution.QuickStepMessageState(
        message_key="msg-001",
        folder_key="inbox",
    )


def test_safe_quick_step_applies_synthetic_state_with_readback() -> None:
    updated, result = quick_step_execution.execute_quick_step(
        _state(),
        quick_step_execution.QuickStepExecutionRequest(
            quick_step_key="quick-archive-read",
            message_key="msg-001",
        ),
        readiness=_ready(),
    )
    assert updated.folder_key == "archive"
    assert updated.is_read is True
    assert (
        result.disposition
        is quick_step_execution.QuickStepExecutionDisposition.APPLIED_SYNTHETIC
    )
    assert result.read_back == updated
    assert result.verified is True


def test_outbound_quick_step_is_prepare_only_and_never_partial() -> None:
    outbound = quick_step_models.SyntheticQuickStep(
        quick_step_key="quick-forward",
        display_name="Synthetic forward",
        order=1,
        actions=(
            quick_step_models.QuickStepAction(
                quick_step_models.QuickStepActionKind.MARK_READ
            ),
            quick_step_models.QuickStepAction(
                quick_step_models.QuickStepActionKind.FORWARD_TO_RECIPIENT,
                "recipient-approved",
            ),
        ),
    )
    request = quick_step_execution.QuickStepExecutionRequest(
        quick_step_key=outbound.quick_step_key,
        message_key="msg-001",
    )
    with pytest.raises(PermissionError, match="prepare-only allowance"):
        quick_step_execution.execute_quick_step(
            _state(),
            request,
            readiness=_ready(),
            steps=(outbound,),
        )

    unchanged, result = quick_step_execution.execute_quick_step(
        _state(),
        request,
        readiness=_ready(),
        steps=(outbound,),
        allow_outbound_prepare=True,
    )
    assert unchanged == _state()
    assert unchanged.is_read is False
    assert result.changed is False
    assert (
        result.disposition
        is quick_step_execution.QuickStepExecutionDisposition.PREPARED_OUTBOUND
    )
    assert result.prepared_action_kinds == ("FORWARD_TO_RECIPIENT",)


def test_destructive_quick_step_requires_explicit_allowance() -> None:
    destructive = quick_step_models.SyntheticQuickStep(
        quick_step_key="quick-delete",
        display_name="Synthetic delete",
        order=1,
        actions=(
            quick_step_models.QuickStepAction(
                quick_step_models.QuickStepActionKind.DELETE
            ),
        ),
    )
    request = quick_step_execution.QuickStepExecutionRequest(
        quick_step_key=destructive.quick_step_key,
        message_key="msg-001",
    )
    with pytest.raises(PermissionError, match="explicit policy allowance"):
        quick_step_execution.execute_quick_step(
            _state(),
            request,
            readiness=_ready(),
            steps=(destructive,),
        )

    updated, result = quick_step_execution.execute_quick_step(
        _state(),
        request,
        readiness=_ready(),
        steps=(destructive,),
        allow_destructive=True,
    )
    assert updated.deleted is True
    assert result.changed is True


def test_execution_request_binds_to_idempotency_and_lock() -> None:
    request = quick_step_execution.QuickStepExecutionRequest(
        quick_step_key="quick-followup",
        message_key="msg-001",
    )
    identity = resource_state_identity(
        ApplicationKey.OUTLOOK,
        account_scope="professional_session",
        container_kind="mail",
        external_container_id="inbox",
        resource_kind="message",
        external_resource_id=request.message_key,
    )
    record = reserve_operation(
        "outlook_quick_step_execute",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out067_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
