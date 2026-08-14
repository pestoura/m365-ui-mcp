"""UIContract fail-closed and capability model tests."""

from __future__ import annotations

import pytest

from planner_mcp.capabilities import build_capabilities
from planner_mcp.errors import UiContractUnattested, UiDrift
from planner_mcp.ui_contract import assert_no_drift, load_status, require_attested

CAP_030_STATES = {
    "UNVERIFIED_LIVE",
    "DISCOVERED",
    "READ_SUPPORTED",
    "MUTATION_SUPPORTED",
    "DEGRADED",
    "BLOCKED",
    "OUT_OF_SCOPE",
}


_AUTH_SELECTORS = {
    "auth.login_email_input",
    "auth.login_next_button",
    "auth.login_password_input",
    "auth.login_signin_button",
}


def test_selectors_are_unverified_and_not_fabricated() -> None:
    status = load_status()
    # The aggregate status is still UNVERIFIED because the Planner fragments are
    # not yet attested; full attestation requires them too. The promoted
    # common.auth fragments are reflected as attested and removed from the
    # unverified set, while every non-auth selector remains unverified.
    assert status.attested is False
    assert status.attestation_status == "UNVERIFIED_LIVE"
    assert status.selector_count > 0
    assert len(status.unverified_selectors) == status.selector_count - len(_AUTH_SELECTORS)
    assert all(name not in _AUTH_SELECTORS for name in status.unverified_selectors)
    assert status.unverified_selectors == tuple(
        name for name in status.unverified_selectors if name not in _AUTH_SELECTORS
    )


def test_require_attested_fails_closed() -> None:
    with pytest.raises(UiContractUnattested):
        require_attested("plan_list")


def test_drift_detection() -> None:
    assert_no_drift(load_status().version)
    with pytest.raises(UiDrift):
        assert_no_drift("9.9.9")


def test_capabilities_do_not_use_graph_or_mock_as_live_evidence() -> None:
    caps = build_capabilities(license_evidence={"premium_detected": True})
    assert caps["graph_api_used"] is False
    assert set(caps["support_levels"]) == CAP_030_STATES
    assert caps["capabilities"]
    for row in caps["capabilities"]:
        assert row["support_level"] == "UNVERIFIED_LIVE"
        assert row["tenant_license_availability"] == "OBSERVED"
        assert row["ui_observed"] == "UNVERIFIED_LIVE"
        assert row["ui_contract_status"] == "UNVERIFIED_LIVE"
        assert row["read_attestation"] == "NO"
        assert row["mutation_attestation"] == "NO"
