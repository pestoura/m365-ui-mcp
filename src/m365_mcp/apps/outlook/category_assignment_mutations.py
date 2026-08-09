"""Synthetic-only Outlook category assignment/bulk semantics for OUT-032.

All changes are applied atomically to tenant-neutral CategoryAssignment tuples
and verified through OUT-017 reads. Large synthetic batches require a dry-run
digest, modelling the production blast-radius gate without exposing Outlook.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.category_reads import (
    CategoryAssignment,
    SyntheticCategory,
    read_fixture_message_categories,
)
from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_BATCH = 50
_DRY_RUN_THRESHOLD = 10


class CategoryAssignmentAction(StrEnum):
    APPLY = "APPLY"
    REMOVE = "REMOVE"


def _validate_digest(value: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("dry_run_digest must be lowercase SHA-256 hex")


@dataclass(frozen=True)
class CategoryAssignmentMutation:
    action: CategoryAssignmentAction
    message_key: str
    category_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.action, CategoryAssignmentAction):
            raise ValueError("action must be a closed CategoryAssignmentAction")
        for field_name in ("message_key", "category_key"):
            value = getattr(self, field_name)
            invalid = (
                not value
                or value != value.strip()
                or any(char.isspace() for char in value)
            )
            if invalid:
                raise ValueError(f"{field_name} must be a non-empty semantic token")

    def to_payload(self) -> dict[str, str]:
        return {
            "action": self.action.value,
            "message_key": self.message_key,
            "category_key": self.category_key,
        }


@dataclass(frozen=True)
class CategoryAssignmentBatchRequest:
    items: tuple[CategoryAssignmentMutation, ...]
    dry_run_digest: str | None = None

    def __post_init__(self) -> None:
        if not self.items or len(self.items) > _MAX_BATCH:
            raise ValueError("category assignment batch must be non-empty and bounded")
        identities = tuple(
            (item.action, item.message_key, item.category_key) for item in self.items
        )
        if len(set(identities)) != len(identities):
            raise ValueError("category assignment batch must not contain duplicate operations")
        if len(self.items) > _DRY_RUN_THRESHOLD and self.dry_run_digest is None:
            raise ValueError("large category assignment batch requires dry_run_digest")
        if self.dry_run_digest is not None:
            _validate_digest(self.dry_run_digest)

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "items": [item.to_payload() for item in self.items],
        }
        if self.dry_run_digest is not None:
            payload["dry_run_digest"] = self.dry_run_digest
        return payload


@dataclass(frozen=True)
class CategoryAssignmentBatchResult:
    changed_count: int
    affected_message_keys: tuple[str, ...]
    verified: bool
    synthetic: bool = True


def _validate_references(
    fixture: OutlookMockFixture,
    categories: tuple[SyntheticCategory, ...],
    request: CategoryAssignmentBatchRequest,
) -> None:
    message_keys = {message.message_key for message in fixture.messages}
    category_keys = {category.category_key for category in categories}
    for item in request.items:
        if item.message_key not in message_keys:
            raise ValueError("category mutation references unknown synthetic message_key")
        if item.category_key not in category_keys:
            raise ValueError("category mutation references unknown synthetic category_key")


def apply_fixture_category_assignments(
    fixture: OutlookMockFixture,
    request: CategoryAssignmentBatchRequest,
    *,
    readiness: OutlookReadinessReport,
    categories: tuple[SyntheticCategory, ...],
    assignments: tuple[CategoryAssignment, ...],
) -> tuple[tuple[CategoryAssignment, ...], CategoryAssignmentBatchResult]:
    """Apply one bounded synthetic batch and verify every affected message."""
    if not fixture.synthetic:
        raise ValueError("OUT-032 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    _validate_references(fixture, categories, request)

    pairs = {(item.message_key, item.category_key) for item in assignments}
    before = set(pairs)
    for item in request.items:
        pair = (item.message_key, item.category_key)
        if item.action is CategoryAssignmentAction.APPLY:
            pairs.add(pair)
        else:
            pairs.discard(pair)

    updated = tuple(
        CategoryAssignment(message_key=message_key, category_key=category_key)
        for message_key, category_key in sorted(pairs)
    )
    affected = tuple(sorted({item.message_key for item in request.items}))
    for message_key in affected:
        state = read_fixture_message_categories(
            fixture,
            message_key,
            readiness=readiness,
            categories=categories,
            assignments=updated,
        )
        expected = tuple(
            sorted(
                category_key
                for candidate_message, category_key in pairs
                if candidate_message == message_key
            )
        )
        if state.category_keys != expected:
            raise RuntimeError("synthetic category read-back did not match applied batch")

    return (
        updated,
        CategoryAssignmentBatchResult(
            changed_count=len(before.symmetric_difference(pairs)),
            affected_message_keys=affected,
            verified=True,
        ),
    )


__all__ = [
    "CategoryAssignmentAction",
    "CategoryAssignmentBatchRequest",
    "CategoryAssignmentBatchResult",
    "CategoryAssignmentMutation",
    "apply_fixture_category_assignments",
]
