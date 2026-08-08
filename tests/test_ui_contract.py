"""Tests for UIContract loading, attestation and fail-closed selector handling."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from planner_mcp.ui_contract import (
    Attestation,
    Selector,
    UIContractError,
    UnattestedSelectorError,
    load_contract,
    require_usable,
)

REPO = Path(__file__).resolve().parents[1]
GOOD_HASH = "sha256:" + "a" * 64


def _attestation() -> Attestation:
    return Attestation(
        captured_at="2026-01-01",
        evidence_hash=GOOD_HASH,
        evidence_ref="evidence/ui/example.json",
        observer="operator",
    )


def test_unattested_selector_is_not_usable() -> None:
    selector = Selector(id="plan.list.container", description="x", role="list", name="Plans")
    assert selector.is_addressable() is True
    assert selector.is_attested() is False
    assert selector.is_usable() is False


def test_attested_selector_is_usable() -> None:
    selector = Selector(
        id="plan.list.container",
        description="x",
        role="list",
        name="Plans",
        attestation=_attestation(),
    )
    assert selector.is_usable() is True
    assert require_usable(selector) is selector


def test_require_usable_fails_closed() -> None:
    selector = Selector(id="plan.list.container", description="x", role="list")
    with pytest.raises(UnattestedSelectorError):
        require_usable(selector)


def test_attested_but_unaddressable_selector_fails_closed() -> None:
    selector = Selector(id="plan.list.container", description="x", attestation=_attestation())
    with pytest.raises(UnattestedSelectorError):
        require_usable(selector)


def test_invalid_attestation_is_rejected() -> None:
    with pytest.raises(UIContractError):
        Attestation(
            captured_at="01-01-2026",
            evidence_hash=GOOD_HASH,
            evidence_ref="e",
            observer="operator",
        )
    with pytest.raises(UIContractError):
        Attestation(
            captured_at="2026-01-01",
            evidence_hash="md5:abc",
            evidence_ref="e",
            observer="operator",
        )


def test_invalid_selector_id_is_rejected() -> None:
    with pytest.raises(UIContractError):
        Selector(id="PlanList", description="x", role="list")


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(UIContractError):
        load_contract({"version": "0.1.0", "surface": "s", "selectors": [], "extra": 1})


def test_coverage_and_unattested_reporting() -> None:
    contract = load_contract(
        {
            "version": "0.1.0",
            "surface": "planner-premium",
            "selectors": [
                {
                    "id": "plan.list.container",
                    "description": "x",
                    "role": "list",
                    "attestation": {
                        "captured_at": "2026-01-01",
                        "evidence_hash": GOOD_HASH,
                        "evidence_ref": "evidence/ui/example.json",
                        "observer": "operator",
                    },
                },
                {"id": "plan.list.item", "description": "y", "role": "listitem"},
            ],
        },
    )
    assert contract.coverage() == 0.5
    assert [s.id for s in contract.unattested()] == ["plan.list.item"]
    assert contract.get("plan.list.container").is_usable() is True


def test_missing_selector_fails_closed() -> None:
    contract = load_contract({"version": "0.1.0", "surface": "s", "selectors": []})
    with pytest.raises(UnattestedSelectorError):
        contract.get("plan.list.container")


def test_repository_contracts_parse_and_are_fully_attested() -> None:
    files = sorted((REPO / "browser" / "selectors").glob("*.yaml"))
    assert files, "no UIContract documents found"
    for path in files:
        contract = load_contract(yaml.safe_load(path.read_text(encoding="utf-8")))
        assert contract.unusable() == (), f"{path.name} contains unusable selectors"
