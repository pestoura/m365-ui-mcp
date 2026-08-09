"""Shared-mailbox-scoped synthetic organization mutations for OUT-113."""

from __future__ import annotations

from m365_mcp.apps.outlook.category_assignment_mutations import (
    CategoryAssignmentBatchRequest,
    CategoryAssignmentBatchResult,
    apply_fixture_category_assignments,
)
from m365_mcp.apps.outlook.category_reads import CategoryAssignment, SyntheticCategory
from m365_mcp.apps.outlook.flag_mutations import (
    FlagMutationRequest,
    FlagMutationResult,
    apply_fixture_flag_mutation,
)
from m365_mcp.apps.outlook.folder_mutations import (
    FolderMutationRequest,
    FolderMutationResult,
    apply_fixture_folder_mutation,
)
from m365_mcp.apps.outlook.folder_reads import SyntheticFolder
from m365_mcp.apps.outlook.follow_up_reads import FollowUpFlag
from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport
from m365_mcp.apps.outlook.shared_mailbox_context import SharedMailboxContext


def _gate(context: SharedMailboxContext) -> None:
    if not context.valid:
        raise ValueError("verified shared mailbox context is required")


def apply_shared_category_assignments(
    context: SharedMailboxContext,
    fixture: OutlookMockFixture,
    request: CategoryAssignmentBatchRequest,
    *,
    readiness: OutlookReadinessReport,
    categories: tuple[SyntheticCategory, ...],
    assignments: tuple[CategoryAssignment, ...],
) -> tuple[tuple[CategoryAssignment, ...], CategoryAssignmentBatchResult]:
    _gate(context)
    return apply_fixture_category_assignments(
        fixture,
        request,
        readiness=readiness,
        categories=categories,
        assignments=assignments,
    )


def apply_shared_flag_mutation(
    context: SharedMailboxContext,
    fixture: OutlookMockFixture,
    request: FlagMutationRequest,
    *,
    readiness: OutlookReadinessReport,
    flags: tuple[FollowUpFlag, ...],
) -> tuple[tuple[FollowUpFlag, ...], FlagMutationResult]:
    _gate(context)
    return apply_fixture_flag_mutation(
        fixture,
        request,
        readiness=readiness,
        flags=flags,
    )


def apply_shared_folder_mutation(
    context: SharedMailboxContext,
    fixture: OutlookMockFixture,
    request: FolderMutationRequest,
    *,
    readiness: OutlookReadinessReport,
    folders: tuple[SyntheticFolder, ...],
    favorite_folder_keys: tuple[str, ...] = (),
) -> tuple[
    OutlookMockFixture,
    tuple[SyntheticFolder, ...],
    tuple[str, ...],
    FolderMutationResult,
]:
    _gate(context)
    return apply_fixture_folder_mutation(
        fixture,
        request,
        readiness=readiness,
        folders=folders,
        favorite_folder_keys=favorite_folder_keys,
    )


__all__ = [
    "apply_shared_category_assignments",
    "apply_shared_flag_mutation",
    "apply_shared_folder_mutation",
]
