from __future__ import annotations

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import (
    draft_models,
    outbound_models,
    sent_item_readback,
)
from m365_mcp.idempotency_v2 import (
    ReadBackOutcome,
    RetryAction,
    mark_effect_unverified,
)
from m365_mcp.state_identity import resource_state_identity
from m365_mcp.tool_registry import default_tool_registry


def _intent() -> outbound_models.SyntheticOutboundIntent:
    return outbound_models.SyntheticOutboundIntent(
        intent_key="intent-055",
        kind=outbound_models.OutboundIntentKind.SEND_DRAFT,
        draft_key=draft_models.default_synthetic_drafts()[0].draft_key,
    )


def _identity():
    return resource_state_identity(
        ApplicationKey.OUTLOOK,
        account_scope="professional_session",
        container_kind="folder",
        external_container_id="sent",
        resource_kind="outbound_intent",
        external_resource_id="intent-055",
    )


def test_sent_item_readback_classifies_absent_present_and_ambiguous() -> None:
    intent = _intent()
    absent = sent_item_readback.evaluate_sent_item_read_back(intent, ())
    assert absent.outcome is ReadBackOutcome.EFFECT_ABSENT

    present = sent_item_readback.evaluate_sent_item_read_back(
        intent,
        (sent_item_readback.SyntheticSentItemObservation("intent-055", "msg-sent-001"),),
    )
    assert present.outcome is ReadBackOutcome.EFFECT_PRESENT
    assert present.matched_message_key == "msg-sent-001"

    ambiguous = sent_item_readback.evaluate_sent_item_read_back(
        intent,
        (
            sent_item_readback.SyntheticSentItemObservation("intent-055", "msg-sent-001"),
            sent_item_readback.SyntheticSentItemObservation("intent-055", "msg-sent-002"),
        ),
    )
    assert ambiguous.outcome is ReadBackOutcome.AMBIGUOUS
    assert ambiguous.candidate_count == 2


def test_effect_unverified_outbound_retry_is_governed_by_readback() -> None:
    intent = _intent()
    identity = _identity()
    record = sent_item_readback.reserve_outbound_intent(identity, intent)
    assert record.read_back_required is True
    record = mark_effect_unverified(record)

    absent = sent_item_readback.evaluate_sent_item_read_back(intent, ())
    assert (
        sent_item_readback.resolve_outbound_retry(record, identity, intent, absent)
        is RetryAction.RETRY_SAFE
    )

    present = sent_item_readback.evaluate_sent_item_read_back(
        intent,
        (sent_item_readback.SyntheticSentItemObservation("intent-055", "msg-sent-001"),),
    )
    assert (
        sent_item_readback.resolve_outbound_retry(record, identity, intent, present)
        is RetryAction.DO_NOT_RETRY
    )

    ambiguous = sent_item_readback.evaluate_sent_item_read_back(
        intent,
        (
            sent_item_readback.SyntheticSentItemObservation("intent-055", "msg-sent-001"),
            sent_item_readback.SyntheticSentItemObservation("intent-055", "msg-sent-002"),
        ),
    )
    assert (
        sent_item_readback.resolve_outbound_retry(record, identity, intent, ambiguous)
        is RetryAction.READ_BACK_REQUIRED
    )


def test_out055_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
