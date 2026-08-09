from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import (
    mail_search,
    message_get,
    mock_ui,
    readiness,
    shared_mailbox_context,
    shared_mailbox_reads,
)
from m365_mcp.tool_registry import default_tool_registry


def _ready() -> readiness.OutlookReadinessReport:
    return readiness.OutlookReadinessReport(
        state=readiness.OutlookReadinessState.DISCOVERY_READY,
        primary_context_verified=True,
        shared_context_verified=True,
        candidate_count=1,
        observed_count=1,
        blocked_count=0,
        reattestation_count=0,
    )


def _context(*, valid: bool) -> shared_mailbox_context.SharedMailboxContext:
    return shared_mailbox_context.SharedMailboxContext(
        state=(
            shared_mailbox_context.SharedMailboxContextState.VERIFIED
            if valid
            else shared_mailbox_context.SharedMailboxContextState.UNVERIFIED
        ),
        primary_context_verified=True,
        shared_shell_verified=valid,
        scope_digest="a" * 64 if valid else None,
        evidence_digest="b" * 64 if valid else None,
    )


def test_shared_mailbox_search_and_read_compose_existing_semantics() -> None:
    fixture = mock_ui.default_outlook_fixture()
    search = shared_mailbox_reads.search_shared_mailbox_messages(
        _context(valid=True),
        fixture,
        mail_search.MailSearchRequest(query="synthetic"),
        readiness=_ready(),
    )
    assert search.shared_scope_verified is True
    assert search.result.synthetic is True
    read = shared_mailbox_reads.get_shared_mailbox_message(
        _context(valid=True),
        fixture,
        message_get.MessageGetRequest("msg-001"),
        readiness=_ready(),
    )
    assert read.result.message_key == "msg-001"


def test_shared_mailbox_reads_fail_closed_without_verified_scope() -> None:
    fixture = mock_ui.default_outlook_fixture()
    with pytest.raises(ValueError, match="verified shared mailbox context"):
        shared_mailbox_reads.search_shared_mailbox_messages(
            _context(valid=False),
            fixture,
            mail_search.MailSearchRequest(limit=1),
            readiness=_ready(),
        )


def test_out112_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
