"""Planner compatibility view over the fragmented M365 UIContract store."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from m365_mcp.ui_contract_projection import project_ui_contract_set
from m365_mcp.ui_contract_store import load_ui_contract_set

from .errors import UiContractUnattested, UiDrift

UNVERIFIED = "UNVERIFIED_LIVE"
ATTESTED = "ATTESTED"

# The two atomic ``common.auth`` UIContract fragments. Each is independently
# collectable/attestable because the email and password surfaces never coexist
# on the same Microsoft Entra ID sign-in page. AUTH-101 requires BOTH fragments
# to be effectively_attested before any credential field is applied.
COMMON_AUTH_FRAGMENT_IDS = ("common.auth.email", "common.auth.password")


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
    """Return whether the ``common.auth`` authentication fragments are attested.

    This is fragment-scoped: it inspects ONLY the two atomic ``common.auth``
    UIContract fragments (``common.auth.email`` and ``common.auth.password``) and
    returns True iff BOTH fragments exist and are effectively attested (fragment +
    every selector explicitly ATTESTED, no drift). Any other fragment's
    attestation state (e.g. Planner application fragments) is irrelevant to the
    authentication bootstrap boundary.

    The two fragments are intentionally separate because the email and password
    surfaces never coexist on the same Microsoft Entra ID sign-in page: the
    password/sign-in selectors only appear AFTER email -> Next. Both must be
    attested before ``submit_operator_signin`` may apply any credential field
    (AUTH-101 gate).

    Missing fragment => False (fail closed). This intentionally does NOT read
    the aggregated ``load_status().attested`` signal, which combines common +
    Planner fragments and would wrongly report UNKNOWN while ``common.auth`` is
    already attested but the Planner fragments are still UNVERIFIED.
    """
    source = load_ui_contract_set()
    seen: set[str] = set()
    attested_fragments = 0
    for fragment in source.fragments:
        if fragment.fragment_id not in COMMON_AUTH_FRAGMENT_IDS:
            continue
        seen.add(fragment.fragment_id)
        if fragment.effectively_attested:
            attested_fragments += 1
    # Both atomic auth fragments must be present and effectively attested.
    return len(seen) == len(COMMON_AUTH_FRAGMENT_IDS) and attested_fragments == len(
        COMMON_AUTH_FRAGMENT_IDS
    )


def full_contract_set_digest() -> str:
    """Return the exact full-set contract digest used by live attestation.

    The live attestation observation collector (``collect_structural_observation``
    / ``collect_running_observation``) binds ``contract_set.digest()`` — the
    SHA-256 of the COMPLETE UIContract set (every fragment, common + Planner +
    Outlook). The compatibility ``load_status()`` view, by contrast, projects to
    Planner scope and digests only common + Planner fragments, so its digest
    differs once Outlook fragments are present. The worker ``/health`` endpoint
    and the evidence paths must expose the SAME full-set digest the collector
    binds, otherwise every observation fails with
    ``CONTRACT_SET_DIGEST_MISMATCH``. This helper centralizes that exact value.
    """
    return load_ui_contract_set().digest()


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
