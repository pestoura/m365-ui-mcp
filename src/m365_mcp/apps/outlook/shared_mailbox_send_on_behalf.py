"""Synthetic-only shared-mailbox Send-on-behalf intent preparation for OUT-117."""

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
class SharedMailboxSendOnBehalfResult:
    draft_key: str
    identity_key: str
    intent_key: str
    verified: bool
    dispatched: bool = False
    synthetic: bool = True


def _resolve_delegated_identity(
    identity_key: str,
    identities: tuple[SyntheticFromIdentity, ...],
) -> SyntheticFromIdentity:
    if "@" in identity_key:
        raise ValueError("delegated identity_key must not encode an address")
    matches = tuple(item for item in identities if item.identity_key == identity_key)
    if len(matches) != 1:
        raise ValueError("Send-on-behalf identity must resolve to exactly one candidate")
    identity = matches[0]
    if identity.mode is not FromIdentityMode.DELEGATED:
        raise ValueError("Send-on-behalf requires a DELEGATED From identity")
    if not identity.authorized:
        raise ValueError("Send-on-behalf identity is not authorized")
    return identity


def prepare_shared_mailbox_send_on_behalf(
    context: SharedMailboxContext,
    drafts: tuple[SyntheticDraft, ...],
    *,
    draft_key: str,
    identity_key: str,
    readiness: OutlookReadinessReport,
    identities: tuple[SyntheticFromIdentity, ...],
) -> tuple[
    tuple[SyntheticDraft, ...],
    SyntheticOutboundIntent,
    SharedMailboxSendOnBehalfResult,
]:
    """Prepare a governed Send-on-behalf intent without dispatching it."""
    if not context.valid:
        raise ValueError("Send-on-behalf requires verified shared mailbox context")
    identity = _resolve_delegated_identity(identity_key, identities)
    updated, selection = select_from_identity(
        drafts,
        FromIdentityRequest(draft_key, identity.identity_key),
        readiness=readiness,
        identities=identities,
    )
    if selection.mode is not FromIdentityMode.DELEGATED or not selection.verified:
        raise RuntimeError("synthetic Send-on-behalf identity read-back failed")

    intent = SyntheticOutboundIntent(
        intent_key=f"send-on-behalf-{draft_key}-{identity.identity_key}",
        kind=OutboundIntentKind.SEND_DRAFT,
        draft_key=draft_key,
    )
    if intent.executable:
        raise RuntimeError("synthetic Send-on-behalf intent unexpectedly became executable")
    return updated, intent, SharedMailboxSendOnBehalfResult(
        draft_key=draft_key,
        identity_key=identity.identity_key,
        intent_key=intent.intent_key,
        verified=True,
    )


__all__ = [
    "SharedMailboxSendOnBehalfResult",
    "prepare_shared_mailbox_send_on_behalf",
]
