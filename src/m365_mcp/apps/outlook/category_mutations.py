"""Synthetic-only Outlook category lifecycle governance for OUT-031.

The module operates only on tenant-neutral synthetic category tuples and uses
OUT-017 reads for immediate read-back. Outlook remains RESERVED, so these
semantics are not exposed as a public mutation or browser operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.category_reads import (
    CategoryAssignment,
    CategoryColorToken,
    SyntheticCategory,
    list_fixture_categories,
)
from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


class CategoryMutationAction(StrEnum):
    """Closed OUT-031 category lifecycle actions."""

    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


@dataclass(frozen=True)
class CategoryMutationRequest:
    """One bounded category lifecycle request."""

    action: CategoryMutationAction
    category_key: str
    display_name: str | None = None
    color_token: CategoryColorToken | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.action, CategoryMutationAction):
            raise ValueError("action must be a closed CategoryMutationAction")
        invalid_key = (
            not self.category_key
            or self.category_key != self.category_key.strip()
            or any(char.isspace() for char in self.category_key)
        )
        if invalid_key:
            raise ValueError("category_key must be a non-empty semantic token")

        if self.action is CategoryMutationAction.DELETE:
            if self.display_name is not None or self.color_token is not None:
                raise ValueError("delete must not carry category replacement fields")
            return

        if self.display_name is not None:
            if not self.display_name or self.display_name != self.display_name.strip():
                raise ValueError("display_name must be non-empty and trimmed")
        if self.color_token is not None and not isinstance(
            self.color_token,
            CategoryColorToken,
        ):
            raise ValueError("color_token must be a closed CategoryColorToken")
        if self.action is CategoryMutationAction.CREATE and self.display_name is None:
            raise ValueError("create requires display_name")

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "action": self.action.value,
            "category_key": self.category_key,
        }
        if self.display_name is not None:
            payload["display_name"] = self.display_name
        if self.color_token is not None:
            payload["color_token"] = self.color_token.value
        return payload


@dataclass(frozen=True)
class CategoryMutationResult:
    """Verified synthetic category lifecycle outcome."""

    action: CategoryMutationAction
    category_key: str
    changed: bool
    exists_after: bool
    read_back_name: str | None
    read_back_color: CategoryColorToken | None
    verified: bool
    synthetic: bool = True


def _find(
    categories: tuple[SyntheticCategory, ...],
    category_key: str,
) -> SyntheticCategory | None:
    return next(
        (item for item in categories if item.category_key == category_key),
        None,
    )


def apply_fixture_category_mutation(
    fixture: OutlookMockFixture,
    request: CategoryMutationRequest,
    *,
    readiness: OutlookReadinessReport,
    categories: tuple[SyntheticCategory, ...],
    assignments: tuple[CategoryAssignment, ...],
) -> tuple[tuple[SyntheticCategory, ...], CategoryMutationResult]:
    """Apply one synthetic lifecycle mutation and verify it through OUT-017."""
    if not fixture.synthetic:
        raise ValueError("OUT-031 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")

    current = _find(categories, request.category_key)
    changed = False

    if request.action is CategoryMutationAction.CREATE:
        requested = SyntheticCategory(
            category_key=request.category_key,
            display_name=request.display_name or "",
            color_token=request.color_token or CategoryColorToken.NEUTRAL,
        )
        if current is None:
            updated = (*categories, requested)
            changed = True
        elif current == requested:
            updated = categories
        else:
            raise ValueError("category_key already exists with different definition")

    elif request.action is CategoryMutationAction.UPDATE:
        if current is None:
            raise ValueError("synthetic category_key not found")
        replacement = SyntheticCategory(
            category_key=current.category_key,
            display_name=request.display_name or current.display_name,
            color_token=request.color_token or current.color_token,
        )
        updated = tuple(
            replacement if item.category_key == request.category_key else item
            for item in categories
        )
        changed = replacement != current

    else:
        if any(item.category_key == request.category_key for item in assignments):
            raise ValueError("category delete blocked while synthetic assignments exist")
        updated = tuple(
            item for item in categories if item.category_key != request.category_key
        )
        changed = current is not None

    read_back = list_fixture_categories(
        fixture,
        readiness=readiness,
        categories=updated,
        assignments=assignments,
    )
    projected = next(
        (
            item
            for item in read_back.categories
            if item.category_key == request.category_key
        ),
        None,
    )
    exists_after = projected is not None
    if request.action is CategoryMutationAction.DELETE:
        verified = not exists_after
    else:
        verified = projected is not None

    if not verified:
        raise RuntimeError("synthetic category read-back did not prove requested state")

    return (
        updated,
        CategoryMutationResult(
            action=request.action,
            category_key=request.category_key,
            changed=changed,
            exists_after=exists_after,
            read_back_name=projected.display_name if projected is not None else None,
            read_back_color=projected.color_token if projected is not None else None,
            verified=True,
        ),
    )


__all__ = [
    "CategoryMutationAction",
    "CategoryMutationRequest",
    "CategoryMutationResult",
    "apply_fixture_category_mutation",
]
