from __future__ import annotations

from m365_mcp.apps.outlook import mock_ui, myday_reads, readiness
from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.tool_registry import default_tool_registry


def _ready() -> readiness.OutlookReadinessReport:
    return readiness.OutlookReadinessReport(state=readiness.OutlookReadinessState.DISCOVERY_READY, primary_context_verified=True, shared_context_verified=False, candidate_count=1, observed_count=1, blocked_count=0, reattestation_count=0)


def test_smart_lists_are_deterministic() -> None:
    fixture = mock_ui.default_outlook_fixture()
    assert [item.task_key for item in myday_reads.read_fixture_smart_list(fixture, myday_reads.SmartListKind.MY_DAY, readiness=_ready())] == ["smart-alpha"]
    assert [item.task_key for item in myday_reads.read_fixture_smart_list(fixture, myday_reads.SmartListKind.IMPORTANT, readiness=_ready())] == ["smart-alpha"]
    assert [item.task_key for item in myday_reads.read_fixture_smart_list(fixture, myday_reads.SmartListKind.PLANNED, readiness=_ready())] == ["smart-alpha", "smart-bravo"]
    assert [item.task_key for item in myday_reads.read_fixture_smart_list(fixture, myday_reads.SmartListKind.COMPLETED, readiness=_ready())] == ["smart-charlie"]


def test_duplicate_keys_and_bad_reference_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    item = myday_reads.SyntheticSmartTask("smart-a", "A")
    try:
        myday_reads.read_fixture_smart_list(fixture, myday_reads.SmartListKind.MY_DAY, readiness=_ready(), tasks=(item, item))
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("duplicate task keys accepted")
    try:
        myday_reads.read_fixture_smart_list(fixture, myday_reads.SmartListKind.PLANNED, readiness=_ready(), reference_day_offset=5000)
    except ValueError as exc:
        assert "bounded" in str(exc)
    else:
        raise AssertionError("unbounded reference accepted")


def test_projection_excludes_identity_and_browser_primitives() -> None:
    projection = repr(myday_reads.default_synthetic_smart_tasks()[0].to_projection()).lower()
    for forbidden in ("@", "http", "://", "selector", "xpath", "javascript", "cookie", "tenant", "utc"):
        assert forbidden not in projection


def test_out029_keeps_outlook_activation_absent() -> None:
    assert default_tool_registry().by_application("outlook") == ()
    assert default_capability_registry().by_application("outlook") == ()
