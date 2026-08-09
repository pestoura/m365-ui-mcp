from __future__ import annotations

from m365_mcp.apps.outlook import discovery, mailbox_context, message_get, mock_ui, readiness
from m365_mcp.apps.outlook.shell_contracts import OutlookShellTarget
from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.tool_registry import default_tool_registry

EVIDENCE = "b" * 64


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


def test_message_get_returns_exact_synthetic_message_metadata() -> None:
    result = message_get.get_fixture_message(
        mock_ui.default_outlook_fixture(),
        message_get.MessageGetRequest(message_key="msg-002"),
        readiness=_ready_report(),
    )

    assert result.message_key == "msg-002"
    assert result.subject == "Synthetic meeting notes"
    assert result.folder_key == "archive"
    assert result.is_read is True
    assert result.has_attachments is True
    assert result.synthetic is True


def test_unknown_message_and_unready_discovery_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    try:
        message_get.get_fixture_message(
            fixture,
            message_get.MessageGetRequest(message_key="missing"),
            readiness=_ready_report(),
        )
    except ValueError as exc:
        assert "message_key not found" in str(exc)
    else:
        raise AssertionError("unknown message key must fail closed")

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
        message_get.get_fixture_message(
            fixture,
            message_get.MessageGetRequest(message_key="msg-001"),
            readiness=unready,
        )
    except ValueError as exc:
        assert "read-only discovery is not ready" in str(exc)
    else:
        raise AssertionError("unready message get must fail closed")


def test_message_key_validation_is_bounded() -> None:
    for value in ("", " ", "bad key"):
        try:
            message_get.MessageGetRequest(message_key=value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid message key accepted: {value!r}")


def test_out011_keeps_outlook_execution_surface_reserved() -> None:
    assert default_tool_registry().by_application("outlook") == ()
    assert default_capability_registry().by_application("outlook") == ()
