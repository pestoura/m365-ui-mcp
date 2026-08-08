"""CORE-016 locator strategy abstraction acceptance tests."""

from __future__ import annotations

import pytest

from m365_browser_worker.locators import LocatorStrategy as WorkerLocatorStrategy
from m365_mcp.locators import (
    LocatorCandidate,
    LocatorPlan,
    LocatorStrategy,
    locator_plan_from_metadata,
)
from m365_mcp.ui_contract_store import load_ui_contract_set


EVIDENCE = "sha256:" + "a" * 64


def test_accessible_semantics_are_prioritized_over_fallbacks() -> None:
    plan = LocatorPlan(
        selector_key="task.title",
        candidates=(
            LocatorCandidate(LocatorStrategy.CSS, "[data-task-title]", evidence_digest=EVIDENCE),
            LocatorCandidate(LocatorStrategy.PLACEHOLDER, "Task title"),
            LocatorCandidate(LocatorStrategy.LABEL, "Title"),
            LocatorCandidate(LocatorStrategy.ROLE, "textbox", name="Task title"),
        ),
    )
    assert tuple(item.strategy for item in plan.ordered_candidates()) == (
        LocatorStrategy.ROLE,
        LocatorStrategy.LABEL,
        LocatorStrategy.PLACEHOLDER,
        LocatorStrategy.CSS,
    )
    assert plan.primary.strategy is LocatorStrategy.ROLE


def test_fallback_selector_requires_attested_evidence_digest() -> None:
    with pytest.raises(ValueError, match="requires sha256 evidence digest"):
        LocatorCandidate(LocatorStrategy.CSS, "[data-plan-id]")
    with pytest.raises(ValueError, match="requires sha256 evidence digest"):
        LocatorCandidate(LocatorStrategy.TEST_ID, "plan-card", evidence_digest="unverified")


def test_xpath_and_javascript_are_not_valid_css_fallbacks() -> None:
    for value in ("xpath=//button", "//button", "a[href='javascript:void(0)']"):
        with pytest.raises(ValueError, match="unsafe locator primitive"):
            LocatorCandidate(LocatorStrategy.CSS, value, evidence_digest=EVIDENCE)


def test_locator_metadata_schema_is_closed() -> None:
    with pytest.raises(ValueError, match="unsupported locator strategy"):
        locator_plan_from_metadata(
            "plan.title",
            {"locators": [{"strategy": "xpath", "value": "//h1"}]},
        )
    with pytest.raises(ValueError, match="unknown fields"):
        locator_plan_from_metadata(
            "plan.title",
            {
                "locators": [
                    {"strategy": "label", "value": "Plan", "script": "click()"}
                ]
            },
        )


def test_structured_metadata_is_deterministic_and_worker_uses_same_model() -> None:
    plan = locator_plan_from_metadata(
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
    assert plan.primary.strategy is LocatorStrategy.ROLE
    assert WorkerLocatorStrategy is LocatorStrategy


def test_shipped_contract_does_not_invent_live_locators() -> None:
    contract_set = load_ui_contract_set()
    assert all(
        "locators" not in metadata
        for fragment in contract_set.fragments
        for metadata in fragment.selectors.values()
    )
