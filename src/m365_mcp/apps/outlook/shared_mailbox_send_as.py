"""Synthetic-only shared-mailbox Send-as intent preparation for OUT-116.

This module composes the verified shared-mailbox context, existing From identity
selection, and the fail-closed outbound intent foundation. It never dispatches
mail and never projects a mailbox address or tenant identity.
"""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.draft_models import SyntheticDraft
from m365_mcp.apps.outlook.from_identity_mutations import (
    FromIdentityMode,
    FromIdentityRequest,
    SyntheticFromIdentity,
    select_from_identity,
)
from m365_mcp.apps.outlook.outbound_models import (
    OutboundIntentKind,
    SyntheticOutboundIntent,
)
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport
from m365_mcp.apps.outlook.shared_mailbox_context import SharedMailboxContext


@dataclass(frozen=True)
class SharedMailboxSendAsResult:
    draft_key: str
    identity_key: str
    intent_key: str
    verified: bool
    dispatched: bool = False
    synthetic: bool = True


def _resolve_shared_identity(
    identity_key: str,
    identities: tuple[SyntheticFromIdentity, ...],
) -> SyntheticFromIdentity:
    if "@" in identity_key:
        raise ValueError("shared identity_key must not encode an address")
    matches = tuple(item for item in identities if item.identity_key == identity_key)
    if len(matches) != 1:
        raise ValueError("Send-as identity must resolve to exactly one candidate")
    identity = matches[0]
    if identity.mode is not FromIdentityMode.SHARED:
        raise ValueError("Send-as requires a SHARED From identity")
    if not identity.authorized:
        raise ValueError("Send-as identity is not authorized")
    return identity


def prepare_shared_mailbox_send_as(
    context: SharedMailboxContext,
    drafts: tuple[SyntheticDraft, ...],
    *,
    draft_key: str,
    identity_key: str,
    readiness: OutlookReadinessReport,
    identities: tuple[SyntheticFromIdentity, ...],
) -> tuple[tuple[SyntheticDraft, ...], SyntheticOutboundIntent, SharedMailboxSendAsResult]:
    """Prepare a governed Send-as intent without making it executable."""
    if not context.valid:
        raise ValueError("Send-as requires verified shared mailbox context")
    identity = _resolve_shared_identity(identity_key, identities)
    updated, selection = select_from_identity(
        drafts,
        FromIdentityRequest(draft_key, identity.identity_key),
        readiness=readiness,
        identities=identities,
    )
    if selection.mode is not FromIdentityMode.SHARED or not selection.verified:
        raise RuntimeError("synthetic Send-as identity read-back failed")

    intent = SyntheticOutboundIntent(
        intent_key=f"send-as-{draft_key}-{identity.identity_key}",
        kind=OutboundIntentKind.SEND_DRAFT,
        draft_key=draft_key,
    )
    if intent.executable:
        raise RuntimeError("synthetic Send-as intent unexpectedly became executable")
    return updated, intent, SharedMailboxSendAsResult(
        draft_key=draft_key,
        identity_key=identity.identity_key,
        intent_key=intent.intent_key,
        verified=True,
    )


__all__ = ["SharedMailboxSendAsResult", "prepare_shared_mailbox_send_as"]
