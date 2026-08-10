"""Governed synthetic S/MIME operation-intent preparation for OUT-127."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.draft_models import SyntheticDraft
from m365_mcp.apps.outlook.outbound_models import OutboundApprovalState
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport
from m365_mcp.apps.outlook.smime_capability_status import SyntheticSmimeCapabilityStatus


class SmimeOperation(StrEnum):
    SIGN = "SIGN"
    ENCRYPT = "ENCRYPT"
    SIGN_AND_ENCRYPT = "SIGN_AND_ENCRYPT"


@dataclass(frozen=True)
class SmimeOperationRequest:
    draft_key: str
    operation: SmimeOperation

    def __post_init__(self) -> None:
        if (
            not self.draft_key
            or self.draft_key != self.draft_key.strip()
            or any(char.isspace() for char in self.draft_key)
        ):
            raise ValueError("draft_key must be a non-empty semantic token")
        if "@" in self.draft_key or "://" in self.draft_key:
            raise ValueError("draft_key must not encode an address or URL")
        if not isinstance(self.operation, SmimeOperation):
            raise ValueError("operation must be a closed SmimeOperation")


@dataclass(frozen=True)
class SmimeOperationIntent:
    operation_key: str
    draft_key: str
    operation: SmimeOperation
    certificate_binding_present: bool = False
    approval_state: OutboundApprovalState = OutboundApprovalState.REQUIRED_NOT_BOUND
    dispatched: bool = False
    synthetic: bool = True
    live_support_state: str = "UNOBSERVED"

    @property
    def executable(self) -> bool:
        return False

    def __post_init__(self) -> None:
        if self.certificate_binding_present:
            raise ValueError("synthetic S/MIME intent must not bind certificate material")
        if not self.synthetic or self.live_support_state != "UNOBSERVED":
            raise ValueError("synthetic S/MIME intent must not imply live support")

    def to_projection(self) -> dict[str, object]:
        return {
            "operation_key": self.operation_key,
            "draft_key": self.draft_key,
            "operation": self.operation.value,
            "certificate_binding_present": False,
            "approval_state": self.approval_state.value,
            "approval_required": True,
            "executable": False,
            "dispatched": False,
            "synthetic": True,
            "live_support_state": self.live_support_state,
        }


def prepare_smime_operation(
    drafts: tuple[SyntheticDraft, ...],
    request: SmimeOperationRequest,
    *,
    capability: SyntheticSmimeCapabilityStatus,
    readiness: OutlookReadinessReport,
) -> SmimeOperationIntent:
    """Prepare a requested S/MIME mode without signing, encrypting or key access."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not any(draft.draft_key == request.draft_key and draft.synthetic for draft in drafts):
        raise ValueError("synthetic draft_key not found")
    if not capability.synthetic or capability.live_support_state != "UNOBSERVED":
        raise ValueError("synthetic S/MIME capability evidence is required")
    if capability.certificate_material_exported or capability.private_key_material_exported:
        raise ValueError("certificate or private-key material must not be exported")

    needs_signing = request.operation in {SmimeOperation.SIGN, SmimeOperation.SIGN_AND_ENCRYPT}
    needs_encryption = request.operation in {
        SmimeOperation.ENCRYPT,
        SmimeOperation.SIGN_AND_ENCRYPT,
    }
    if needs_signing and not capability.signing_mode_present:
        raise ValueError("S/MIME signing mode is not available in the synthetic capability")
    if needs_encryption and not capability.encryption_mode_present:
        raise ValueError("S/MIME encryption mode is not available in the synthetic capability")

    suffix = request.operation.value.lower().replace("_", "-")
    intent = SmimeOperationIntent(
        operation_key=f"smime-{suffix}-{request.draft_key}",
        draft_key=request.draft_key,
        operation=request.operation,
    )
    if intent.executable or intent.dispatched:
        raise RuntimeError("synthetic S/MIME operation unexpectedly became executable")
    return intent


__all__ = [
    "SmimeOperation",
    "SmimeOperationIntent",
    "SmimeOperationRequest",
    "prepare_smime_operation",
]
