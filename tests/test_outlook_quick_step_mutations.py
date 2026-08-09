from __future__ import annotations

from dataclasses import replace

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import quick_step_models, quick_step_mutations, readiness
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


def _third_step(*, destructive: bool = False) -> quick_step_models.SyntheticQuickStep:
    action = (
        quick_step_models.QuickStepAction(quick_step_models.QuickStepActionKind.DELETE)
        if destructive
        else quick_step_models.QuickStepAction(
            quick_step_models.QuickStepActionKind.MARK_READ
        )
    )
    return quick_step_models.SyntheticQuickStep(
        quick_step_key="quick-third",
        display_name="Synthetic third Quick Step",
        description="Synthetic lifecycle fixture",
        order=3,
        shortcut=quick_step_models.QuickStepShortcut.CTRL_SHIFT_3,
        actions=(action,),
    )


def test_create_update_reorder_and_delete_have_readback() -> None:
    steps = quick_step_models.default_synthetic_quick_steps()
    third = _third_step()
    steps, created = quick_step_mutations.mutate_quick_steps(
        steps,
        quick_step_mutations.QuickStepMutationRequest(
            quick_step_mutations.QuickStepMutationAction.CREATE,
            third.quick_step_key,
            third,
        ),
        readiness=_ready(),
    )
    assert created.read_back == third
    assert created.verified is True

    followup = next(step for step in steps if step.quick_step_key == "quick-followup")
    moved = replace(
        followup,
        display_name="Synthetic follow up updated",
        order=1,
    )
    steps, updated = quick_step_mutations.mutate_quick_steps(
        steps,
        quick_step_mutations.QuickStepMutationRequest(
            quick_step_mutations.QuickStepMutationAction.UPDATE,
            moved.quick_step_key,
            moved,
        ),
        readiness=_ready(),
    )
    assert tuple(step.quick_step_key for step in steps) == (
        "quick-followup",
        "quick-archive-read",
        "quick-third",
    )
    assert updated.read_back == moved

    steps, deleted = quick_step_mutations.mutate_quick_steps(
        steps,
        quick_step_mutations.QuickStepMutationRequest(
            quick_step_mutations.QuickStepMutationAction.DELETE,
            "quick-third",
        ),
        readiness=_ready(),
    )
    assert deleted.read_back is None
    assert tuple(step.order for step in steps) == (1, 2)


def test_sensitive_definition_requires_explicit_policy_allowance() -> None:
    sensitive = _third_step(destructive=True)
    request = quick_step_mutations.QuickStepMutationRequest(
        quick_step_mutations.QuickStepMutationAction.CREATE,
        sensitive.quick_step_key,
        sensitive,
    )
    with pytest.raises(PermissionError, match="explicit policy allowance"):
        quick_step_mutations.mutate_quick_steps(
            quick_step_models.default_synthetic_quick_steps(),
            request,
            readiness=_ready(),
        )

    updated, result = quick_step_mutations.mutate_quick_steps(
        quick_step_models.default_synthetic_quick_steps(),
        request,
        readiness=_ready(),
        allow_sensitive_definition=True,
    )
    assert updated[-1] == sensitive
    assert result.read_back == sensitive


def test_delete_is_idempotent() -> None:
    request = quick_step_mutations.QuickStepMutationRequest(
        quick_step_mutations.QuickStepMutationAction.DELETE,
        "quick-missing",
    )
    original = quick_step_models.default_synthetic_quick_steps()
    updated, result = quick_step_mutations.mutate_quick_steps(
        original,
        request,
        readiness=_ready(),
    )
    assert updated == original
    assert result.changed is False
    assert result.verified is True


def test_quick_step_lifecycle_binds_to_idempotency_and_lock() -> None:
    request = quick_step_mutations.QuickStepMutationRequest(
        quick_step_mutations.QuickStepMutationAction.DELETE,
        "quick-followup",
    )
    identity = resource_state_identity(
        ApplicationKey.OUTLOOK,
        account_scope="professional_session",
        container_kind="mail_settings",
        external_container_id="quick_steps",
        resource_kind="quick_step",
        external_resource_id=request.quick_step_key,
    )
    record = reserve_operation(
        "outlook_quick_step_lifecycle",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out066_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
