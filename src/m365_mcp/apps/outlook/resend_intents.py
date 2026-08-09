"""Fail-closed synthetic resend intent preparation for OUT-054."""

from __future__ import annotations

from m365_mcp.apps.outlook.draft_models import SyntheticDraft
from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.outbound_models import (
    OutboundIntentKind,
    SyntheticOutboundIntent,
)
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


def prepare_resend_intent(
    drafts: tuple[SyntheticDraft, ...],
    fixture: OutlookMockFixture,
    *,
    intent_key: str,
    draft_key: str,
    source_message_key: str,
    readiness: OutlookReadinessReport,
) -> SyntheticOutboundIntent:
    """Prepare but never execute a governed synthetic resend intent."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not fixture.synthetic:
        raise ValueError("OUT-054 requires synthetic source fixture")
    draft = next((item for item in drafts if item.draft_key == draft_key), None)
    if draft is None or not draft.synthetic:
        raise ValueError("synthetic draft_key not found")
    if not (draft.to_keys or draft.cc_keys or draft.bcc_keys):
        raise ValueError("resend preparation requires at least one recipient")
    source = next(
        (item for item in fixture.messages if item.message_key == source_message_key),
        None,
    )
    if source is None:
        raise ValueError("synthetic source_message_key not found")
    if source.folder_key != "sent":
        raise ValueError("resend source must be a synthetic sent item")

    return SyntheticOutboundIntent(
        intent_key=intent_key,
        kind=OutboundIntentKind.RESEND,
        draft_key=draft_key,
        source_message_key=source_message_key,
    )


__all__ = ["prepare_resend_intent"]
