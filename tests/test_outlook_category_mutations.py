from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import category_mutations, category_reads, mock_ui, readiness
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


def test_create_update_delete_with_read_back() -> None:
    fixture = mock_ui.default_outlook_fixture()
    categories = category_reads.default_synthetic_categories()
    assignments = category_reads.default_synthetic_category_assignments()

    created, create_result = category_mutations.apply_fixture_category_mutation(
        fixture,
        category_mutations.CategoryMutationRequest(
            category_mutations.CategoryMutationAction.CREATE,
            "cat-new",
            "Synthetic New",
            category_reads.CategoryColorToken.GREEN,
        ),
        readiness=_ready(),
        categories=categories,
        assignments=assignments,
    )
    assert create_result.changed is True
    assert create_result.exists_after is True
    assert create_result.verified is True

    updated, update_result = category_mutations.apply_fixture_category_mutation(
        fixture,
        category_mutations.CategoryMutationRequest(
            category_mutations.CategoryMutationAction.UPDATE,
            "cat-new",
            "Synthetic Updated",
            category_reads.CategoryColorToken.PURPLE,
        ),
        readiness=_ready(),
        categories=created,
        assignments=assignments,
    )
    assert update_result.read_back_name == "Synthetic Updated"
    assert update_result.read_back_color is category_reads.CategoryColorToken.PURPLE

    deleted, delete_result = category_mutations.apply_fixture_category_mutation(
        fixture,
        category_mutations.CategoryMutationRequest(
            category_mutations.CategoryMutationAction.DELETE,
            "cat-new",
        ),
        readiness=_ready(),
        categories=updated,
        assignments=assignments,
    )
    assert all(item.category_key != "cat-new" for item in deleted)
    assert delete_result.exists_after is False
    assert delete_result.verified is True


def test_delete_assigned_category_fails_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    with pytest.raises(ValueError, match="assignments exist"):
        category_mutations.apply_fixture_category_mutation(
            fixture,
            category_mutations.CategoryMutationRequest(
                category_mutations.CategoryMutationAction.DELETE,
                "cat-project",
            ),
            readiness=_ready(),
            categories=category_reads.default_synthetic_categories(),
            assignments=category_reads.default_synthetic_category_assignments(),
        )


def test_create_is_domain_idempotent_and_conflicts_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    categories = category_reads.default_synthetic_categories()
    assignments = category_reads.default_synthetic_category_assignments()
    request = category_mutations.CategoryMutationRequest(
        category_mutations.CategoryMutationAction.CREATE,
        "cat-project",
        "Synthetic Project",
        category_reads.CategoryColorToken.BLUE,
    )
    unchanged, result = category_mutations.apply_fixture_category_mutation(
        fixture,
        request,
        readiness=_ready(),
        categories=categories,
        assignments=assignments,
    )
    assert unchanged == categories
    assert result.changed is False

    with pytest.raises(ValueError, match="different definition"):
        category_mutations.apply_fixture_category_mutation(
            fixture,
            category_mutations.CategoryMutationRequest(
                category_mutations.CategoryMutationAction.CREATE,
                "cat-project",
                "Different",
            ),
            readiness=_ready(),
            categories=categories,
            assignments=assignments,
        )


def test_request_binds_to_core_idempotency_and_lock_models() -> None:
    request = category_mutations.CategoryMutationRequest(
        category_mutations.CategoryMutationAction.CREATE,
        "cat-new",
        "Synthetic New",
    )
    identity = container_state_identity(
        ApplicationKey.OUTLOOK,
        account_scope="professional_session",
        container_kind="category_catalog",
        external_container_id="primary-categories",
    )
    record = reserve_operation(
        "outlook_category_create",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.identity_digest == identity.identity_digest
    assert record.read_back_required is True
    assert lock.application is ApplicationKey.OUTLOOK


def test_out031_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
