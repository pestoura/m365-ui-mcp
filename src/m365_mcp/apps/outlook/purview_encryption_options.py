"""Synthetic governed Purview protection-option intent for OUT-125."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.draft_models import SyntheticDraft
from m365_mcp.apps.outlook.outbound_models import OutboundApprovalState
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


class PurviewProtectionOption(StrEnum):
    ENCRYPT = "ENCRYPT"
    DO_NOT_FORWARD = "DO_NOT_FORWARD"


@dataclass(frozen=True)
class PurviewProtectionRequest:
    draft_key: str
    option: PurviewProtectionOption

    def __post_init__(self) -> None:
        if (
            not self.draft_key
            or self.draft_key != self.draft_key.strip()
            or any(char.isspace() for char in self.draft_key)
        ):
            raise ValueError("draft_key must be a non-empty semantic token")
        if "@" in self.draft_key or "://" in self.draft_key:
            raise ValueError("draft_key must not encode an address or URL")
        if not isinstance(self.option, PurviewProtectionOption):
            raise ValueError("option must be a closed PurviewProtectionOption")


@dataclass(frozen=True)
class PurviewProtectionIntent:
    protection_key: str
    draft_key: str
    option: PurviewProtectionOption
    approval_state: OutboundApprovalState = OutboundApprovalState.REQUIRED_NOT_BOUND
    dispatched: bool = False
    synthetic: bool = True

    @property
    def executable(self) -> bool:
        return False

    def to_projection(self) -> dict[str, object]:
        return {
            "protection_key": self.protection_key,
            "draft_key": self.draft_key,
            "option": self.option.value,
            "approval_state": self.approval_state.value,
            "approval_required": True,
            "executable": False,
            "dispatched": False,
            "synthetic": True,
            "live_support_state": "UNOBSERVED",
        }


def prepare_purview_protection(
    drafts: tuple[SyntheticDraft, ...],
    request: PurviewProtectionRequest,
    *,
    readiness: OutlookReadinessReport,
) -> PurviewProtectionIntent:
    """Prepare a protection option without applying it to a live draft."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not any(draft.draft_key == request.draft_key and draft.synthetic for draft in drafts):
        raise ValueError("synthetic draft_key not found")

    option_key = request.option.value.lower().replace("_", "-")
    intent = PurviewProtectionIntent(
        protection_key=f"purview-{option_key}-{request.draft_key}",
        draft_key=request.draft_key,
        option=request.option,
    )
    if intent.executable or intent.dispatched:
        raise RuntimeError("synthetic Purview protection unexpectedly became executable")
    return intent


__all__ = [
    "PurviewProtectionIntent",
    "PurviewProtectionOption",
    "PurviewProtectionRequest",
    "prepare_purview_protection",
]
