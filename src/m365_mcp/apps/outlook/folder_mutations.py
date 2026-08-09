"""Synthetic-only Outlook folder lifecycle semantics for OUT-039."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from m365_mcp.apps.outlook.folder_reads import SyntheticFolder
from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_FOLDERS = 200
_PROTECTED_FOLDERS = frozenset({"inbox", "archive", "sent"})


class FolderMutationAction(StrEnum):
    CREATE = "CREATE"
    RENAME = "RENAME"
    FAVORITE = "FAVORITE"
    UNFAVORITE = "UNFAVORITE"


@dataclass(frozen=True)
class FolderMutationRequest:
    action: FolderMutationAction
    folder_key: str
    display_name: str | None = None
    parent_key: str | None = None

    def __post_init__(self) -> None:
        for name in ("folder_key", "parent_key"):
            value = getattr(self, name)
            if value is None:
                continue
            if not value or value != value.strip() or any(char.isspace() for char in value):
                raise ValueError(f"{name} must be a non-empty semantic token")
        if self.display_name is not None and (
            not self.display_name or self.display_name != self.display_name.strip()
        ):
            raise ValueError("display_name must be non-empty and trimmed")
        if self.action in {FolderMutationAction.CREATE, FolderMutationAction.RENAME}:
            if self.display_name is None:
                raise ValueError("create/rename requires display_name")
        elif self.display_name is not None or self.parent_key is not None:
            raise ValueError("favorite operations accept only folder_key")
        if self.action is FolderMutationAction.RENAME and self.parent_key is not None:
            raise ValueError("rename must not change parent_key")

    def to_payload(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "folder_key": self.folder_key,
            "display_name": self.display_name,
            "parent_key": self.parent_key,
        }


@dataclass(frozen=True)
class FolderMutationResult:
    action: FolderMutationAction
    folder_key: str
    previous_display_name: str | None
    read_back_display_name: str | None
    previous_favorite: bool
    read_back_favorite: bool
    changed: bool
    verified: bool
    synthetic: bool = True


def apply_fixture_folder_mutation(
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
    """Apply one bounded synthetic folder lifecycle mutation with read-back."""
    if not fixture.synthetic:
        raise ValueError("OUT-039 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")

    by_key = {folder.folder_key: folder for folder in folders}
    if set(by_key) != set(fixture.folders):
        raise ValueError("folder catalog does not match synthetic fixture")
    if len(by_key) != len(folders):
        raise ValueError("folder catalog keys must be unique")
    if any(key not in by_key for key in favorite_folder_keys):
        raise ValueError("favorite folder references unknown folder")

    current = by_key.get(request.folder_key)
    previous_name = current.display_name if current is not None else None
    previous_favorite = request.folder_key in favorite_folder_keys
    updated_fixture = fixture
    updated_folders = folders
    updated_favorites = favorite_folder_keys

    if request.action is FolderMutationAction.CREATE:
        if current is not None:
            raise ValueError("folder_key already exists")
        if len(folders) >= _MAX_FOLDERS:
            raise ValueError("folder catalog exceeds bounded size")
        if request.parent_key is not None and request.parent_key not in by_key:
            raise ValueError("parent_key does not exist")
        if request.display_name is None:
            raise RuntimeError("validated display_name unexpectedly absent")
        created = SyntheticFolder(
            folder_key=request.folder_key,
            display_name=request.display_name,
            parent_key=request.parent_key,
        )
        updated_folders = folders + (created,)
        updated_fixture = replace(fixture, folders=fixture.folders + (request.folder_key,))
    elif request.action is FolderMutationAction.RENAME:
        if current is None:
            raise ValueError("folder_key does not exist")
        if request.folder_key in _PROTECTED_FOLDERS:
            raise ValueError("protected synthetic folder cannot be renamed")
        if request.display_name is None:
            raise RuntimeError("validated display_name unexpectedly absent")
        replacement = replace(current, display_name=request.display_name)
        updated_folders = tuple(
            replacement if folder.folder_key == request.folder_key else folder
            for folder in folders
        )
    elif request.action is FolderMutationAction.FAVORITE:
        if current is None:
            raise ValueError("folder_key does not exist")
        if not previous_favorite:
            updated_favorites = favorite_folder_keys + (request.folder_key,)
    else:
        if current is None:
            raise ValueError("folder_key does not exist")
        updated_favorites = tuple(
            key for key in favorite_folder_keys if key != request.folder_key
        )

    read_back = next(
        (folder for folder in updated_folders if folder.folder_key == request.folder_key),
        None,
    )
    read_back_name = read_back.display_name if read_back is not None else None
    read_back_favorite = request.folder_key in updated_favorites

    if request.action is FolderMutationAction.CREATE:
        verified = read_back is not None and request.folder_key in updated_fixture.folders
        changed = True
    elif request.action is FolderMutationAction.RENAME:
        verified = read_back_name == request.display_name
        changed = previous_name != read_back_name
    elif request.action is FolderMutationAction.FAVORITE:
        verified = read_back_favorite
        changed = not previous_favorite
    else:
        verified = not read_back_favorite
        changed = previous_favorite
    if not verified:
        raise RuntimeError("synthetic read-back did not prove requested folder state")

    return updated_fixture, updated_folders, updated_favorites, FolderMutationResult(
        action=request.action,
        folder_key=request.folder_key,
        previous_display_name=previous_name,
        read_back_display_name=read_back_name,
        previous_favorite=previous_favorite,
        read_back_favorite=read_back_favorite,
        changed=changed,
        verified=True,
    )


__all__ = [
    "FolderMutationAction",
    "FolderMutationRequest",
    "FolderMutationResult",
    "apply_fixture_folder_mutation",
]
