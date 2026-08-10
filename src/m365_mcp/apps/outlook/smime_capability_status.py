"""Synthetic S/MIME capability/status reporting for OUT-126."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


class SmimeCertificateStatus(StrEnum):
    NOT_MODELED = "NOT_MODELED"


@dataclass(frozen=True)
class SyntheticSmimeCapabilityStatus:
    signing_mode_present: bool = True
    encryption_mode_present: bool = True
    certificate_status: SmimeCertificateStatus = SmimeCertificateStatus.NOT_MODELED
    certificate_material_exported: bool = False
    private_key_material_exported: bool = False
    source: str = "SYNTHETIC_FIXTURE"
    live_support_state: str = "UNOBSERVED"
    synthetic: bool = True

    def __post_init__(self) -> None:
        if self.certificate_material_exported or self.private_key_material_exported:
            raise ValueError("S/MIME certificate or private-key material must never be exported")
        if not self.synthetic:
            raise ValueError("OUT-126 status is synthetic-only")
        if self.live_support_state != "UNOBSERVED":
            raise ValueError("synthetic S/MIME status must not imply live support")

    def to_projection(self) -> dict[str, object]:
        return {
            "signing_mode_present": self.signing_mode_present,
            "encryption_mode_present": self.encryption_mode_present,
            "certificate_status": self.certificate_status.value,
            "certificate_material_exported": False,
            "private_key_material_exported": False,
            "source": self.source,
            "live_support_state": self.live_support_state,
            "synthetic": True,
        }


def read_smime_capability_status(
    *,
    readiness: OutlookReadinessReport,
) -> SyntheticSmimeCapabilityStatus:
    """Report fixture capability shape without reading certificate secrets."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    return SyntheticSmimeCapabilityStatus()


__all__ = [
    "SmimeCertificateStatus",
    "SyntheticSmimeCapabilityStatus",
    "read_smime_capability_status",
]
