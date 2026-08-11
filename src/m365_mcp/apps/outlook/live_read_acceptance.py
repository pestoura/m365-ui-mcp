"""Fail-closed REL-013 Outlook read-only live acceptance boundary.

The boundary composes existing sanitized account, mailbox, UI attestation and
REL-025 evidence primitives. It never accepts tenant/user identifiers, URLs,
DOM, mailbox content, browser session material or mutation instructions.
"""

from __future__ import annotations

from m365_browser_worker.account_context import AccountContext
from m365_mcp.apps.outlook.mailbox_context import PrimaryMailboxContext
from m365_mcp.attestation import (
    AttestationDecision,
    AttestationDecisionState,
    AttestationLevel,
    AttestationObservation,
    ObservationSource,
)
from m365_mcp.capability_promotion import (
    LiveCapabilityEvidence,
    PromotionEvidenceSource,
)
from m365_mcp.ui_drift import UILifecycleState

OUTLOOK_READONLY_APPLICATION = "outlook"
OUTLOOK_READONLY_SURFACE = "outlook_web"
OUTLOOK_READONLY_ACCOUNT_SCOPE = "professional_session"
OUTLOOK_READONLY_CONTAINER_SCOPE = "account"
OUTLOOK_READONLY_CAPABILITY = "mail.read"

REL013_REQUIRED_GATE_IDS = (
    "REL-004",
    "REL-007",
    "REL-011",
    "REL-013-account-context",
    "REL-013-mailbox-context",
    "REL-013-read-probe",
)


def build_outlook_readonly_live_evidence(
    account_context: AccountContext,
    mailbox_context: PrimaryMailboxContext,
    observation: AttestationObservation,
    decision: AttestationDecision,
    *,
    environment_id: str,
    passed_gate_ids: tuple[str, ...],
) -> LiveCapabilityEvidence:
    """Build promotion-grade REL-025 evidence only after an exact LIVE READ proof.

    Synthetic or mock observations are rejected here rather than being upgraded
    into evidence that merely looks live. The returned evidence remains inert:
    REL-025 still decides whether the capability can be promoted.
    """
    if not account_context.valid:
        raise ValueError("REL013_ACCOUNT_CONTEXT_NOT_VERIFIED")
    if not mailbox_context.valid:
        raise ValueError("REL013_PRIMARY_MAILBOX_CONTEXT_NOT_VERIFIED")
    if observation.source is not ObservationSource.LIVE_UI:
        raise ValueError("REL013_LIVE_UI_EVIDENCE_REQUIRED")
    if observation.target_level is not AttestationLevel.READ:
        raise ValueError("REL013_READ_ATTESTATION_REQUIRED")
    if observation.mutation_applied is not None:
        raise ValueError("REL013_MUTATION_EVIDENCE_FORBIDDEN")
    if observation.approval_digest is not None:
        raise ValueError("REL013_MUTATION_APPROVAL_FORBIDDEN")
    if observation.compensation_proven is not None:
        raise ValueError("REL013_COMPENSATION_EVIDENCE_FORBIDDEN")
    if observation.read_probe_ok is not True:
        raise ValueError("REL013_READ_PROBE_NOT_CONFIRMED")
    if decision.state is not AttestationDecisionState.PASSED:
        raise ValueError("REL013_ATTESTATION_NOT_PASSED")

    record = decision.evidence_record
    if UILifecycleState(record.lifecycle_state) is not UILifecycleState.HEALTHY:
        raise ValueError("REL013_UI_LIFECYCLE_NOT_HEALTHY")
    if record.contract_set_digest != observation.contract_set_digest:
        raise ValueError("REL013_CONTRACT_SET_DIGEST_MISMATCH")
    if record.recorded_at != observation.observed_at:
        raise ValueError("REL013_EVIDENCE_TIMESTAMP_MISMATCH")

    supplied_gates = set(passed_gate_ids)
    missing_gates = tuple(gate for gate in REL013_REQUIRED_GATE_IDS if gate not in supplied_gates)
    if missing_gates:
        raise ValueError(f"REL013_REQUIRED_GATES_MISSING:{','.join(missing_gates)}")

    return LiveCapabilityEvidence(
        application=OUTLOOK_READONLY_APPLICATION,
        surface=OUTLOOK_READONLY_SURFACE,
        account_scope=OUTLOOK_READONLY_ACCOUNT_SCOPE,
        container_scope=OUTLOOK_READONLY_CONTAINER_SCOPE,
        capability=OUTLOOK_READONLY_CAPABILITY,
        environment_id=environment_id,
        observed_at=observation.observed_at,
        source=PromotionEvidenceSource.LIVE_UI,
        contract_set_digest=observation.contract_set_digest,
        passed_gate_ids=passed_gate_ids,
        acceptance_ok=True,
        readback_ok=True,
    )


__all__ = [
    "OUTLOOK_READONLY_ACCOUNT_SCOPE",
    "OUTLOOK_READONLY_APPLICATION",
    "OUTLOOK_READONLY_CAPABILITY",
    "OUTLOOK_READONLY_CONTAINER_SCOPE",
    "OUTLOOK_READONLY_SURFACE",
    "REL013_REQUIRED_GATE_IDS",
    "build_outlook_readonly_live_evidence",
]
