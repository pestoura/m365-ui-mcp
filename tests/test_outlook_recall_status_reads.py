from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import recall_status_reads
from m365_mcp.tool_registry import default_tool_registry


def test_recall_status_reports_bounded_aggregate_state() -> None:
    status = recall_status_reads.SyntheticRecallStatus(
        recall_key="recall-057",
        sent_message_key="msg-sent-001",
        status=recall_status_reads.RecallStatus.PARTIAL,
        attempted_count=3,
        succeeded_count=2,
        failed_count=1,
    )
    read_back = recall_status_reads.read_recall_status((status,), "recall-057")
    assert read_back.status is recall_status_reads.RecallStatus.PARTIAL
    assert read_back.to_projection()["attempted_count"] == 3
    assert read_back.synthetic is True


def test_recall_status_rejects_inconsistent_counts_and_unknown_key() -> None:
    with pytest.raises(ValueError, match="both success and failure"):
        recall_status_reads.SyntheticRecallStatus(
            recall_key="recall-057",
            sent_message_key="msg-sent-001",
            status=recall_status_reads.RecallStatus.PARTIAL,
            attempted_count=2,
            succeeded_count=2,
            failed_count=0,
        )

    with pytest.raises(ValueError, match="exactly one"):
        recall_status_reads.read_recall_status((), "recall-missing")


def test_out057_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
