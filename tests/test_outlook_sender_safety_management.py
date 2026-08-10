from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import sender_safety_management
from m365_mcp.tool_registry import default_tool_registry


def test_sender_block_and_safe_are_idempotent_and_exclusive() -> None:
    state = sender_safety_management.SenderSafetyState()
    state, blocked = sender_safety_management.apply_sender_safety_action(
        state,
        "sender-alpha",
        sender_safety_management.SenderSafetyAction.BLOCK,
    )
    assert state.blocked_sender_keys == ("sender-alpha",)
    assert blocked.changed is True
    assert blocked.read_back_verified is True
    assert blocked.dispatched is False

    state, safe = sender_safety_management.apply_sender_safety_action(
        state,
        "sender-alpha",
        sender_safety_management.SenderSafetyAction.SAFE_ADD,
    )
    assert state.blocked_sender_keys == ()
    assert state.safe_sender_keys == ("sender-alpha",)
    assert safe.changed is True

    state, again = sender_safety_management.apply_sender_safety_action(
        state,
        "sender-alpha",
        sender_safety_management.SenderSafetyAction.SAFE_ADD,
    )
    assert again.changed is False


def test_sender_safety_rejects_address_shape() -> None:
    with pytest.raises(ValueError, match="opaque"):
        sender_safety_management.apply_sender_safety_action(
            sender_safety_management.SenderSafetyState(),
            "person@example.test",
            sender_safety_management.SenderSafetyAction.BLOCK,
        )


def test_out122_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
