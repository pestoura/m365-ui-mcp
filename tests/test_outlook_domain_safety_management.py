from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import domain_safety_management
from m365_mcp.tool_registry import default_tool_registry


def test_domain_block_and_safe_are_idempotent_and_exclusive() -> None:
    state = domain_safety_management.DomainSafetyState()
    state, blocked = domain_safety_management.apply_domain_safety_action(
        state,
        "domain-alpha",
        domain_safety_management.DomainSafetyAction.BLOCK,
    )
    assert state.blocked_domain_keys == ("domain-alpha",)
    assert blocked.changed is True
    assert blocked.read_back_verified is True
    assert blocked.dispatched is False

    state, safe = domain_safety_management.apply_domain_safety_action(
        state,
        "domain-alpha",
        domain_safety_management.DomainSafetyAction.SAFE_ADD,
    )
    assert state.blocked_domain_keys == ()
    assert state.safe_domain_keys == ("domain-alpha",)
    assert safe.changed is True

    state, again = domain_safety_management.apply_domain_safety_action(
        state,
        "domain-alpha",
        domain_safety_management.DomainSafetyAction.SAFE_ADD,
    )
    assert again.changed is False


def test_domain_safety_rejects_real_domain_shape() -> None:
    with pytest.raises(ValueError, match="opaque"):
        domain_safety_management.apply_domain_safety_action(
            domain_safety_management.DomainSafetyState(),
            "example.test",
            domain_safety_management.DomainSafetyAction.BLOCK,
        )


def test_out123_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
