from __future__ import annotations

from m365_mcp.apps.outlook import default_outlook_fixture, foundation_manifest
from m365_mcp.tool_registry import default_tool_registry


def test_outlook_mock_fixture_is_deterministic_and_synthetic() -> None:
    first = default_outlook_fixture()
    second = default_outlook_fixture()

    assert first == second
    assert first.fixture_version == "outlook-mock-v1"
    assert first.synthetic is True
    assert first.mailbox_key == "mock-primary"
    assert first.folders == ("inbox", "archive", "sent")
    assert tuple(message.message_key for message in first.messages) == (
        "msg-001",
        "msg-002",
    )


def test_outlook_mock_fixture_contains_no_live_identity_or_routing_material() -> None:
    fixture = default_outlook_fixture()
    serialized = repr(fixture).lower()

    forbidden = (
        "@",
        "https://",
        "cookie",
        "token",
        "tenant_id",
        "storage_state",
        "selector",
        "xpath",
    )
    assert not any(marker in serialized for marker in forbidden)


def test_out_002_does_not_activate_outlook_execution() -> None:
    manifest = foundation_manifest()
    registry = default_tool_registry()

    assert manifest.public_tools_enabled is False
    assert manifest.browser_operations_enabled is False
    assert registry.by_application("outlook") == ()
