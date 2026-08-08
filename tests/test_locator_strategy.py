"""CORE-016 locator strategy abstraction acceptance tests."""

from __future__ import annotations

import importlib


pytest = importlib.import_module("pytest")
json = importlib.import_module("json")
locators = importlib.import_module("m365_mcp.locators")
worker_locators = importlib.import_module("m365_browser_worker.locators")
ui_contract_store = importlib.import_module("m365_mcp.ui_contract_store")

EVIDENCE = "sha256:" + "a" * 64


def test_accessible_semantics_are_prioritized_over_fallbacks() -> None:
    plan = locators.LocatorPlan(
        selector_key="task.title",
        candidates=(
            locators.LocatorCandidate(
                locators.LocatorStrategy.CSS,
                "[data-task-title]",
                evidence_digest=EVIDENCE,
            ),
            locators.LocatorCandidate(locators.LocatorStrategy.PLACEHOLDER, "Task title"),
            locators.LocatorCandidate(locators.LocatorStrategy.LABEL, "Title"),
            locators.LocatorCandidate(
                locators.LocatorStrategy.ROLE,
                "textbox",
                name="Task title",
            ),
        ),
    )
    assert tuple(item.strategy for item in plan.ordered_candidates()) == (
        locators.LocatorStrategy.ROLE,
        locators.LocatorStrategy.LABEL,
        locators.LocatorStrategy.PLACEHOLDER,
        locators.LocatorStrategy.CSS,
    )
    assert plan.primary.strategy is locators.LocatorStrategy.ROLE


def test_fallback_selector_requires_attested_evidence_digest() -> None:
    with pytest.raises(ValueError, match="requires sha256 evidence digest"):
        locators.LocatorCandidate(locators.LocatorStrategy.CSS, "[data-plan-id]")
    with pytest.raises(ValueError, match="requires sha256 evidence digest"):
        locators.LocatorCandidate(
            locators.LocatorStrategy.TEST_ID,
            "plan-card",
            evidence_digest="unverified",
        )


def test_xpath_and_javascript_are_not_valid_css_fallbacks() -> None:
    for value in ("xpath=//button", "//button", "a[href='javascript:void(0)']"):
        with pytest.raises(ValueError, match="unsafe locator primitive"):
            locators.LocatorCandidate(
                locators.LocatorStrategy.CSS,
                value,
                evidence_digest=EVIDENCE,
            )


def test_locator_metadata_schema_is_closed() -> None:
    with pytest.raises(ValueError, match="unsupported locator strategy"):
        locators.locator_plan_from_metadata(
            "plan.title",
            {"locators": [{"strategy": "xpath", "value": "//h1"}]},
        )
    with pytest.raises(ValueError, match="unknown fields"):
        locators.locator_plan_from_metadata(
            "plan.title",
            {
                "locators": [
                    {"strategy": "label", "value": "Plan", "script": "click()"}
                ]
            },
        )


def test_structured_metadata_is_deterministic_and_worker_uses_same_model() -> None:
    plan = locators.locator_plan_from_metadata(
        "plan.title",
        {
            "locators": [
                {
                    "strategy": "css",
                    "value": "[data-plan-title]",
                    "evidence_digest": EVIDENCE,
                },
                {"strategy": "role", "value": "heading", "name": "Plan title"},
            ]
        },
    )
    assert plan is not None
    assert plan.primary.strategy is locators.LocatorStrategy.ROLE
    assert worker_locators.LocatorStrategy is locators.LocatorStrategy


def test_shipped_contract_does_not_invent_live_locators() -> None:
    contract_set = ui_contract_store.load_ui_contract_set()
    assert all(
        "locators" not in metadata
        for fragment in contract_set.fragments
        for metadata in fragment.selectors.values()
    )


def test_ui_contract_loader_rejects_fallback_without_evidence(tmp_path) -> None:
    manifest = {
        "ui_contract_set_version": "0.1.0",
        "legacy_ui_contract_version": "0.1.0",
        "fragments": [
            {"fragment_id": "common.test", "path": "ui_fragments/common/test.json"}
        ],
    }
    fragment = {
        "fragment_id": "common.test",
        "fragment_version": "0.1.0",
        "scope": "common",
        "application": None,
        "surface": None,
        "capability_keys": [],
        "attested": False,
        "attestation_status": "UNVERIFIED_LIVE",
        "selectors": {
            "test.selector": {
                "value": None,
                "status": "UNVERIFIED_LIVE",
                "locators": [{"strategy": "css", "value": "[data-test]"}],
            }
        },
    }
    fragment_path = tmp_path / "ui_fragments" / "common" / "test.json"
    fragment_path.parent.mkdir(parents=True)
    (tmp_path / "ui_contract_set.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    fragment_path.write_text(json.dumps(fragment), encoding="utf-8")

    with pytest.raises(ValueError, match="requires sha256 evidence digest"):
        ui_contract_store.load_ui_contract_set(tmp_path)
