from __future__ import annotations

import json
from pathlib import Path

from m365_mcp.apps.outlook.discovery import default_outlook_discovery_candidates

_CONTRACTS = Path("contracts")
_SET_PATH = _CONTRACTS / "ui_contract_set.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_outlook_fragments_cover_discovery_candidates_without_live_claims() -> None:
    contract_set = _load(_SET_PATH)
    entries = contract_set["fragments"]
    assert isinstance(entries, list)

    outlook_paths = [
        _CONTRACTS / entry["path"]
        for entry in entries
        if isinstance(entry, dict)
        and str(entry.get("fragment_id", "")).startswith("outlook.")
    ]
    assert len(outlook_paths) == 6

    capability_keys: set[str] = set()
    for path in outlook_paths:
        fragment = _load(path)
        assert fragment["application"] == "outlook"
        assert fragment["attested"] is False
        assert fragment["attestation_status"] == "UNVERIFIED_LIVE"

        raw_capabilities = fragment["capability_keys"]
        assert isinstance(raw_capabilities, list)
        capability_keys.update(str(item) for item in raw_capabilities)

        selectors = fragment["selectors"]
        assert isinstance(selectors, dict)
        assert selectors
        for locator in selectors.values():
            assert isinstance(locator, dict)
            assert locator["value"] is None
            assert locator["status"] == "UNVERIFIED_LIVE"

    expected = {
        candidate.capability_key
        for candidate in default_outlook_discovery_candidates()
    }
    assert capability_keys == expected


def test_outlook_contract_set_version_advances_without_legacy_change() -> None:
    contract_set = _load(_SET_PATH)
    assert contract_set["ui_contract_set_version"] == "0.2.0"
    assert contract_set["legacy_ui_contract_version"] == "0.1.0"
