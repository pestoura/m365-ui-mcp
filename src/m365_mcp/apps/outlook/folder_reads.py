"""Synthetic-only Outlook folder listing/navigation reads for OUT-016.

The model exposes a bounded folder hierarchy derived from the OUT-002 fixture.
It carries no mailbox/account/tenant identity, URL, selector, XPath, JavaScript,
navigation command or browser primitive. Navigation here means resolving a
semantic folder position inside a validated synthetic tree, never driving a UI.
"""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_FOLDER_DEPTH = 8
_MAX_FOLDERS = 200


@dataclass(frozen=True)
class SyntheticFolder:
    """Tenant-neutral folder definition bound to one synthetic fixture folder."""

    folder_key: str
    display_name: str
    parent_key: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("folder_key", "parent_key"):
            value = getattr(self, field_name)
            if value is None:
                continue
            invalid = (
                not value
                or value != value.strip()
                or any(char.isspace() for char in value)
            )
            if invalid:
                raise ValueError(f"{field_name} must be a non-empty semantic token")
        if not self.display_name or self.display_name != self.display_name.strip():
            raise ValueError("display_name must be non-empty")
        if self.parent_key is not None and self.parent_key == self.folder_key:
            raise ValueError("folder_key must not be its own parent_key")


@dataclass(frozen=True)
class FolderNode:
    """Bounded read-only folder projection with derived counts."""

    folder_key: str
    display_name: str
    parent_key: str | None
    depth: int
    child_count: int
    message_count: int
    unread_count: int

    def to_projection(self) -> dict[str, object]:
        return {
            "folder_key": self.folder_key,
            "display_name": self.display_name,
            "parent_key": self.parent_key,
            "depth": self.depth,
            "child_count": self.child_count,
            "message_count": self.message_count,
            "unread_count": self.unread_count,
        }


@dataclass(frozen=True)
class FolderListResult:
    """Deterministic folder hierarchy listing for one synthetic fixture."""

    folders: tuple[FolderNode, ...]
    folder_count: int
    max_depth: int
    synthetic: bool


@dataclass(frozen=True)
class FolderNavigationResult:
    """Semantic folder position: the folder, its ancestors and direct children."""

    folder: FolderNode
    ancestor_keys: tuple[str, ...]
    child_keys: tuple[str, ...]
    synthetic: bool

    def to_projection(self) -> dict[str, object]:
        return {
            "folder": self.folder.to_projection(),
            "ancestor_keys": list(self.ancestor_keys),
            "child_keys": list(self.child_keys),
            "synthetic": self.synthetic,
        }


def default_synthetic_folders() -> tuple[SyntheticFolder, ...]:
    """Return the explicit synthetic folder catalog matching the OUT-002 fixture."""
    return (
        SyntheticFolder(folder_key="inbox", display_name="Inbox"),
        SyntheticFolder(folder_key="archive", display_name="Archive"),
        SyntheticFolder(folder_key="sent", display_name="Sent"),
    )


def _validate_catalog(
    fixture: OutlookMockFixture,
    catalog: tuple[SyntheticFolder, ...],
) -> None:
    if not catalog:
        raise ValueError("folder catalog must not be empty")
    if len(catalog) > _MAX_FOLDERS:
        raise ValueError("folder catalog exceeds bounded size")

    keys = tuple(folder.folder_key for folder in catalog)
    if len(set(keys)) != len(keys):
        raise ValueError("folder catalog keys must be unique")
    if set(keys) != set(fixture.folders):
        raise ValueError("folder catalog does not match synthetic fixture folders")

    known = set(keys)
    for folder in catalog:
        if folder.parent_key is not None and folder.parent_key not in known:
            raise ValueError("folder catalog references unknown parent_key")


def _depth_of(folder_key: str, parents: dict[str, str | None]) -> int:
    depth = 0
    seen = {folder_key}
    current = parents[folder_key]
    while current is not None:
        depth += 1
        if depth > _MAX_FOLDER_DEPTH:
            raise ValueError("folder hierarchy exceeds bounded depth")
        if current in seen:
            raise ValueError("folder hierarchy must not contain a cycle")
        seen.add(current)
        current = parents[current]
    return depth


def _build_nodes(
    fixture: OutlookMockFixture,
    catalog: tuple[SyntheticFolder, ...],
) -> tuple[FolderNode, ...]:
    parents = {folder.folder_key: folder.parent_key for folder in catalog}
    children: dict[str, int] = {folder.folder_key: 0 for folder in catalog}
    for folder in catalog:
        if folder.parent_key is not None:
            children[folder.parent_key] += 1

    nodes = []
    for folder in catalog:
        messages = tuple(
            message
            for message in fixture.messages
            if message.folder_key == folder.folder_key
        )
        nodes.append(
            FolderNode(
                folder_key=folder.folder_key,
                display_name=folder.display_name,
                parent_key=folder.parent_key,
                depth=_depth_of(folder.folder_key, parents),
                child_count=children[folder.folder_key],
                message_count=len(messages),
                unread_count=sum(1 for message in messages if not message.is_read),
            )
        )
    return tuple(nodes)


def list_fixture_folders(
    fixture: OutlookMockFixture,
    *,
    readiness: OutlookReadinessReport,
    folders: tuple[SyntheticFolder, ...] | None = None,
) -> FolderListResult:
    """List the bounded synthetic folder hierarchy when read discovery is ready."""
    if not fixture.synthetic:
        raise ValueError("OUT-016 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")

    catalog = default_synthetic_folders() if folders is None else folders
    _validate_catalog(fixture, catalog)
    nodes = _build_nodes(fixture, catalog)
    return FolderListResult(
        folders=nodes,
        folder_count=len(nodes),
        max_depth=max(node.depth for node in nodes),
        synthetic=True,
    )


def navigate_fixture_folder(
    fixture: OutlookMockFixture,
    folder_key: str,
    *,
    readiness: OutlookReadinessReport,
    folders: tuple[SyntheticFolder, ...] | None = None,
) -> FolderNavigationResult:
    """Resolve one synthetic folder position without any UI navigation."""
    if not folder_key or folder_key != folder_key.strip():
        raise ValueError("folder_key must be a non-empty semantic token")

    listing = list_fixture_folders(fixture, readiness=readiness, folders=folders)
    by_key = {node.folder_key: node for node in listing.folders}
    node = by_key.get(folder_key)
    if node is None:
        raise ValueError("unknown synthetic folder_key")

    ancestors: list[str] = []
    current = node.parent_key
    while current is not None:
        ancestors.append(current)
        current = by_key[current].parent_key

    child_keys = tuple(
        sorted(item.folder_key for item in listing.folders if item.parent_key == folder_key)
    )
    return FolderNavigationResult(
        folder=node,
        ancestor_keys=tuple(ancestors),
        child_keys=child_keys,
        synthetic=True,
    )


__all__ = [
    "FolderListResult",
    "FolderNavigationResult",
    "FolderNode",
    "SyntheticFolder",
    "default_synthetic_folders",
    "list_fixture_folders",
    "navigate_fixture_folder",
]
