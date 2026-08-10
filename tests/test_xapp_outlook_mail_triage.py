import pytest

from m365_mcp.application_registry import ApplicationState
from m365_mcp.apps.outlook.manifest import foundation_manifest
from m365_mcp.apps.outlook.message_list import MessageListItem, MessageListResult
from m365_mcp.tool_registry import default_tool_registry
from m365_mcp.xapp_outlook_mail_triage import (
    OutlookMailTriagePlan,
    OutlookTriageDisposition,
    OutlookTriageRecommendation,
    plan_synthetic_mail_triage,
)


def _result(*, synthetic: bool = True) -> MessageListResult:
    return MessageListResult(
        items=(
            MessageListItem("msg-02", "subject two", "inbox", False, False),
            MessageListItem("msg-01", "subject one", "inbox", False, True),
            MessageListItem("msg-03", "subject three", "inbox", True, True),
        ),
        folder_key="inbox",
        offset=0,
        limit=50,
        total_matching=3,
        has_more=False,
        synthetic=synthetic,
    )


def test_triage_is_deterministic_metadata_only_and_non_executing() -> None:
    plan = plan_synthetic_mail_triage(_result())

    assert plan.recommendations == (
        OutlookTriageRecommendation(
            "msg-01",
            OutlookTriageDisposition.REVIEW_ATTACHMENT,
        ),
        OutlookTriageRecommendation("msg-02", OutlookTriageDisposition.REVIEW_UNREAD),
        OutlookTriageRecommendation("msg-03", OutlookTriageDisposition.NO_ACTION),
    )
    assert plan.synthetic is True
    assert plan.live_observed is False
    assert plan.execution_performed is False
    assert all("subject" not in item.__dict__ for item in plan.recommendations)


def test_triage_requires_synthetic_source_and_bounded_item_count() -> None:
    with pytest.raises(ValueError, match="synthetic"):
        plan_synthetic_mail_triage(_result(synthetic=False))

    with pytest.raises(ValueError, match="between 1 and 100"):
        plan_synthetic_mail_triage(_result(), max_items=0)


def test_triage_plan_rejects_duplicates_and_execution_claims() -> None:
    duplicate = OutlookTriageRecommendation(
        "msg-01",
        OutlookTriageDisposition.REVIEW_UNREAD,
    )
    with pytest.raises(ValueError, match="must be unique"):
        OutlookMailTriagePlan((duplicate, duplicate))

    with pytest.raises(ValueError, match="must not execute"):
        OutlookMailTriagePlan((duplicate,), execution_performed=True)


def test_outlook_foundation_and_public_registry_remain_inert() -> None:
    manifest = foundation_manifest()

    assert manifest.state is ApplicationState.RESERVED
    assert manifest.public_tools_enabled is False
    assert manifest.browser_operations_enabled is False
    assert default_tool_registry().by_application("outlook") == ()
