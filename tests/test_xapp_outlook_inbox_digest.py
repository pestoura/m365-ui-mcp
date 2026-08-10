import pytest

from m365_mcp.application_registry import ApplicationState
from m365_mcp.apps.outlook.manifest import foundation_manifest
from m365_mcp.apps.outlook.message_list import MessageListItem, MessageListResult
from m365_mcp.tool_registry import default_tool_registry
from m365_mcp.xapp_outlook_inbox_digest import build_synthetic_inbox_digest


def _result(*, synthetic: bool = True, folder_key: str = "inbox") -> MessageListResult:
    items = (
        MessageListItem("msg-02", "sensitive subject two", folder_key, False, False),
        MessageListItem("msg-01", "sensitive subject one", folder_key, False, True),
        MessageListItem("msg-03", "sensitive subject three", folder_key, True, True),
    )
    return MessageListResult(
        items=items,
        folder_key=folder_key,
        offset=0,
        limit=50,
        total_matching=3,
        has_more=False,
        synthetic=synthetic,
    )


def test_digest_reduces_synthetic_inbox_to_counts_and_opaque_keys() -> None:
    digest = build_synthetic_inbox_digest(_result(), max_attention_keys=1)

    assert digest.page_count == 3
    assert digest.total_matching == 3
    assert digest.unread_count == 2
    assert digest.attachment_count == 2
    assert digest.attention_message_keys == ("msg-01",)
    assert digest.synthetic is True
    assert digest.live_observed is False
    assert digest.execution_performed is False
    assert "subject" not in digest.__dict__


def test_digest_requires_synthetic_inbox_and_bounded_attention() -> None:
    with pytest.raises(ValueError, match="synthetic"):
        build_synthetic_inbox_digest(_result(synthetic=False))

    with pytest.raises(ValueError, match="inbox folder"):
        build_synthetic_inbox_digest(_result(folder_key="archive"))

    with pytest.raises(ValueError, match="between 1 and 100"):
        build_synthetic_inbox_digest(_result(), max_attention_keys=101)


def test_outlook_foundation_and_public_registry_remain_inert() -> None:
    manifest = foundation_manifest()

    assert manifest.state is ApplicationState.RESERVED
    assert manifest.public_tools_enabled is False
    assert manifest.browser_operations_enabled is False
    assert default_tool_registry().by_application("outlook") == ()
