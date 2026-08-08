from __future__ import annotations

import pytest

from m365_mcp.apps.outlook import (
    DiscoveryState,
    OutlookCapabilityCandidate,
    OutlookShellTarget,
    default_outlook_discovery_candidates,
    foundation_manifest,
)
from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.tool_registry import default_tool_registry


def test_default_outlook_discovery_candidates_are_closed_and_unobserved() -> None:
    candidates = default_outlook_discovery_candidates()

    assert tuple(candidate.capability_key for candidate in candidates) == (
        "mail.read",
        "calendar.read",
        "people.read",
        "todo.read",
        "settings.read",
    )
    assert all(candidate.state is DiscoveryState.UNOBSERVED for candidate in candidates)
    assert all(candidate.evidence_digest is None for candidate in candidates)


def test_discovery_candidate_requires_matching_shell_contract() -> None:
    with pytest.raises(ValueError, match="shell contract mismatch"):
        OutlookCapabilityCandidate(
            "mail.read",
            OutlookShellTarget.MAIL,
            "outlook.shell.calendar",
        )


def test_observed_candidate_requires_bounded_evidence_digest() -> None:
    with pytest.raises(ValueError, match="requires evidence digest"):
        OutlookCapabilityCandidate(
            "mail.read",
            OutlookShellTarget.MAIL,
            "outlook.shell.mail",
            state=DiscoveryState.OBSERVED,
        )

    observed = OutlookCapabilityCandidate(
        "mail.read",
        OutlookShellTarget.MAIL,
        "outlook.shell.mail",
        state=DiscoveryState.OBSERVED,
        evidence_digest="a" * 64,
    )
    assert observed.evidence_digest == "a" * 64


def test_unobserved_candidate_cannot_smuggle_evidence_or_activate_outlook() -> None:
    with pytest.raises(ValueError, match="cannot carry evidence digest"):
        OutlookCapabilityCandidate(
            "mail.read",
            OutlookShellTarget.MAIL,
            "outlook.shell.mail",
            evidence_digest="a" * 64,
        )

    manifest = foundation_manifest()
    assert manifest.public_tools_enabled is False
    assert manifest.browser_operations_enabled is False
    assert default_tool_registry().by_application("outlook") == ()
    assert default_capability_registry().by_application("outlook") == ()
