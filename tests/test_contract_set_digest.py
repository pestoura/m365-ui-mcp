"""CORE-015 deterministic UI contract-set digest acceptance tests."""

from __future__ import annotations

import re

from m365_mcp.ui_contract_projection import project_ui_contract_set
from m365_mcp.ui_contract_store import UIContractFragment, UIContractSet, load_ui_contract_set
from planner_mcp.ui_contract import load_status


def _fragment(
    fragment_id: str,
    *,
    selector_status: str = "UNVERIFIED_LIVE",
) -> UIContractFragment:
    return UIContractFragment(
        fragment_id=fragment_id,
        fragment_version="0.1.0",
        scope="surface",
        application="planner",
        surface="planner-premium-web",
        capability_keys=("plans.read",),
        attested=False,
        attestation_status="UNVERIFIED_LIVE",
        selectors={
            "plan.title": {
                "status": selector_status,
                "value": None,
            }
        },
    )


def test_loaded_contract_set_digest_is_stable_and_well_formed() -> None:
    first = load_ui_contract_set().digest()
    second = load_ui_contract_set().digest()
    assert first == second
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", first)


def test_json_mapping_key_order_does_not_change_digest() -> None:
    first_fragment = _fragment("planner.plan-surface")
    second_fragment = UIContractFragment(
        fragment_id="planner.plan-surface",
        fragment_version="0.1.0",
        scope="surface",
        application="planner",
        surface="planner-premium-web",
        capability_keys=("plans.read",),
        attested=False,
        attestation_status="UNVERIFIED_LIVE",
        selectors={"plan.title": {"value": None, "status": "UNVERIFIED_LIVE"}},
    )
    first = UIContractSet("0.1.0", "0.1.0", (first_fragment,))
    second = UIContractSet("0.1.0", "0.1.0", (second_fragment,))
    assert first.digest() == second.digest()


def test_contract_content_or_manifest_order_changes_digest() -> None:
    first = _fragment("one")
    second = _fragment("two")
    changed = _fragment("one", selector_status="DRIFTED")

    baseline = UIContractSet("0.1.0", "0.1.0", (first, second)).digest()
    reordered = UIContractSet("0.1.0", "0.1.0", (second, first)).digest()
    modified = UIContractSet("0.1.0", "0.1.0", (changed, second)).digest()

    assert reordered != baseline
    assert modified != baseline


def test_digest_payload_contains_no_runtime_identity_fields() -> None:
    payload = str(load_ui_contract_set().canonical_payload()).lower()
    for forbidden in (
        "tenant_id",
        "account_id",
        "user_identifier",
        "session_id",
        "cookie",
        "access_token",
        "refresh_token",
        "timestamp",
        "absolute_path",
    ):
        assert forbidden not in payload


def test_planner_status_exposes_exact_planner_projection_digest() -> None:
    expected = project_ui_contract_set(load_ui_contract_set(), "planner").digest()
    status = load_status()
    assert status.contract_set_digest == expected
    assert status.to_dict()["ui_contract_set_digest"] == expected
