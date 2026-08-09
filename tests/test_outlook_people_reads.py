from __future__ import annotations

from m365_mcp.apps.outlook import mock_ui, people_reads, readiness
from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.tool_registry import default_tool_registry


def _ready() -> readiness.OutlookReadinessReport:
    return readiness.OutlookReadinessReport(
        state=readiness.OutlookReadinessState.DISCOVERY_READY,
        primary_context_verified=True,
        shared_context_verified=False,
        candidate_count=1,
        observed_count=1,
        blocked_count=0,
        reattestation_count=0,
    )


def test_search_and_get_contacts() -> None:
    fixture = mock_ui.default_outlook_fixture()
    result = people_reads.search_fixture_contacts(fixture, "example", readiness=_ready())
    assert [item.contact_key for item in result.items] == ["person-alpha", "person-charlie"]
    assert result.total_matching == 2
    item = people_reads.get_fixture_contact(fixture, "person-bravo", readiness=_ready())
    assert item.display_name == "Bea Sample"


def test_invalid_queries_and_keys_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    for query in ("", " bad", "x" * 81):
        try:
            people_reads.search_fixture_contacts(fixture, query, readiness=_ready())
        except ValueError:
            pass
        else:
            raise AssertionError("invalid query accepted")
    try:
        people_reads.get_fixture_contact(fixture, "person@example.invalid", readiness=_ready())
    except ValueError:
        pass
    else:
        raise AssertionError("identity-shaped key accepted")


def test_catalog_integrity_and_unknown_key_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    duplicate = people_reads.SyntheticContact("person-a", "A")
    for catalog in ((), (duplicate, duplicate)):
        try:
            people_reads.search_fixture_contacts(fixture, "a", readiness=_ready(), contacts=catalog)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid catalog accepted")
    try:
        people_reads.get_fixture_contact(fixture, "missing", readiness=_ready())
    except ValueError as exc:
        assert "not found" in str(exc)
    else:
        raise AssertionError("unknown contact accepted")


def test_projection_has_no_identity_or_browser_primitives() -> None:
    fixture = mock_ui.default_outlook_fixture()
    projection = repr(people_reads.get_fixture_contact(fixture, "person-alpha", readiness=_ready()).to_projection()).lower()
    for forbidden in ("@", "http", "://", "selector", "xpath", "javascript", "cookie", "tenant"):
        assert forbidden not in projection


def test_out025_keeps_outlook_activation_absent() -> None:
    assert default_tool_registry().by_application("outlook") == ()
    assert default_capability_registry().by_application("outlook") == ()
