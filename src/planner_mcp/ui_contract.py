"""Versioned UIContract handling. Unverified selectors fail closed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import load_contract
from .errors import UiContractUnattested, UiDrift

UNVERIFIED = "UNVERIFIED_LIVE"
ATTESTED = "ATTESTED"


@dataclass(frozen=True)
class UiContractStatus:
    """Snapshot of the current UIContract state."""

    version: str
    attested: bool
    attestation_status: str
    selector_count: int
    unverified_selectors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ui_contract_version": self.version,
            "attested": self.attested,
            "attestation_status": self.attestation_status,
            "selector_count": self.selector_count,
            "unverified_selectors": list(self.unverified_selectors),
            "fail_closed_error": None if self.attested else UiContractUnattested.code,
        }


def load_status() -> UiContractStatus:
    """Load the packaged UIContract and summarise attestation."""
    doc = load_contract("ui_contract")
    selectors: dict[str, Any] = doc.get("selectors", {})
    unverified = tuple(
        name for name, meta in selectors.items() if meta.get("status") != ATTESTED
    )
    return UiContractStatus(
        version=str(doc.get("ui_contract_version", "0.0.0")),
        attested=bool(doc.get("attested", False)) and not unverified,
        attestation_status=str(doc.get("attestation_status", UNVERIFIED)),
        selector_count=len(selectors),
        unverified_selectors=unverified,
    )


def require_attested(operation: str) -> None:
    """Fail closed when live operations are attempted without attestation."""
    status = load_status()
    if not status.attested:
        raise UiContractUnattested(
            f"live operation '{operation}' blocked: UIContract not attested",
            ui_contract_version=status.version,
            unverified_selectors=list(status.unverified_selectors),
        )


def assert_no_drift(observed_version: str) -> None:
    """Raise UI_DRIFT when the worker reports a different contract version."""
    status = load_status()
    if observed_version != status.version:
        raise UiDrift(
            "worker UIContract version differs from control plane",
            expected=status.version,
            observed=observed_version,
        )
