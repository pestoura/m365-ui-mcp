from __future__ import annotations

from m365_mcp.apps.outlook import conversation_reads, discovery, mailbox_context, mock_ui, readiness
from m365_mcp.apps.outlook.shell_contracts import OutlookShellTarget
from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.tool_registry import default_tool_registry

EVIDENCE = "d" * 64


def _ready_report() -> readiness.OutlookReadinessReport:
    primary = mailbox_context.PrimaryMailboxContext(
        state=mailbox_context.PrimaryMailboxContextState.VERIFIED,
        account_context_verified=True,
        primary_shell_verified=True,
        evidence_digest=EVIDENCE,
    )
    candidate = discovery.OutlookCapabilityCandidate(
        capability_key="mail.read",
        shell_target=OutlookShellTarget.MAIL,
        shell_contract_key="outlook.shell.mail",
        state=discovery.DiscoveryState.OBSERVED,
        evidence_digest=EVIDENCE,
    )
    return readiness.evaluate_outlook_readiness(primary, (candidate,))


def test_explicit_thread_read_preserves_declared_message_order() -> None:
    fixture = mock_ui.default_outlook_fixture()
    conversations = (
        conversation_reads.SyntheticConversation(
            conversation_key="thread-combined",
            message_keys=("msg-002", "msg-001"),
        ),
    )
    result = conversation_reads.read_fixture_conversation(
        fixture,
        "thread-combined",
        readiness=_ready_report(),
        conversations=conversations,
    )

    assert result.synthetic is True
    assert result.message_count == 2
    assert tuple(message.message_key for message in result.messages) == (
        "msg-002",
        "msg-001",
    )


def test_default_conversations_are_explicit_and_deterministic() -> None:
    catalog = conversation_reads.default_synthetic_conversations()

    assert tuple(item.conversation_key for item in catalog) == (
        "thread-project-update",
        "thread-meeting-notes",
    )
    assert catalog[0].message_keys == ("msg-001",)
    assert catalog[1].message_keys == ("msg-002",)


def test_unknown_or_dangling_thread_fails_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    try:
        conversation_reads.read_fixture_conversation(
            fixture,
            "missing-thread",
            readiness=_ready_report(),
        )
    except ValueError as exc:
        assert "conversation_key not found" in str(exc)
    else:
        raise AssertionError("unknown conversation must fail closed")

    dangling = (
        conversation_reads.SyntheticConversation(
            conversation_key="thread-dangling",
            message_keys=("msg-missing",),
        ),
    )
    try:
        conversation_reads.read_fixture_conversation(
            fixture,
            "thread-dangling",
            readiness=_ready_report(),
            conversations=dangling,
        )
    except ValueError as exc:
        assert "unknown synthetic message_key" in str(exc)
    else:
        raise AssertionError("dangling thread membership must fail closed")


def test_duplicate_thread_keys_and_message_keys_fail_closed() -> None:
    try:
        conversation_reads.SyntheticConversation(
            conversation_key="thread-a",
            message_keys=("msg-001", "msg-001"),
        )
    except ValueError as exc:
        assert "message_keys must be non-empty and unique" in str(exc)
    else:
        raise AssertionError("duplicate message membership must fail closed")

    duplicate_catalog = (
        conversation_reads.SyntheticConversation("thread-a", ("msg-001",)),
        conversation_reads.SyntheticConversation("thread-a", ("msg-002",)),
    )
    try:
        conversation_reads.read_fixture_conversation(
            mock_ui.default_outlook_fixture(),
            "thread-a",
            readiness=_ready_report(),
            conversations=duplicate_catalog,
        )
    except ValueError as exc:
        assert "catalog keys must be unique" in str(exc)
    else:
        raise AssertionError("duplicate thread keys must fail closed")


def test_out013_remains_reserved_without_thread_inference_primitive() -> None:
    assert default_tool_registry().by_application("outlook") == ()
    assert default_capability_registry().by_application("outlook") == ()
