import pytest

from m365_mcp.xapp_agentic_budgets import (
    AgenticBudget,
    AgenticBudgetDecision,
    AgenticBudgetUsage,
    assess_agentic_budget,
)


def test_budget_continues_with_numeric_remaining_capacity() -> None:
    assessment = assess_agentic_budget(
        AgenticBudget(max_tokens=1000, max_steps=10, max_runtime_ms=5000),
        AgenticBudgetUsage(tokens_used=400, steps_used=3, runtime_ms=1200),
    )

    assert assessment.decision is AgenticBudgetDecision.CONTINUE
    assert assessment.remaining_tokens == 600
    assert assessment.remaining_steps == 7
    assert assessment.remaining_runtime_ms == 3800
    assert assessment.exhausted_dimensions == ()


def test_exact_limit_or_overrun_is_exhausted_fail_closed() -> None:
    at_limit = assess_agentic_budget(
        AgenticBudget(max_tokens=100, max_steps=5, max_runtime_ms=1000),
        AgenticBudgetUsage(tokens_used=100, steps_used=1, runtime_ms=100),
    )
    overrun = assess_agentic_budget(
        AgenticBudget(max_tokens=100, max_steps=5, max_runtime_ms=1000),
        AgenticBudgetUsage(tokens_used=120, steps_used=9, runtime_ms=2000),
    )

    assert at_limit.decision is AgenticBudgetDecision.EXHAUSTED
    assert at_limit.exhausted_dimensions == ("tokens",)
    assert overrun.decision is AgenticBudgetDecision.EXHAUSTED
    assert overrun.exhausted_dimensions == ("tokens", "steps", "runtime_ms")
    assert overrun.remaining_tokens == 0


def test_budget_rejects_invalid_bounds_and_negative_usage() -> None:
    with pytest.raises(ValueError, match="max_tokens"):
        AgenticBudget(max_tokens=0, max_steps=1, max_runtime_ms=1)

    with pytest.raises(ValueError, match="max_steps"):
        AgenticBudget(max_tokens=1, max_steps=1001, max_runtime_ms=1)

    with pytest.raises(ValueError, match="tokens_used"):
        AgenticBudgetUsage(tokens_used=-1)


def test_budget_models_contain_numeric_fields_only() -> None:
    budget = AgenticBudget(100, 5, 1000)
    usage = AgenticBudgetUsage(10, 1, 50)

    assert budget.__dict__ == {
        "max_tokens": 100,
        "max_steps": 5,
        "max_runtime_ms": 1000,
    }
    assert usage.__dict__ == {
        "tokens_used": 10,
        "steps_used": 1,
        "runtime_ms": 50,
    }
