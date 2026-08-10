from __future__ import annotations

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
    shared_mailbox_context,
    shared_mailbox_organization,
)
from m365_mcp.tool_registry import default_tool_registry


def _ready() -> readiness.OutlookReadinessReport:
    return readiness.OutlookReadinessReport(
        state=readiness.OutlookReadinessState.DISCOVERY_READY,
        primary_context_verified=True,
        shared_context_verified=True,
        candidate_count=1,
        observed_count=1,
        blocked_count=0,
        reattestation_count=0,
    )


def _context(*, valid: bool) -> shared_mailbox_context.SharedMailboxContext:
    return shared_mailbox_context.SharedMailboxContext(
        state=(
            shared_mailbox_context.SharedMailboxContextState.VERIFIED
            if valid
            else shared_mailbox_context.SharedMailboxContextState.UNVERIFIED
        ),
        primary_context_verified=True,
        shared_shell_verified=valid,
        scope_digest="a" * 64 if valid else None,
        evidence_digest="b" * 64 if valid else None,
    )


def test_shared_category_mutation_reuses_existing_read_back() -> None:
    fixture = mock_ui.default_outlook_fixture()
    categories = category_reads.default_synthetic_categories()
    assignments = category_reads.default_synthetic_category_assignments()
    request = category_assignment_mutations.CategoryAssignmentBatchRequest(
        items=(
            category_assignment_mutations.CategoryAssignmentMutation(
                category_assignment_mutations.CategoryAssignmentAction.APPLY,
                "msg-001",
                "cat-followup",
            ),
        )
    )
    updated, result = shared_mailbox_organization.apply_shared_category_assignments(
        _context(valid=True),
        fixture,
        request,
        readiness=_ready(),
        categories=categories,
        assignments=assignments,
    )
    assert result.verified is True
    assert any(
        item.message_key == "msg-001" and item.category_key == "cat-followup"
        for item in updated
    )


def test_shared_organization_fails_closed_without_verified_scope() -> None:
    fixture = mock_ui.default_outlook_fixture()
    request = category_assignment_mutations.CategoryAssignmentBatchRequest(
        items=(
            category_assignment_mutations.CategoryAssignmentMutation(
                category_assignment_mutations.CategoryAssignmentAction.REMOVE,
                "msg-001",
                "cat-project",
            ),
        )
    )
    with pytest.raises(ValueError, match="verified shared mailbox context"):
        shared_mailbox_organization.apply_shared_category_assignments(
            _context(valid=False),
            fixture,
            request,
            readiness=_ready(),
            categories=category_reads.default_synthetic_categories(),
            assignments=category_reads.default_synthetic_category_assignments(),
        )


def test_out113_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
