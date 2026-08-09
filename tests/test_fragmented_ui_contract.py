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


def test_fragment_set_preserves_legacy_selector_surface_and_order() -> None:
    contract_set = _planner_contract_set()
    legacy = json.loads((contracts_dir() / "ui_contract.json").read_text(encoding="utf-8"))
    selectors = contract_set.selectors()

    assert contract_set.legacy_version == legacy["ui_contract_version"]
    assert selectors == legacy["selectors"]
    assert tuple(selectors) == tuple(legacy["selectors"])
    assert len(contract_set.fragments) == 4
    assert tuple(fragment.fragment_id for fragment in contract_set.fragments) == (
        "common.auth",
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
    assert sum(len(fragment.selectors) for fragment in contract_set.fragments) == 10


def test_planner_status_remains_fail_closed_and_compatible() -> None:
    status = load_status()
    legacy = json.loads((contracts_dir() / "ui_contract.json").read_text(encoding="utf-8"))
    assert status.version == "0.1.0"
    assert status.selector_count == 10
    assert status.attested is False
    assert status.attestation_status == "UNVERIFIED_LIVE"
    assert status.unverified_selectors == tuple(legacy["selectors"])


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
