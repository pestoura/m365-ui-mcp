from __future__ import annotations

import hashlib

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import (
    category_assignment_mutations,
    category_reads,
    mock_ui,
    readiness,
)
from m365_mcp.idempotency_v2 import reserve_operation
from m365_mcp.state_identity import container_state_identity
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


def test_apply_and_remove_batch_are_verified() -> None:
    fixture = mock_ui.default_outlook_fixture()
    categories = category_reads.default_synthetic_categories()
    assignments = category_reads.default_synthetic_category_assignments()
    request = category_assignment_mutations.CategoryAssignmentBatchRequest(
        (
            category_assignment_mutations.CategoryAssignmentMutation(
                category_assignment_mutations.CategoryAssignmentAction.APPLY,
                "msg-001",
                "cat-followup",
            ),
            category_assignment_mutations.CategoryAssignmentMutation(
                category_assignment_mutations.CategoryAssignmentAction.REMOVE,
                "msg-002",
                "cat-followup",
            ),
        )
    )
    updated, result = (
        category_assignment_mutations.apply_fixture_category_assignments(
            fixture,
            request,
            readiness=_ready(),
            categories=categories,
            assignments=assignments,
        )
    )
    pairs = {(item.message_key, item.category_key) for item in updated}
    assert ("msg-001", "cat-followup") in pairs
    assert ("msg-002", "cat-followup") not in pairs
    assert result.changed_count == 2
    assert result.verified is True


def test_repeated_apply_is_domain_idempotent() -> None:
    fixture = mock_ui.default_outlook_fixture()
    assignments = category_reads.default_synthetic_category_assignments()
    request = category_assignment_mutations.CategoryAssignmentBatchRequest(
        (
            category_assignment_mutations.CategoryAssignmentMutation(
                category_assignment_mutations.CategoryAssignmentAction.APPLY,
                "msg-001",
                "cat-project",
            ),
        )
    )
    updated, result = (
        category_assignment_mutations.apply_fixture_category_assignments(
            fixture,
            request,
            readiness=_ready(),
            categories=category_reads.default_synthetic_categories(),
            assignments=assignments,
        )
    )
    assert updated == assignments
    assert result.changed_count == 0


def test_large_batch_requires_dry_run_digest() -> None:
    item = category_assignment_mutations.CategoryAssignmentMutation(
        category_assignment_mutations.CategoryAssignmentAction.APPLY,
        "msg-001",
        "cat-project",
    )
    items = tuple(
        category_assignment_mutations.CategoryAssignmentMutation(
            item.action,
            f"msg-{index:03d}",
            item.category_key,
        )
        for index in range(11)
    )
    with pytest.raises(ValueError, match="dry_run_digest"):
        category_assignment_mutations.CategoryAssignmentBatchRequest(items)

    digest = hashlib.sha256(b"synthetic-dry-run").hexdigest()
    request = category_assignment_mutations.CategoryAssignmentBatchRequest(
        items,
        dry_run_digest=digest,
    )
    assert request.dry_run_digest == digest


def test_unknown_references_fail_before_apply() -> None:
    fixture = mock_ui.default_outlook_fixture()
    request = category_assignment_mutations.CategoryAssignmentBatchRequest(
        (
            category_assignment_mutations.CategoryAssignmentMutation(
                category_assignment_mutations.CategoryAssignmentAction.APPLY,
                "missing",
                "cat-project",
            ),
        )
    )
    with pytest.raises(ValueError, match="unknown synthetic message_key"):
        category_assignment_mutations.apply_fixture_category_assignments(
            fixture,
            request,
            readiness=_ready(),
            categories=category_reads.default_synthetic_categories(),
            assignments=category_reads.default_synthetic_category_assignments(),
        )


def test_batch_binds_to_core_idempotency_and_catalog_lock() -> None:
    request = category_assignment_mutations.CategoryAssignmentBatchRequest(
        (
            category_assignment_mutations.CategoryAssignmentMutation(
                category_assignment_mutations.CategoryAssignmentAction.APPLY,
                "msg-001",
                "cat-project",
            ),
        )
    )
    identity = container_state_identity(
        ApplicationKey.OUTLOOK,
        account_scope="professional_session",
        container_kind="category_assignments",
        external_container_id="primary-category-assignments",
    )
    record = reserve_operation(
        "outlook_category_apply_bulk",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out032_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
