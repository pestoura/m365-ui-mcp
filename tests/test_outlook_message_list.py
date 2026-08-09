from __future__ import annotations

from m365_mcp.apps.outlook import discovery, mailbox_context, message_list, mock_ui, readiness
from m365_mcp.apps.outlook.shell_contracts import OutlookShellTarget
from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.tool_registry import default_tool_registry

EVIDENCE = "a" * 64


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


def test_inbox_message_list_is_deterministic_and_bounded() -> None:
    result = message_list.list_fixture_messages(
        mock_ui.default_outlook_fixture(),
        message_list.MessageListRequest(folder_key="inbox", limit=1),
        readiness=_ready_report(),
    )

    assert result.synthetic is True
    assert result.folder_key == "inbox"
    assert result.total_matching == 1
    assert result.has_more is False
    assert tuple(item.message_key for item in result.items) == ("msg-001",)
    assert result.items[0].subject == "Synthetic project update"
    assert result.items[0].is_read is False


def test_archive_message_metadata_preserves_attachment_flag() -> None:
    result = message_list.list_fixture_messages(
        mock_ui.default_outlook_fixture(),
        message_list.MessageListRequest(folder_key="archive"),
        readiness=_ready_report(),
    )

    assert tuple(item.message_key for item in result.items) == ("msg-002",)
    assert result.items[0].has_attachments is True
    assert result.items[0].is_read is True


def test_pagination_can_return_empty_page_without_expanding_scope() -> None:
    result = message_list.list_fixture_messages(
        mock_ui.default_outlook_fixture(),
        message_list.MessageListRequest(folder_key="inbox", offset=1, limit=1),
        readiness=_ready_report(),
    )

    assert result.items == ()
    assert result.total_matching == 1
    assert result.offset == 1
    assert result.limit == 1
    assert result.has_more is False


def test_unknown_folder_and_unready_discovery_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    try:
        message_list.list_fixture_messages(
            fixture,
            message_list.MessageListRequest(folder_key="unknown"),
            readiness=_ready_report(),
        )
    except ValueError as exc:
        assert "unknown synthetic folder_key" in str(exc)
    else:
        raise AssertionError("unknown folder must fail closed")

    unready = readiness.OutlookReadinessReport(
        state=readiness.OutlookReadinessState.FOUNDATION_READY,
        primary_context_verified=True,
        shared_context_verified=False,
        candidate_count=1,
        observed_count=0,
        blocked_count=0,
        reattestation_count=0,
    )
    try:
        message_list.list_fixture_messages(
            fixture,
            message_list.MessageListRequest(),
            readiness=unready,
        )
    except ValueError as exc:
        assert "read-only discovery is not ready" in str(exc)
    else:
        raise AssertionError("unready Outlook discovery must fail closed")


def test_message_list_request_rejects_unbounded_or_invalid_inputs() -> None:
    for kwargs in (
        {"limit": 101},
        {"limit": 0},
        {"offset": -1},
        {"folder_key": "bad folder"},
    ):
        try:
            message_list.MessageListRequest(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid message-list request accepted: {kwargs!r}")


def test_out010_does_not_activate_outlook_public_execution_surfaces() -> None:
    assert default_tool_registry().by_application("outlook") == ()
    assert default_capability_registry().by_application("outlook") == ()
