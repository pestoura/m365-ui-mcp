"""Config and policy tests."""

from __future__ import annotations

from planner_mcp.config import Settings
from planner_mcp.policy import Decision, evaluate


def test_defaults_are_fail_closed() -> None:
    settings = Settings()
    assert settings.allow_mutations is False
    assert settings.require_ui_contract_attestation is True


def test_read_tools_allowed() -> None:
    settings = Settings()
    assert evaluate("planner_plan_list", settings).decision is Decision.ALLOW


def test_unknown_tool_denied() -> None:
    settings = Settings()
    assert evaluate("planner_task_create", settings).decision is Decision.DENY


def test_mutation_denied_in_0_1_0() -> None:
    settings = Settings()
    result = evaluate("planner_plan_list", settings, mutation=True)
    assert result.decision is Decision.DENY
    assert result.reason == "MUTATIONS_DISABLED_IN_0_1_0"
