from __future__ import annotations

import m365_mcp.application_registry as application_registry
import m365_mcp.idempotency_v2 as idempotency_v2
import m365_mcp.state_identity as state_identity


def _identity(application: application_registry.ApplicationKey) -> state_identity.StateIdentity:
    container_kind = (
        "plan" if application is application_registry.ApplicationKey.PLANNER else "mailbox"
    )
    return state_identity.container_state_identity(
        application,
        account_scope="professional_session",
        container_kind=container_kind,
        external_container_id="same-external-id",
    )


def test_idempotency_key_binds_application_identity_and_request_payload() -> None:
    planner = _identity(application_registry.ApplicationKey.PLANNER)
    outlook = _identity(application_registry.ApplicationKey.OUTLOOK)
    payload_a = {"title": "A"}
    payload_b = {"title": "B"}

    planner_a = idempotency_v2.reserve_operation(
        "item.create",
        planner,
        payload_a,
        read_back_required=True,
    )
    planner_b = idempotency_v2.reserve_operation(
        "item.create",
        planner,
        payload_b,
        read_back_required=True,
    )
    outlook_a = idempotency_v2.reserve_operation(
        "item.create",
        outlook,
        payload_a,
        read_back_required=True,
    )

    assert planner_a.key != planner_b.key
    assert planner_a.key != outlook_a.key
    assert planner_a.identity_digest != outlook_a.identity_digest


def test_request_payload_is_reduced_to_digest_only() -> None:
    tenant_value = "tenant-content-that-must-not-be-retained"
    record = idempotency_v2.reserve_operation(
        "item.update",
        _identity(application_registry.ApplicationKey.PLANNER),
        {"value": tenant_value},
        read_back_required=True,
    )

    assert len(record.request_digest) == 64
    assert tenant_value not in repr(record)


def test_completed_operation_associates_result_and_replays_result() -> None:
    identity = _identity(application_registry.ApplicationKey.PLANNER)
    payload = {"value": "semantic-input"}
    reserved = idempotency_v2.reserve_operation(
        "item.update",
        identity,
        payload,
        read_back_required=True,
    )
    completed = idempotency_v2.associate_result(reserved, {"status": "ok"})

    assert completed.phase is idempotency_v2.OperationPhase.COMPLETED
    assert completed.result_digest is not None
    assert idempotency_v2.resolve_retry(
        completed,
        operation="item.update",
        identity=identity,
        payload=payload,
    ) is idempotency_v2.RetryAction.REPLAY_RESULT


def test_binding_mismatch_is_denied() -> None:
    planner = _identity(application_registry.ApplicationKey.PLANNER)
    outlook = _identity(application_registry.ApplicationKey.OUTLOOK)
    payload = {"value": "same"}
    record = idempotency_v2.reserve_operation(
        "item.update",
        planner,
        payload,
        read_back_required=True,
    )

    assert idempotency_v2.resolve_retry(
        record,
        operation="item.update",
        identity=outlook,
        payload=payload,
    ) is idempotency_v2.RetryAction.DENY_BINDING_MISMATCH
    assert idempotency_v2.resolve_retry(
        record,
        operation="item.delete",
        identity=planner,
        payload=payload,
    ) is idempotency_v2.RetryAction.DENY_BINDING_MISMATCH


def test_pre_effect_failure_is_retry_safe() -> None:
    identity = _identity(application_registry.ApplicationKey.PLANNER)
    payload = {"value": "x"}
    record = idempotency_v2.mark_failed_pre_effect(
        idempotency_v2.reserve_operation(
            "item.create",
            identity,
            payload,
            read_back_required=True,
        )
    )

    assert idempotency_v2.resolve_retry(
        record,
        operation="item.create",
        identity=identity,
        payload=payload,
    ) is idempotency_v2.RetryAction.RETRY_SAFE


def test_unverified_effect_without_readback_is_never_blindly_retried() -> None:
    identity = _identity(application_registry.ApplicationKey.PLANNER)
    payload = {"value": "x"}
    record = idempotency_v2.mark_effect_unverified(
        idempotency_v2.reserve_operation(
            "item.create",
            identity,
            payload,
            read_back_required=False,
        )
    )

    assert idempotency_v2.resolve_retry(
        record,
        operation="item.create",
        identity=identity,
        payload=payload,
    ) is idempotency_v2.RetryAction.DO_NOT_RETRY


def test_readback_controls_retry_after_unverified_effect() -> None:
    identity = _identity(application_registry.ApplicationKey.PLANNER)
    payload = {"value": "x"}
    record = idempotency_v2.mark_effect_unverified(
        idempotency_v2.reserve_operation(
            "item.create",
            identity,
            payload,
            read_back_required=True,
        )
    )

    assert idempotency_v2.resolve_retry(
        record,
        operation="item.create",
        identity=identity,
        payload=payload,
        read_back=idempotency_v2.ReadBackOutcome.EFFECT_ABSENT,
    ) is idempotency_v2.RetryAction.RETRY_SAFE
    assert idempotency_v2.resolve_retry(
        record,
        operation="item.create",
        identity=identity,
        payload=payload,
        read_back=idempotency_v2.ReadBackOutcome.EFFECT_PRESENT,
    ) is idempotency_v2.RetryAction.DO_NOT_RETRY
    assert idempotency_v2.resolve_retry(
        record,
        operation="item.create",
        identity=identity,
        payload=payload,
        read_back=idempotency_v2.ReadBackOutcome.AMBIGUOUS,
    ) is idempotency_v2.RetryAction.READ_BACK_REQUIRED
    assert idempotency_v2.resolve_retry(
        record,
        operation="item.create",
        identity=identity,
        payload=payload,
    ) is idempotency_v2.RetryAction.READ_BACK_REQUIRED


def test_completed_state_is_the_only_state_allowed_to_hold_result_digest() -> None:
    digest = "a" * 64
    try:
        idempotency_v2.IdempotencyRecordV2(
            key=digest,
            operation="item.update",
            identity_digest=digest,
            request_digest=digest,
            phase=idempotency_v2.OperationPhase.RESERVED,
            read_back_required=True,
            result_digest=digest,
        )
    except ValueError as exc:
        assert "only completed record" in str(exc)
    else:
        raise AssertionError("non-completed record with result must fail closed")


def test_no_existing_record_allows_first_execution() -> None:
    assert idempotency_v2.resolve_retry(
        None,
        operation="item.read",
        identity=_identity(application_registry.ApplicationKey.PLANNER),
        payload={"id": "opaque"},
    ) is idempotency_v2.RetryAction.EXECUTE
