"""Content-free agentic token/step/runtime budgets for XAPP-015."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

_MAX_TOKENS = 1_000_000
_MAX_STEPS = 1_000
_MAX_RUNTIME_MS = 86_400_000


class AgenticBudgetDecision(StrEnum):
    CONTINUE = "CONTINUE"
    EXHAUSTED = "EXHAUSTED"


@dataclass(frozen=True)
class AgenticBudget:
    max_tokens: int
    max_steps: int
    max_runtime_ms: int

    def __post_init__(self) -> None:
        limits = (
            ("max_tokens", self.max_tokens, _MAX_TOKENS),
            ("max_steps", self.max_steps, _MAX_STEPS),
            ("max_runtime_ms", self.max_runtime_ms, _MAX_RUNTIME_MS),
        )
        for field_name, value, maximum in limits:
            if not 1 <= value <= maximum:
                raise ValueError(f"{field_name} must be between 1 and {maximum}")


@dataclass(frozen=True)
class AgenticBudgetUsage:
    tokens_used: int = 0
    steps_used: int = 0
    runtime_ms: int = 0

    def __post_init__(self) -> None:
        for field_name in ("tokens_used", "steps_used", "runtime_ms"):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} must be non-negative")


@dataclass(frozen=True)
class AgenticBudgetAssessment:
    decision: AgenticBudgetDecision
    remaining_tokens: int
    remaining_steps: int
    remaining_runtime_ms: int
    exhausted_dimensions: tuple[str, ...]


def assess_agentic_budget(
    budget: AgenticBudget,
    usage: AgenticBudgetUsage,
) -> AgenticBudgetAssessment:
    """Assess numeric usage only; no clock, prompt or tenant content is accepted."""
    remaining = {
        "tokens": max(0, budget.max_tokens - usage.tokens_used),
        "steps": max(0, budget.max_steps - usage.steps_used),
        "runtime_ms": max(0, budget.max_runtime_ms - usage.runtime_ms),
    }
    exhausted = tuple(name for name, value in remaining.items() if value == 0)
    decision = (
        AgenticBudgetDecision.EXHAUSTED
        if exhausted
        else AgenticBudgetDecision.CONTINUE
    )
    return AgenticBudgetAssessment(
        decision=decision,
        remaining_tokens=remaining["tokens"],
        remaining_steps=remaining["steps"],
        remaining_runtime_ms=remaining["runtime_ms"],
        exhausted_dimensions=exhausted,
    )


__all__ = [
    "AgenticBudget",
    "AgenticBudgetAssessment",
    "AgenticBudgetDecision",
    "AgenticBudgetUsage",
    "assess_agentic_budget",
]
