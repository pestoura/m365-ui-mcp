from __future__ import annotations

import m365_mcp.application_registry as application_registry
import m365_mcp.state_identity as state_identity
import m365_mcp.typed_locks as typed_locks


def _plan_identity(plan_id: str = "plan-a") -> state_identity.StateIdentity:
    return state_identity.container_state_identity(
        application_registry.ApplicationKey.PLANNER,
        account_scope="professional_session",
        container_kind="plan",
        external_container_id=plan_id,
    )


def _task_identity(
    task_id: str = "task-a",
    *,
    plan_id: str = "plan-a",
) -> state_identity.StateIdentity:
    return state_identity.resource_state_identity(
        application_registry.ApplicationKey.PLANNER,
        account_scope="professional_session",
        container_kind="plan",
        external_container_id=plan_id,
        resource_kind="task",
        external_resource_id=task_id,
    )


def test_profile_and_account_locks_discard_opaque_raw_keys() -> None:
    profile_raw = "/home/user/browser-profile"
    account_raw = "opaque-professional-account"

    profile = typed_locks.profile_lock(profile_raw)
    account = typed_locks.account_lock(account_raw)

    assert profile.scope is typed_locks.LockScope.PROFILE
    assert account.scope is typed_locks.LockScope.ACCOUNT
    assert profile_raw not in str(profile.canonical_payload())
    assert account_raw not in str(account.canonical_payload())
    assert len(profile.lock_key) == 64
    assert len(account.lock_key) == 64


def test_application_locks_separate_planner_and_outlook() -> None:
    planner = typed_locks.application_lock(
        "account-a",
        application_registry.ApplicationKey.PLANNER,
    )
    outlook = typed_locks.application_lock(
        "account-a",
        application_registry.ApplicationKey.OUTLOOK,
    )

    assert planner.scope is typed_locks.LockScope.APPLICATION
    assert outlook.scope is typed_locks.LockScope.APPLICATION
    assert planner.lock_key != outlook.lock_key


def test_state_locks_use_core_037_container_and_resource_identity() -> None:
    container = typed_locks.state_lock("account-a", _plan_identity())
    resource = typed_locks.state_lock("account-a", _task_identity())

    assert container.scope is typed_locks.LockScope.CONTAINER
    assert resource.scope is typed_locks.LockScope.RESOURCE
    assert container.application is application_registry.ApplicationKey.PLANNER
    assert resource.application is application_registry.ApplicationKey.PLANNER
    assert container.state_identity_digest == _plan_identity().identity_digest
    assert resource.state_identity_digest == _task_identity().identity_digest
    assert container.lock_key != resource.lock_key


def test_same_resource_in_different_container_has_different_lock() -> None:
    first = typed_locks.state_lock(
        "account-a",
        _task_identity("same-task", plan_id="plan-a"),
    )
    second = typed_locks.state_lock(
        "account-a",
        _task_identity("same-task", plan_id="plan-b"),
    )

    assert first.lock_key != second.lock_key


def test_same_state_under_different_accounts_has_different_lock() -> None:
    identity = _plan_identity()
    first = typed_locks.state_lock("account-a", identity)
    second = typed_locks.state_lock("account-b", identity)

    assert first.state_identity_digest == second.state_identity_digest
    assert first.lock_key != second.lock_key


def test_canonical_order_is_broad_to_narrow_and_deduplicated() -> None:
    profile = typed_locks.profile_lock("profile-a")
    account = typed_locks.account_lock("account-a")
    application = typed_locks.application_lock(
        "account-a",
        application_registry.ApplicationKey.PLANNER,
    )
    container = typed_locks.state_lock("account-a", _plan_identity())
    resource = typed_locks.state_lock("account-a", _task_identity())

    ordered = typed_locks.canonical_lock_order(
        (resource, account, container, profile, application, resource)
    )

    assert tuple(lock.scope for lock in ordered) == (
        typed_locks.LockScope.PROFILE,
        typed_locks.LockScope.ACCOUNT,
        typed_locks.LockScope.APPLICATION,
        typed_locks.LockScope.CONTAINER,
        typed_locks.LockScope.RESOURCE,
    )
    assert len(ordered) == 5


def test_account_state_identity_cannot_create_narrow_state_lock() -> None:
    identity = state_identity.account_state_identity(
        application_registry.ApplicationKey.PLANNER,
        account_scope="professional_session",
    )

    try:
        typed_locks.state_lock("account-a", identity)
    except ValueError as exc:
        assert "account-level StateIdentity" in str(exc)
    else:
        raise AssertionError("account StateIdentity must not create a state lock")


def test_legacy_planner_lock_names_have_explicit_mapping() -> None:
    assert typed_locks.legacy_planner_lock_scope("browser_profile") is typed_locks.LockScope.PROFILE
    assert typed_locks.legacy_planner_lock_scope("session") is typed_locks.LockScope.ACCOUNT
    assert typed_locks.legacy_planner_lock_scope("plan") is typed_locks.LockScope.CONTAINER
    assert typed_locks.legacy_planner_lock_scope("bucket") is typed_locks.LockScope.RESOURCE
    assert typed_locks.legacy_planner_lock_scope("task") is typed_locks.LockScope.RESOURCE

    try:
        typed_locks.legacy_planner_lock_scope("unknown")
    except ValueError as exc:
        assert "unknown legacy Planner lock type" in str(exc)
    else:
        raise AssertionError("unknown legacy lock type must fail closed")
