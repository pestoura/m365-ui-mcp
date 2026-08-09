from __future__ import annotations

from m365_mcp.apps.outlook import attachment_metadata, discovery, mailbox_context, mock_ui, readiness
from m365_mcp.apps.outlook.shell_contracts import OutlookShellTarget
from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.tool_registry import default_tool_registry

EVIDENCE = "e" * 64


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


def test_attachment_metadata_is_explicit_and_contains_no_payload() -> None:
    result = attachment_metadata.list_fixture_attachment_metadata(
        mock_ui.default_outlook_fixture(),
        "msg-002",
        readiness=_ready_report(),
    )

    assert result.synthetic is True
    assert result.attachment_count == 1
    attachment = result.attachments[0]
    assert attachment.attachment_key == "att-001"
    assert attachment.file_name == "synthetic-meeting-notes.txt"
    assert attachment.media_type == "text/plain"
    assert attachment.size_bytes == 128
    assert not hasattr(attachment, "content")
    assert not hasattr(attachment, "url")
    assert not hasattr(attachment, "locator")


def test_message_without_attachments_returns_empty_metadata_list() -> None:
    result = attachment_metadata.list_fixture_attachment_metadata(
        mock_ui.default_outlook_fixture(),
        "msg-001",
        readiness=_ready_report(),
    )

    assert result.attachments == ()
    assert result.attachment_count == 0


def test_attachment_catalog_drift_fails_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    dangling = (
        attachment_metadata.SyntheticAttachment(
            attachment_key="att-dangling",
            message_key="msg-missing",
            file_name="synthetic.txt",
            media_type="text/plain",
            size_bytes=1,
        ),
    )
    try:
        attachment_metadata.list_fixture_attachment_metadata(
            fixture,
            "msg-002",
            readiness=_ready_report(),
            attachments=dangling,
        )
    except ValueError as exc:
        assert "unknown synthetic message_key" in str(exc)
    else:
        raise AssertionError("dangling attachment metadata must fail closed")

    mismatch = ()
    try:
        attachment_metadata.list_fixture_attachment_metadata(
            fixture,
            "msg-002",
            readiness=_ready_report(),
            attachments=mismatch,
        )
    except ValueError as exc:
        assert "disagrees with message attachment state" in str(exc)
    else:
        raise AssertionError("attachment-state mismatch must fail closed")


def test_attachment_metadata_validation_is_bounded() -> None:
    invalid = (
        {"attachment_key": "bad key", "size_bytes": 1},
        {"attachment_key": "att-x", "media_type": "invalid", "size_bytes": 1},
        {"attachment_key": "att-x", "size_bytes": -1},
    )
    for overrides in invalid:
        values = {
            "attachment_key": "att-x",
            "message_key": "msg-002",
            "file_name": "synthetic.txt",
            "media_type": "text/plain",
            "size_bytes": 1,
        }
        values.update(overrides)
        try:
            attachment_metadata.SyntheticAttachment(**values)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid attachment metadata accepted: {values!r}")


def test_out014_keeps_attachment_retrieval_and_outlook_activation_absent() -> None:
    assert default_tool_registry().by_application("outlook") == ()
    assert default_capability_registry().by_application("outlook") == ()
