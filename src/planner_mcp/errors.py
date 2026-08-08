"""Typed fail-closed error taxonomy."""

from __future__ import annotations


class PlannerMcpError(Exception):
    """Base error carrying a stable machine-readable code."""

    code = "PLANNER_MCP_ERROR"

    def __init__(self, message: str = "", **context: object) -> None:
        super().__init__(message or self.code)
        self.message = message or self.code
        self.context = context

    def to_dict(self) -> dict[str, object]:
        return {"error": self.code, "message": self.message, "context": self.context}


class BlockerConditionalAccess(PlannerMcpError):
    """Conditional Access requires a managed/compliant device. Never bypass."""

    code = "BLOCKER_CONDITIONAL_ACCESS"


class UiContractUnattested(PlannerMcpError):
    code = "UI_CONTRACT_UNATTESTED"


class UiDrift(PlannerMcpError):
    code = "UI_DRIFT"


class PolicyDenied(PlannerMcpError):
    code = "POLICY_DENIED"


class ApprovalRequired(PlannerMcpError):
    code = "APPROVAL_REQUIRED"


class WorkerUnavailable(PlannerMcpError):
    code = "WORKER_UNAVAILABLE"


class AuthRequired(PlannerMcpError):
    code = "AUTH_REQUIRED"
