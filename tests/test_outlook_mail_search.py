from __future__ import annotations

from m365_mcp.apps.outlook import discovery, mail_search, mailbox_context, mock_ui, readiness
from m365_mcp.apps.outlook.shell_contracts import OutlookShellTarget
from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.tool_registry import default_tool_registry

EVIDENCE = "c" * 64


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


def test_subject_query_is_case_insensitive_and_deterministic() -> None:
    result = mail_search.search_fixture_messages(
        mock_ui.default_outlook_fixture(),
        mail_search.MailSearchRequest(query="PROJECT"),
        readiness=_ready_report(),
    )

    assert result.synthetic is True
    assert result.total_matching == 1
    assert tuple(item.message_key for item in result.items) == ("msg-001",)


def test_search_filters_folder_read_and_attachment_metadata() -> None:
    result = mail_search.search_fixture_messages(
        mock_ui.default_outlook_fixture(),
        mail_search.MailSearchRequest(
            folder_key="archive",
            is_read=True,
            has_attachments=True,
        ),
        readiness=_ready_report(),
    )

    assert tuple(item.message_key for item in result.items) == ("msg-002",)
    assert result.items[0].folder_key == "archive"
    assert result.items[0].has_attachments is True


def test_combined_filter_can_return_bounded_empty_result() -> None:
    result = mail_search.search_fixture_messages(
        mock_ui.default_outlook_fixture(),
        mail_search.MailSearchRequest(query="meeting", is_read=False),
        readiness=_ready_report(),
    )

    assert result.items == ()
    assert result.total_matching == 0
    assert result.has_more is False


def test_search_request_and_context_fail_closed() -> None:
    for kwargs in (
        {"query": " "},
        {"query": "x" * 201},
        {"folder_key": "bad folder"},
        {"offset": -1},
        {"limit": 0},
        {"limit": 101},
    ):
        try:
            mail_search.MailSearchRequest(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid search request accepted: {kwargs!r}")

    fixture = mock_ui.default_outlook_fixture()
    try:
        mail_search.search_fixture_messages(
            fixture,
            mail_search.MailSearchRequest(folder_key="unknown"),
            readiness=_ready_report(),
        )
    except ValueError as exc:
        assert "unknown synthetic folder_key" in str(exc)
    else:
        raise AssertionError("unknown folder must fail closed")


def test_out012_remains_reserved_and_does_not_activate_generic_search() -> None:
    assert default_tool_registry().by_application("outlook") == ()
    assert default_capability_registry().by_application("outlook") == ()
