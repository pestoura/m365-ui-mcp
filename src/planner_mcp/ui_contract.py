"""Planner compatibility view over the fragmented M365 UIContract store."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from m365_mcp.ui_contract_projection import project_ui_contract_set
from m365_mcp.ui_contract_store import load_ui_contract_set

from .errors import UiContractUnattested, UiDrift

UNVERIFIED = "UNVERIFIED_LIVE"
ATTESTED = "ATTESTED"


@dataclass(frozen=True)
class UiContractStatus:
    """Compatibility snapshot of the current UIContract set state."""

    version: str
    contract_set_digest: str
    attested: bool
    attestation_status: str
    selector_count: int
    unverified_selectors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ui_contract_version": self.version,
            "ui_contract_set_digest": self.contract_set_digest,
            "attested": self.attested,
            "attestation_status": self.attestation_status,
            "selector_count": self.selector_count,
            "unverified_selectors": list(self.unverified_selectors),
            "fail_closed_error": None if self.attested else UiContractUnattested.code,
        }


def common_auth_attested() -> bool:
    """Return whether the ``common.auth`` fragment is effectively attested.

    This is fragment-scoped: it inspects ONLY the ``common.auth`` UIContract
    fragment and returns True iff that fragment exists and is effectively
    attested (fragment + every selector explicitly ATTESTED, no drift). Any
    other fragment's attestation state (e.g. Planner application fragments) is
    irrelevant to the authentication bootstrap boundary.

    Missing fragment => False (fail closed). This intentionally does NOT read
    the aggregated ``load_status().attested`` signal, which combines common +
    Planner fragments and would wrongly report UNKNOWN while ``common.auth`` is
    already attested but the Planner fragments are still UNVERIFIED.
    """
    source = load_ui_contract_set()
    for fragment in source.fragments:
        if fragment.fragment_id == "common.auth":
            return fragment.effectively_attested
    return False


def load_status() -> UiContractStatus:
    """Aggregate only common + Planner fragments into the compatibility view."""
    source = load_ui_contract_set()
    contract_set = project_ui_contract_set(
        source,
        "planner",
        set_version=source.legacy_version,
    )
    selectors = contract_set.selectors()
    unverified = tuple(
        name for name, meta in selectors.items() if meta.get("status") != ATTESTED
    )
    fragments_attested = all(fragment.attested for fragment in contract_set.fragments)
    attested = fragments_attested and not unverified
    return UiContractStatus(
        version=contract_set.legacy_version,
        contract_set_digest=contract_set.digest(),
        attested=attested,
        attestation_status=ATTESTED if attested else UNVERIFIED,
        selector_count=len(selectors),
        unverified_selectors=unverified,
    )


def require_attested(operation: str) -> None:
    """Fail closed when live operations are attempted without Planner attestation."""
    status = load_status()
    if not status.attested:
        raise UiContractUnattested(
            f"live operation '{operation}' blocked: UIContract not attested",
            ui_contract_version=status.version,
            ui_contract_set_digest=status.contract_set_digest,
            unverified_selectors=list(status.unverified_selectors),
        )


def assert_no_drift(observed_version: str) -> None:
    """Raise UI_DRIFT when the worker reports a different compatibility version."""
    status = load_status()
    if observed_version != status.version:
        raise UiDrift(
            "worker UIContract version differs from control plane",
            expected=status.version,
            observed=observed_version,
        )
