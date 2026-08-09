"""Synthetic-only Outlook category listing/read state for OUT-017.

Categories are modelled as a bounded, tenant-neutral vocabulary plus explicit
message assignments. The model carries no mailbox/account/tenant identity, URL,
selector, XPath, JavaScript or browser primitive, and performs no mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_CATEGORIES = 100
_MAX_ASSIGNMENTS_PER_MESSAGE = 25


class CategoryColorToken(StrEnum):
    """Closed, tenant-neutral colour vocabulary with no rendering semantics."""

    NEUTRAL = "NEUTRAL"
    RED = "RED"
    ORANGE = "ORANGE"
    YELLOW = "YELLOW"
    GREEN = "GREEN"
    BLUE = "BLUE"
    PURPLE = "PURPLE"


@dataclass(frozen=True)
class SyntheticCategory:
    """Tenant-neutral category definition."""

    category_key: str
    display_name: str
    color_token: CategoryColorToken = CategoryColorToken.NEUTRAL

    def __post_init__(self) -> None:
        invalid = (
            not self.category_key
            or self.category_key != self.category_key.strip()
            or any(char.isspace() for char in self.category_key)
        )
        if invalid:
            raise ValueError("category_key must be a non-empty semantic token")
        if not self.display_name or self.display_name != self.display_name.strip():
            raise ValueError("display_name must be non-empty")
        if not isinstance(self.color_token, CategoryColorToken):
            raise ValueError("color_token must be a closed CategoryColorToken")


@dataclass(frozen=True)
class CategoryAssignment:
    """Explicit synthetic message-to-category assignment."""

    message_key: str
    category_key: str

    def __post_init__(self) -> None:
        for field_name in ("message_key", "category_key"):
            value = getattr(self, field_name)
            invalid = (
                not value
                or value != value.strip()
                or any(char.isspace() for char in value)
            )
            if invalid:
                raise ValueError(f"{field_name} must be a non-empty semantic token")


@dataclass(frozen=True)
class CategoryUsage:
    """Bounded category projection with derived assignment counts."""

    category_key: str
    display_name: str
    color_token: CategoryColorToken
    assigned_message_count: int

    def to_projection(self) -> dict[str, object]:
        return {
            "category_key": self.category_key,
            "display_name": self.display_name,
            "color_token": self.color_token.value,
            "assigned_message_count": self.assigned_message_count,
        }


@dataclass(frozen=True)
class CategoryListResult:
    """Deterministic bounded category catalog with usage counts."""

    categories: tuple[CategoryUsage, ...]
    category_count: int
    assigned_message_count: int
    synthetic: bool


@dataclass(frozen=True)
class MessageCategoryState:
    """Read-only category state for one synthetic message."""

    message_key: str
    category_keys: tuple[str, ...]
    category_count: int
    synthetic: bool

    def to_projection(self) -> dict[str, object]:
        return {
            "message_key": self.message_key,
            "category_keys": list(self.category_keys),
            "category_count": self.category_count,
            "synthetic": self.synthetic,
        }


def default_synthetic_categories() -> tuple[SyntheticCategory, ...]:
    """Return the explicit synthetic category vocabulary."""
    return (
        SyntheticCategory(
            category_key="cat-project",
            display_name="Synthetic Project",
            color_token=CategoryColorToken.BLUE,
        ),
        SyntheticCategory(
            category_key="cat-followup",
            display_name="Synthetic Follow Up",
            color_token=CategoryColorToken.YELLOW,
        ),
    )


def default_synthetic_category_assignments() -> tuple[CategoryAssignment, ...]:
    """Return the explicit synthetic message-to-category assignments."""
    return (
        CategoryAssignment(message_key="msg-001", category_key="cat-project"),
        CategoryAssignment(message_key="msg-002", category_key="cat-followup"),
    )


def _validate(
    fixture: OutlookMockFixture,
    categories: tuple[SyntheticCategory, ...],
    assignments: tuple[CategoryAssignment, ...],
) -> None:
    if len(categories) > _MAX_CATEGORIES:
        raise ValueError("category catalog exceeds bounded size")

    keys = tuple(category.category_key for category in categories)
    if len(set(keys)) != len(keys):
        raise ValueError("category catalog keys must be unique")

    known_categories = set(keys)
    known_messages = {message.message_key for message in fixture.messages}
    pairs = tuple((item.message_key, item.category_key) for item in assignments)
    if len(set(pairs)) != len(pairs):
        raise ValueError("category assignments must be unique")

    per_message: dict[str, int] = {}
    for assignment in assignments:
        if assignment.category_key not in known_categories:
            raise ValueError("category assignment references unknown category_key")
        if assignment.message_key not in known_messages:
            raise ValueError("category assignment references unknown synthetic message_key")
        per_message[assignment.message_key] = per_message.get(assignment.message_key, 0) + 1
        if per_message[assignment.message_key] > _MAX_ASSIGNMENTS_PER_MESSAGE:
            raise ValueError("message exceeds bounded category assignment count")


def list_fixture_categories(
    fixture: OutlookMockFixture,
    *,
    readiness: OutlookReadinessReport,
    categories: tuple[SyntheticCategory, ...] | None = None,
    assignments: tuple[CategoryAssignment, ...] | None = None,
) -> CategoryListResult:
    """List the synthetic category vocabulary with bounded usage counts."""
    if not fixture.synthetic:
        raise ValueError("OUT-017 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")

    catalog = default_synthetic_categories() if categories is None else categories
    links = (
        default_synthetic_category_assignments() if assignments is None else assignments
    )
    _validate(fixture, catalog, links)

    usage = tuple(
        CategoryUsage(
            category_key=category.category_key,
            display_name=category.display_name,
            color_token=category.color_token,
            assigned_message_count=sum(
                1 for item in links if item.category_key == category.category_key
            ),
        )
        for category in catalog
    )
    return CategoryListResult(
        categories=usage,
        category_count=len(usage),
        assigned_message_count=len({item.message_key for item in links}),
        synthetic=True,
    )


def read_fixture_message_categories(
    fixture: OutlookMockFixture,
    message_key: str,
    *,
    readiness: OutlookReadinessReport,
    categories: tuple[SyntheticCategory, ...] | None = None,
    assignments: tuple[CategoryAssignment, ...] | None = None,
) -> MessageCategoryState:
    """Read deterministic category state for one existing synthetic message."""
    if not message_key or message_key != message_key.strip():
        raise ValueError("message_key must be a non-empty semantic token")
    if not fixture.synthetic:
        raise ValueError("OUT-017 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")

    if not any(message.message_key == message_key for message in fixture.messages):
        raise ValueError("synthetic message_key not found")

    catalog = default_synthetic_categories() if categories is None else categories
    links = (
        default_synthetic_category_assignments() if assignments is None else assignments
    )
    _validate(fixture, catalog, links)

    selected = tuple(
        sorted(item.category_key for item in links if item.message_key == message_key)
    )
    return MessageCategoryState(
        message_key=message_key,
        category_keys=selected,
        category_count=len(selected),
        synthetic=True,
    )


__all__ = [
    "CategoryAssignment",
    "CategoryColorToken",
    "CategoryListResult",
    "CategoryUsage",
    "MessageCategoryState",
    "SyntheticCategory",
    "default_synthetic_categories",
    "default_synthetic_category_assignments",
    "list_fixture_categories",
    "read_fixture_message_categories",
]
