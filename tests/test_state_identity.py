from __future__ import annotations

import m365_mcp.state_identity as state_identity
from m365_mcp.application_registry import ApplicationKey


def test_account_identity_is_application_and_scope_aware() -> None:
    planner = state_identity.account_state_identity(
        ApplicationKey.PLANNER,
        account_scope="professional_session",
    )
    outlook = state_identity.account_state_identity(
        ApplicationKey.OUTLOOK,
        account_scope="professional_session",
    )

    assert planner.level is state_identity.StateIdentityLevel.ACCOUNT
    assert planner.identity_digest != outlook.identity_digest
    assert planner.canonical_payload() == {
        "application": "planner",
        "account_scope": "professional_session",
        "level": "ACCOUNT",
    }


def test_container_identity_discards_raw_external_identifier() -> None:
    raw_id = "sensitive-plan-id-123"
    identity = state_identity.container_state_identity(
        ApplicationKey.PLANNER,
        account_scope="professional_session",
        container_kind="plan",
        external_container_id=raw_id,
    )

    payload = identity.canonical_payload()
    assert identity.level is state_identity.StateIdentityLevel.CONTAINER
    assert payload["container_kind"] == "plan"
    assert len(payload["container_id_digest"]) == 64
    assert raw_id not in str(payload)
    assert raw_id not in identity.identity_digest


def test_resource_identity_is_scoped_by_parent_container() -> None:
    task_a = state_identity.resource_state_identity(
        ApplicationKey.PLANNER,
        account_scope="professional_session",
        container_kind="plan",
        external_container_id="plan-a",
        resource_kind="task",
        external_resource_id="task-1",
    )
    task_b = state_identity.resource_state_identity(
        ApplicationKey.PLANNER,
        account_scope="professional_session",
        container_kind="plan",
        external_container_id="plan-b",
        resource_kind="task",
        external_resource_id="task-1",
    )

    assert task_a.level is state_identity.StateIdentityLevel.RESOURCE
    assert task_a.resource_id_digest == task_b.resource_id_digest
    assert task_a.container_id_digest != task_b.container_id_digest
    assert task_a.identity_digest != task_b.identity_digest


def test_identity_level_changes_canonical_identity() -> None:
    container = state_identity.container_state_identity(
        ApplicationKey.PLANNER,
        account_scope="professional_session",
        container_kind="plan",
        external_container_id="same",
    )
    resource = state_identity.resource_state_identity(
        ApplicationKey.PLANNER,
        account_scope="professional_session",
        container_kind="plan",
        external_container_id="same",
        resource_kind="task",
        external_resource_id="same",
    )

    assert container.identity_digest != resource.identity_digest


def test_planner_compatibility_bridge_maps_external_ids_without_retaining_them() -> None:
    plan = state_identity.planner_external_id_identity(
        "legacy-plan-id",
        resource_kind="plan",
    )
    task = state_identity.planner_external_id_identity(
        "legacy-task-id",
        resource_kind="task",
        container_id="legacy-plan-id",
    )

    assert plan.application is ApplicationKey.PLANNER
    assert plan.level is state_identity.StateIdentityLevel.CONTAINER
    assert plan.container_kind == "plan"
    assert task.level is state_identity.StateIdentityLevel.RESOURCE
    assert task.container_kind == "plan"
    assert task.resource_kind == "task"
    assert "legacy-plan-id" not in str(plan.canonical_payload())
    assert "legacy-task-id" not in str(task.canonical_payload())


def test_invalid_identity_shapes_fail_closed() -> None:
    try:
        state_identity.container_state_identity(
            ApplicationKey.PLANNER,
            account_scope="professional session",
            container_kind="plan",
            external_container_id="plan-1",
        )
    except ValueError as exc:
        assert "account_scope" in str(exc)
    else:
        raise AssertionError("whitespace account scope must fail")

    try:
        state_identity.container_state_identity(
            ApplicationKey.PLANNER,
            account_scope="professional_session",
            container_kind="plan",
            external_container_id=" ",
        )
    except ValueError as exc:
        assert "external identity" in str(exc)
    else:
        raise AssertionError("empty external identity must fail")
