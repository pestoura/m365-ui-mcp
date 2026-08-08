from __future__ import annotations

import pytest

from m365_mcp.apps.outlook.discovery import (
    DiscoveryState,
    OutlookCapabilityCandidate,
    default_outlook_discovery_candidates,
)
from m365_mcp.apps.outlook.mailbox_context import PrimaryMailboxContext, PrimaryMailboxContextState
from m365_mcp.apps.outlook.readiness import OutlookReadinessState, evaluate_outlook_readiness
from m365_mcp.apps.outlook.shared_mailbox_context import (
    SharedMailboxContext,
    SharedMailboxContextState,
)
from m365_mcp.apps.outlook.shell_contracts import OutlookShellTarget
from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.tool_registry import default_tool_registry


DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


def _verified_primary() -> PrimaryMailboxContext:
    return PrimaryMailboxContext(
        state=PrimaryMailboxContextState.VERIFIED,
        account_context_verified=True,
        primary_shell_verified=True,
        evidence_digest=DIGEST_A,
    )


def _observed_mail() -> OutlookCapabilityCandidate:
    return OutlookCapabilityCandidate(
        capability_key="mail.read",
        shell_target=OutlookShellTarget.MAIL,
        shell_contract_key="outlook.shell.mail",
        state=DiscoveryState.OBSERVED,
        evidence_digest=DIGEST_B,
    )


def test_unobserved_foundation_is_not_promoted_to_readiness() -> None:
    report = evaluate_outlook_readiness(
        _verified_primary(),
        default_outlook_discovery_candidates(),
    )

    assert report.state is OutlookReadinessState.FOUNDATION_READY
    assert report.ready_for_readonly_discovery is False
    assert report.observed_count == 0
    assert report.to_dict()["live_support_promoted"] is False
    assert report.to_dict()["public_tools_enabled"] is False
    assert report.to_dict()["browser_operations_enabled"] is False


def test_observed_candidate_allows_bounded_readonly_discovery_smoke() -> None:
    report = evaluate_outlook_readiness(_verified_primary(), (_observed_mail(),))

    assert report.state is OutlookReadinessState.DISCOVERY_READY
    assert report.ready_for_readonly_discovery is True
    assert report.candidate_count == 1
    assert report.observed_count == 1


def test_invalid_primary_context_blocks_discovery() -> None:
    primary = PrimaryMailboxContext(
        state=PrimaryMailboxContextState.UNVERIFIED,
        account_context_verified=True,
        primary_shell_verified=False,
    )

    report = evaluate_outlook_readiness(primary, (_observed_mail(),))

    assert report.state is OutlookReadinessState.BLOCKED
    assert report.ready_for_readonly_discovery is False


def test_reattestation_dominates_other_outcomes() -> None:
    candidate = OutlookCapabilityCandidate(
        capability_key="mail.read",
        shell_target=OutlookShellTarget.MAIL,
        shell_contract_key="outlook.shell.mail",
        state=DiscoveryState.REATTESTATION_REQUIRED,
    )

    report = evaluate_outlook_readiness(_verified_primary(), (candidate,))

    assert report.state is OutlookReadinessState.REATTESTATION_REQUIRED
    assert report.ready_for_readonly_discovery is False


def test_verified_shared_context_is_projected_without_identity() -> None:
    shared = SharedMailboxContext(
        state=SharedMailboxContextState.VERIFIED,
        primary_context_verified=True,
        shared_shell_verified=True,
        scope_digest=DIGEST_A,
        evidence_digest=DIGEST_B,
    )

    report = evaluate_outlook_readiness(
        _verified_primary(),
        (_observed_mail(),),
        shared_context=shared,
    )
    projection = report.to_dict()

    assert report.shared_context_verified is True
    assert projection["shared_context_verified"] is True
    assert DIGEST_A not in repr(projection)
    assert DIGEST_B not in repr(projection)


def test_readiness_rejects_empty_or_duplicate_candidate_sets() -> None:
    with pytest.raises(ValueError, match="requires discovery candidates"):
        evaluate_outlook_readiness(_verified_primary(), ())

    candidate = _observed_mail()
    with pytest.raises(ValueError, match="must be unique"):
        evaluate_outlook_readiness(_verified_primary(), (candidate, candidate))


def test_outlook_readiness_does_not_activate_public_execution_surfaces() -> None:
    assert default_tool_registry().by_application("outlook") == ()
    assert default_capability_registry().by_application("outlook") == ()
