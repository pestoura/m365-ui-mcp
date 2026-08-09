"""Fail-closed synthetic forward intent preparation for OUT-053."""

from __future__ import annotations

from m365_mcp.apps.outlook.draft_models import SyntheticDraft
from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.outbound_models import (
    OutboundIntentKind,
    SyntheticOutboundIntent,
)
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


def prepare_forward_intent(
    drafts: tuple[SyntheticDraft, ...],
    fixture: OutlookMockFixture,
    *,
    intent_key: str,
    draft_key: str,
    source_message_key: str,
    readiness: OutlookReadinessReport,
) -> SyntheticOutboundIntent:
    """Prepare but never execute a governed synthetic forward intent."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not fixture.synthetic:
        raise ValueError("OUT-053 requires synthetic source fixture")
    draft = next((item for item in drafts if item.draft_key == draft_key), None)
    if draft is None or not draft.synthetic:
        raise ValueError("synthetic draft_key not found")
    if not (draft.to_keys or draft.cc_keys or draft.bcc_keys):
        raise ValueError("forward preparation requires at least one recipient")
    if not any(item.message_key == source_message_key for item in fixture.messages):
        raise ValueError("synthetic source_message_key not found")

    return SyntheticOutboundIntent(
        intent_key=intent_key,
        kind=OutboundIntentKind.FORWARD,
        draft_key=draft_key,
        source_message_key=source_message_key,
    )


__all__ = ["prepare_forward_intent"]
