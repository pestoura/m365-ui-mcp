from __future__ import annotations

import m365_mcp.apps.outlook.discovery as discovery
import m365_mcp.apps.outlook.mailbox_context as mailbox_context
import m365_mcp.apps.outlook.readiness as outlook_readiness
import m365_mcp.apps.outlook.shared_mailbox_context as shared_mailbox_context
import m365_mcp.apps.outlook.shell_contracts as shell_contracts
from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.tool_registry import default_tool_registry

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


def _verified_primary() -> mailbox_context.PrimaryMailboxContext:
    return mailbox_context.PrimaryMailboxContext(
        state=mailbox_context.PrimaryMailboxContextState.VERIFIED,
        account_context_verified=True,
        primary_shell_verified=True,
        evidence_digest=DIGEST_A,
    )


def _observed_mail() -> discovery.OutlookCapabilityCandidate:
    return discovery.OutlookCapabilityCandidate(
        capability_key="mail.read",
        shell_target=shell_contracts.OutlookShellTarget.MAIL,
        shell_contract_key="outlook.shell.mail",
        state=discovery.DiscoveryState.OBSERVED,
        evidence_digest=DIGEST_B,
    )


def test_unobserved_foundation_is_not_promoted_to_readiness() -> None:
    report = outlook_readiness.evaluate_outlook_readiness(
        _verified_primary(),
        discovery.default_outlook_discovery_candidates(),
    )

    assert report.state is outlook_readiness.OutlookReadinessState.FOUNDATION_READY
    assert report.ready_for_readonly_discovery is False
    assert report.observed_count == 0
    assert report.to_dict()["live_support_promoted"] is False
    assert report.to_dict()["public_tools_enabled"] is False
    assert report.to_dict()["browser_operations_enabled"] is False


def test_observed_candidate_allows_bounded_readonly_discovery_smoke() -> None:
    report = outlook_readiness.evaluate_outlook_readiness(
        _verified_primary(),
        (_observed_mail(),),
    )

    assert report.state is outlook_readiness.OutlookReadinessState.DISCOVERY_READY
    assert report.ready_for_readonly_discovery is True
    assert report.candidate_count == 1
    assert report.observed_count == 1


def test_invalid_primary_context_blocks_discovery() -> None:
    primary = mailbox_context.PrimaryMailboxContext(
        state=mailbox_context.PrimaryMailboxContextState.UNVERIFIED,
        account_context_verified=True,
        primary_shell_verified=False,
    )

    report = outlook_readiness.evaluate_outlook_readiness(primary, (_observed_mail(),))

    assert report.state is outlook_readiness.OutlookReadinessState.BLOCKED
    assert report.ready_for_readonly_discovery is False


def test_reattestation_dominates_other_outcomes() -> None:
    candidate = discovery.OutlookCapabilityCandidate(
        capability_key="mail.read",
        shell_target=shell_contracts.OutlookShellTarget.MAIL,
        shell_contract_key="outlook.shell.mail",
        state=discovery.DiscoveryState.REATTESTATION_REQUIRED,
    )

    report = outlook_readiness.evaluate_outlook_readiness(
        _verified_primary(),
        (candidate,),
    )

    assert report.state is outlook_readiness.OutlookReadinessState.REATTESTATION_REQUIRED
    assert report.ready_for_readonly_discovery is False


def test_verified_shared_context_is_projected_without_identity() -> None:
    shared = shared_mailbox_context.SharedMailboxContext(
        state=shared_mailbox_context.SharedMailboxContextState.VERIFIED,
        primary_context_verified=True,
        shared_shell_verified=True,
        scope_digest=DIGEST_A,
        evidence_digest=DIGEST_B,
    )

    report = outlook_readiness.evaluate_outlook_readiness(
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
    try:
        outlook_readiness.evaluate_outlook_readiness(_verified_primary(), ())
    except ValueError as exc:
        assert "requires discovery candidates" in str(exc)
    else:
        raise AssertionError("empty discovery candidates must fail")

    candidate = _observed_mail()
    try:
        outlook_readiness.evaluate_outlook_readiness(
            _verified_primary(),
            (candidate, candidate),
        )
    except ValueError as exc:
        assert "must be unique" in str(exc)
    else:
        raise AssertionError("duplicate discovery candidates must fail")


def test_outlook_readiness_does_not_activate_public_execution_surfaces() -> None:
    assert default_tool_registry().by_application("outlook") == ()
    assert default_capability_registry().by_application("outlook") == ()
