"""CORE-013 fragmented UIContract storage acceptance tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from m365_mcp.contracts import contracts_dir
from m365_mcp.ui_contract_projection import project_ui_contract_set
from m365_mcp.ui_contract_store import load_ui_contract_set
from planner_mcp.ui_contract import load_status


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _planner_contract_set():
    return project_ui_contract_set(load_ui_contract_set(), "planner")


_AUTH_SELECTORS = {
    "auth.login_email_input",
    "auth.login_next_button",
    "auth.login_password_input",
    "auth.login_signin_button",
}


def test_fragment_set_preserves_legacy_selector_surface_and_order() -> None:
    contract_set = _planner_contract_set()
    legacy = json.loads((contracts_dir() / "ui_contract.json").read_text(encoding="utf-8"))
    selectors = contract_set.selectors()

    assert contract_set.legacy_version == legacy["ui_contract_version"]
    # The Foundation UIContract (contracts/ui_contract.json) is the canonical
    # fail-closed baseline and MUST stay UNVERIFIED_LIVE (check_contracts.py
    # enforces attested=False / UNVERIFIED_LIVE for every selector). The atomic
    # common.auth fragments are promoted to ATTESTED by explicit evidence-backed
    # PR promotion, so the fragmented view legitimately diverges from the
    # Foundation baseline on the four auth selectors. Everything else must remain
    # byte-identical: same selector names (manifest order) and identical
    # value/status for every non-auth selector.
    assert set(selectors) == set(legacy["selectors"])
    for name in selectors:
        if name in _AUTH_SELECTORS:
            # Promoted: attested in the fragmented view, value never live-derived.
            assert selectors[name]["status"] == "ATTESTED", name
            assert selectors[name]["value"] is None, name
        else:
            # Unchanged: identical to the Foundation baseline.
            assert selectors[name] == legacy["selectors"][name], name
    assert len(contract_set.fragments) == 5
    assert tuple(fragment.fragment_id for fragment in contract_set.fragments) == (
        "common.auth.email",
        "common.auth.password",
        "planner.plan-surface",
        "planner.task-surface",
        "planner.account",
    )


def test_fragments_cover_common_application_and_surface_scopes() -> None:
    contract_set = _planner_contract_set()
    assert {fragment.scope for fragment in contract_set.fragments} == {
        "common",
        "application",
        "surface",
    }
    # 4 common.auth selectors (split across two atomic fragments) + 8 planner.
    assert sum(len(fragment.selectors) for fragment in contract_set.fragments) == 12


def test_planner_status_remains_fail_closed_and_compatible() -> None:
    status = load_status()
    legacy = json.loads((contracts_dir() / "ui_contract.json").read_text(encoding="utf-8"))
    assert status.version == "0.1.0"
    assert status.selector_count == 12
    # The aggregate ``load_status`` still reports unattested because the Planner
    # fragments remain UNVERIFIED (full attestation requires them too). But the
    # promoted common.auth fragments are no longer in the unverified set: the
    # auth selectors have been removed from ``unverified_selectors`` while the 8
    # planner selectors remain. This proves the promotion is reflected in the
    # aggregate view without weakening the planner-attestation gate.
    assert status.attested is False
    assert status.attestation_status == "UNVERIFIED_LIVE"
    assert status.unverified_selectors == tuple(
        name for name in legacy["selectors"] if name not in _AUTH_SELECTORS
    )


def test_duplicate_selector_across_fragments_fails_closed(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "ui_contract_set.json",
        {
            "ui_contract_set_version": "0.1.0",
            "legacy_ui_contract_version": "0.1.0",
            "fragments": [
                {"fragment_id": "one", "path": "ui_fragments/one.json"},
                {"fragment_id": "two", "path": "ui_fragments/two.json"},
            ],
        },
    )
    fragment = {
        "fragment_version": "0.1.0",
        "scope": "common",
        "application": None,
        "surface": None,
        "attested": False,
        "attestation_status": "UNVERIFIED_LIVE",
        "selectors": {"shared.selector": {"value": None, "status": "UNVERIFIED_LIVE"}},
    }
    _write_json(tmp_path / "ui_fragments/one.json", {**fragment, "fragment_id": "one"})
    _write_json(tmp_path / "ui_fragments/two.json", {**fragment, "fragment_id": "two"})

    with pytest.raises(ValueError, match="duplicate UIContract selector"):
        load_ui_contract_set(tmp_path)


def test_fragment_path_escape_fails_closed(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "ui_contract_set.json",
        {
            "ui_contract_set_version": "0.1.0",
            "legacy_ui_contract_version": "0.1.0",
            "fragments": [{"fragment_id": "escape", "path": "../escape.json"}],
        },
    )
    with pytest.raises(ValueError, match="inside contracts directory"):
        load_ui_contract_set(tmp_path)
