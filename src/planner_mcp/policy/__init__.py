"""Fail-closed policy package: ALLOW / DENY / REQUIRE_APPROVAL."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..config import Settings


class Decision(StrEnum):
    """Policy decision values."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


@dataclass(frozen=True)
class PolicyResult:
    """A policy decision plus its reason code."""

    decision: Decision
    reason: str

    @property
    def allowed(self) -> bool:
        return self.decision is Decision.ALLOW


READ_TOOLS = frozenset(
    {
        "planner_health",
        "planner_readiness",
        "planner_capabilities",
        "planner_agent_card",
        "planner_ui_contract_status",
        "planner_auth_status",
        "planner_auth_start",
        "planner_auth_resume",
        "planner_auth_session_info",
        "planner_plan_list",
        "planner_plan_get",
        "planner_task_list",
        "planner_task_get",
        "planner_project_snapshot",
        "planner_account_context",
        "planner_license_capabilities",
        "planner_smoke_test",
    }
)


def evaluate(tool: str, settings: Settings, *, mutation: bool = False) -> PolicyResult:
    """Evaluate a tool invocation. Unknown tools and mutations are denied."""
    if mutation or tool not in READ_TOOLS:
        if not settings.allow_mutations:
            return PolicyResult(Decision.DENY, "MUTATIONS_DISABLED_IN_0_1_0")
        return PolicyResult(Decision.REQUIRE_APPROVAL, "MUTATION_REQUIRES_APPROVAL")
    return PolicyResult(Decision.ALLOW, "READ_ONLY_TOOL")


__all__ = ["Decision", "PolicyResult", "READ_TOOLS", "evaluate"]
