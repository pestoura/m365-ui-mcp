from m365_mcp.application_registry import ApplicationState
from m365_mcp.apps.outlook.directory_org_reads import SyntheticDirectoryPerson
from m365_mcp.apps.outlook.manifest import foundation_manifest
from m365_mcp.apps.outlook.people_reads import SyntheticContact
from m365_mcp.tool_registry import default_tool_registry
from m365_mcp.xapp_outlook_person_context import build_synthetic_person_context


def _expect_value_error(callable_object: object) -> None:
    try:
        callable_object()  # type: ignore[operator]
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_person_context_links_synthetic_records_without_live_support() -> None:
    contact = SyntheticContact("person-alpha", "Alex Example", "Example Org", "Architect")
    directory = SyntheticDirectoryPerson(
        "dir-alpha",
        "Alex Example",
        "Architect",
        "Security",
        "dir-lead",
    )
    context = build_synthetic_person_context(contact, directory)

    assert context.contact_key == "person-alpha"
    assert context.directory_person_key == "dir-alpha"
    assert context.manager_key == "dir-lead"
    assert context.synthetic is True
    assert context.live_observed is False
    assert context.execution_performed is False


def test_person_context_fails_closed_on_unlinked_records() -> None:
    contact = SyntheticContact("person-alpha", "Alex Example")
    directory = SyntheticDirectoryPerson("dir-bravo", "Bea Sample", "Engineer", "Platform")

    _expect_value_error(lambda: build_synthetic_person_context(contact, directory))


def test_outlook_boundary_remains_reserved_and_private() -> None:
    assert foundation_manifest().state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
