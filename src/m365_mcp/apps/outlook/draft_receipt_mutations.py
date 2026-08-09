"""Synthetic draft read/delivery receipt options for OUT-048."""

from __future__ import annotations

from dataclasses import dataclass, replace

from m365_mcp.apps.outlook.draft_models import SyntheticDraft
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


@dataclass(frozen=True)
class DraftReceiptRequest:
    draft_key: str
    read_receipt_requested: bool | None = None
    delivery_receipt_requested: bool | None = None

    def __post_init__(self) -> None:
        if (
            not self.draft_key
            or self.draft_key != self.draft_key.strip()
            or any(char.isspace() for char in self.draft_key)
        ):
            raise ValueError("draft_key must be a non-empty semantic token")
        if self.read_receipt_requested is None and self.delivery_receipt_requested is None:
            raise ValueError("at least one receipt option is required")

    def to_payload(self) -> dict[str, object]:
        return {
            "draft_key": self.draft_key,
            "read_receipt_requested": self.read_receipt_requested,
            "delivery_receipt_requested": self.delivery_receipt_requested,
        }


@dataclass(frozen=True)
class DraftReceiptResult:
    draft_key: str
    read_back_read_receipt_requested: bool
    read_back_delivery_receipt_requested: bool
    changed: bool
    verified: bool
    synthetic: bool = True


def apply_draft_receipt_options(
    drafts: tuple[SyntheticDraft, ...],
    request: DraftReceiptRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[SyntheticDraft, ...], DraftReceiptResult]:
    """Apply receipt flags to one synthetic draft and verify through read-back."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    current = next((item for item in drafts if item.draft_key == request.draft_key), None)
    if current is None or not current.synthetic:
        raise ValueError("synthetic draft_key not found")

    read_receipt = (
        current.read_receipt_requested
        if request.read_receipt_requested is None
        else request.read_receipt_requested
    )
    delivery_receipt = (
        current.delivery_receipt_requested
        if request.delivery_receipt_requested is None
        else request.delivery_receipt_requested
    )
    replacement = replace(
        current,
        read_receipt_requested=read_receipt,
        delivery_receipt_requested=delivery_receipt,
    )
    updated = tuple(
        replacement if item.draft_key == request.draft_key else item for item in drafts
    )
    read_back = next(item for item in updated if item.draft_key == request.draft_key)
    if (
        read_back.read_receipt_requested != read_receipt
        or read_back.delivery_receipt_requested != delivery_receipt
    ):
        raise RuntimeError("synthetic read-back did not prove receipt option state")

    return updated, DraftReceiptResult(
        draft_key=request.draft_key,
        read_back_read_receipt_requested=read_back.read_receipt_requested,
        read_back_delivery_receipt_requested=read_back.delivery_receipt_requested,
        changed=replacement != current,
        verified=True,
    )


__all__ = [
    "DraftReceiptRequest",
    "DraftReceiptResult",
    "apply_draft_receipt_options",
]
