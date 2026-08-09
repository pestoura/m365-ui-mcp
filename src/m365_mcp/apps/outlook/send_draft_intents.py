"""Fail-closed synthetic send-draft intent preparation for OUT-050."""

from __future__ import annotations

from m365_mcp.apps.outlook.draft_models import SyntheticDraft
from m365_mcp.apps.outlook.outbound_models import (
    OutboundIntentKind,
    SyntheticOutboundIntent,
)
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


def prepare_send_draft_intent(
    drafts: tuple[SyntheticDraft, ...],
    *,
    intent_key: str,
    draft_key: str,
    readiness: OutlookReadinessReport,
) -> SyntheticOutboundIntent:
    """Prepare but never execute a governed synthetic send-draft intent."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    draft = next((item for item in drafts if item.draft_key == draft_key), None)
    if draft is None or not draft.synthetic:
        raise ValueError("synthetic draft_key not found")
    if not (draft.to_keys or draft.cc_keys or draft.bcc_keys):
        raise ValueError("send-draft preparation requires at least one recipient")

    return SyntheticOutboundIntent(
        intent_key=intent_key,
        kind=OutboundIntentKind.SEND_DRAFT,
        draft_key=draft_key,
    )


__all__ = ["prepare_send_draft_intent"]
