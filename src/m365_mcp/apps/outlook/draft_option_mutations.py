"""Closed synthetic draft importance/sensitivity options for OUT-045."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from m365_mcp.apps.outlook.draft_models import SyntheticDraft
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


class DraftImportance(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


class DraftSensitivity(StrEnum):
    NORMAL = "NORMAL"
    PERSONAL = "PERSONAL"
    PRIVATE = "PRIVATE"
    CONFIDENTIAL = "CONFIDENTIAL"


@dataclass(frozen=True)
class DraftOptionRequest:
    draft_key: str
    importance: DraftImportance | None = None
    sensitivity: DraftSensitivity | None = None

    def __post_init__(self) -> None:
        if (
            not self.draft_key
            or self.draft_key != self.draft_key.strip()
            or any(char.isspace() for char in self.draft_key)
        ):
            raise ValueError("draft_key must be a non-empty semantic token")
        if self.importance is None and self.sensitivity is None:
            raise ValueError("at least one draft option is required")

    def to_payload(self) -> dict[str, object]:
        return {
            "draft_key": self.draft_key,
            "importance": self.importance.value if self.importance is not None else None,
            "sensitivity": (
                self.sensitivity.value if self.sensitivity is not None else None
            ),
        }


@dataclass(frozen=True)
class DraftOptionResult:
    draft_key: str
    read_back_importance: DraftImportance
    read_back_sensitivity: DraftSensitivity
    changed: bool
    verified: bool
    synthetic: bool = True


def apply_draft_options(
    drafts: tuple[SyntheticDraft, ...],
    request: DraftOptionRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[SyntheticDraft, ...], DraftOptionResult]:
    """Apply closed draft options and prove them through immediate read-back."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    current = next((item for item in drafts if item.draft_key == request.draft_key), None)
    if current is None or not current.synthetic:
        raise ValueError("synthetic draft_key not found")

    importance = (
        DraftImportance(current.importance)
        if request.importance is None
        else request.importance
    )
    sensitivity = (
        DraftSensitivity(current.sensitivity)
        if request.sensitivity is None
        else request.sensitivity
    )
    replacement = replace(
        current,
        importance=importance.value,
        sensitivity=sensitivity.value,
    )
    updated = tuple(
        replacement if item.draft_key == request.draft_key else item for item in drafts
    )
    read_back = next(item for item in updated if item.draft_key == request.draft_key)
    if read_back.importance != importance.value or read_back.sensitivity != sensitivity.value:
        raise RuntimeError("synthetic read-back did not prove draft options")

    return updated, DraftOptionResult(
        draft_key=request.draft_key,
        read_back_importance=importance,
        read_back_sensitivity=sensitivity,
        changed=replacement != current,
        verified=True,
    )


__all__ = [
    "DraftImportance",
    "DraftOptionRequest",
    "DraftOptionResult",
    "DraftSensitivity",
    "apply_draft_options",
]
