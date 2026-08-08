"""UIContract fail-closed and capability model tests."""

from __future__ import annotations

import pytest

from planner_mcp.capabilities import build_capabilities
from planner_mcp.errors import UiContractUnattested, UiDrift
from planner_mcp.ui_contract import assert_no_drift, load_status, require_attested


def test_selectors_are_unverified_and_not_fabricated() -> None:
    status = load_status()
    assert status.attested is False
    assert status.attestation_status == "UNVERIFIED_LIVE"
    assert status.selector_count > 0
    assert len(status.unverified_selectors) == status.selector_count


def test_require_attested_fails_closed() -> None:
    with pytest.raises(UiContractUnattested):
        require_attested("plan_list")


def test_drift_detection() -> None:
    assert_no_drift(load_status().version)
    with pytest.raises(UiDrift):
        assert_no_drift("9.9.9")


def test_capabilities_do_not_use_graph() -> None:
    caps = build_capabilities(license_evidence={"premium_detected": True})
    assert caps["graph_api_used"] is False
    assert caps["capabilities"]
    for row in caps["capabilities"]:
        assert row["support_level"] in {
            "unsupported", "planned", "read_unattested", "read_attested",
            "mutation_attested",
        }
        assert row["ui_contract_status"] == "UNVERIFIED_LIVE"
