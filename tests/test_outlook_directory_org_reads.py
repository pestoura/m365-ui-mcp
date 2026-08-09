from __future__ import annotations

from m365_mcp.apps.outlook import directory_org_reads, mock_ui, readiness
from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.tool_registry import default_tool_registry


def _ready() -> readiness.OutlookReadinessReport:
    return readiness.OutlookReadinessReport(state=readiness.OutlookReadinessState.DISCOVERY_READY, primary_context_verified=True, shared_context_verified=False, candidate_count=1, observed_count=1, blocked_count=0, reattestation_count=0)


def test_directory_search_and_org_context() -> None:
    fixture = mock_ui.default_outlook_fixture()
    hits = directory_org_reads.search_fixture_directory(fixture, "security", readiness=_ready())
    assert [item.person_key for item in hits] == ["dir-lead", "dir-architect"]
    context = directory_org_reads.read_fixture_org_context(fixture, "dir-lead", readiness=_ready())
    assert context["direct_report_keys"] == ("dir-architect", "dir-engineer")


def test_dangling_manager_and_unknown_person_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    bad = (directory_org_reads.SyntheticDirectoryPerson("dir-a", "A", "Role", "Unit", "missing"),)
    try:
        directory_org_reads.search_fixture_directory(fixture, "a", readiness=_ready(), directory=bad)
    except ValueError as exc:
        assert "manager_key" in str(exc)
    else:
        raise AssertionError("dangling manager accepted")
    try:
        directory_org_reads.read_fixture_org_context(fixture, "missing", readiness=_ready())
    except ValueError as exc:
        assert "not found" in str(exc)
    else:
        raise AssertionError("unknown person accepted")


def test_projection_excludes_identity_and_browser_primitives() -> None:
    fixture = mock_ui.default_outlook_fixture()
    projection = repr(directory_org_reads.read_fixture_org_context(fixture, "dir-lead", readiness=_ready())).lower()
    for forbidden in ("@", "http", "://", "selector", "xpath", "javascript", "cookie", "tenant"):
        assert forbidden not in projection


def test_out026_keeps_outlook_activation_absent() -> None:
    assert default_tool_registry().by_application("outlook") == ()
    assert default_capability_registry().by_application("outlook") == ()
