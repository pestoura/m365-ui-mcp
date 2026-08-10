"""Sanitized synthetic compliance blocker mapping for OUT-129."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ComplianceBlockerCode(StrEnum):
    POLICY_BLOCKED = "POLICY_BLOCKED"
    RETENTION_LOCKED = "RETENTION_LOCKED"
    PERMISSION_REQUIRED = "PERMISSION_REQUIRED"
    SECURITY_POLICY_RESTRICTED = "SECURITY_POLICY_RESTRICTED"
    UNSUPPORTED_TENANT_POLICY = "UNSUPPORTED_TENANT_POLICY"


class ComplianceBlockerCategory(StrEnum):
    POLICY = "POLICY"
    RETENTION = "RETENTION"
    AUTHORIZATION = "AUTHORIZATION"
    SECURITY = "SECURITY"
    CAPABILITY = "CAPABILITY"


@dataclass(frozen=True)
class ComplianceBlockerMapping:
    code: ComplianceBlockerCode
    category: ComplianceBlockerCategory
    retryable: bool
    operator_action: str
    raw_error_exported: bool = False
    synthetic: bool = True
    live_support_state: str = "UNOBSERVED"

    def __post_init__(self) -> None:
        if self.raw_error_exported:
            raise ValueError("raw tenant compliance errors must not be exported")
        if not self.synthetic or self.live_support_state != "UNOBSERVED":
            raise ValueError("compliance mapping must remain synthetic and live-unobserved")
        if not self.operator_action or self.operator_action != self.operator_action.strip():
            raise ValueError("operator_action must be a bounded semantic instruction")

    def to_projection(self) -> dict[str, object]:
        return {
            "code": self.code.value,
            "category": self.category.value,
            "retryable": self.retryable,
            "operator_action": self.operator_action,
            "raw_error_exported": False,
            "synthetic": True,
            "live_support_state": self.live_support_state,
        }


_MAPPINGS = {
    ComplianceBlockerCode.POLICY_BLOCKED: (
        ComplianceBlockerCategory.POLICY,
        False,
        "review-compliance-policy",
    ),
    ComplianceBlockerCode.RETENTION_LOCKED: (
        ComplianceBlockerCategory.RETENTION,
        False,
        "respect-retention-lock",
    ),
    ComplianceBlockerCode.PERMISSION_REQUIRED: (
        ComplianceBlockerCategory.AUTHORIZATION,
        False,
        "request-authorized-scope",
    ),
    ComplianceBlockerCode.SECURITY_POLICY_RESTRICTED: (
        ComplianceBlockerCategory.SECURITY,
        False,
        "review-security-policy",
    ),
    ComplianceBlockerCode.UNSUPPORTED_TENANT_POLICY: (
        ComplianceBlockerCategory.CAPABILITY,
        False,
        "record-unsupported-policy",
    ),
}


def map_compliance_blocker(code: ComplianceBlockerCode) -> ComplianceBlockerMapping:
    """Map a closed blocker code without accepting or exporting raw tenant errors."""
    if not isinstance(code, ComplianceBlockerCode):
        raise ValueError("code must be a closed ComplianceBlockerCode")
    category, retryable, action = _MAPPINGS[code]
    return ComplianceBlockerMapping(
        code=code,
        category=category,
        retryable=retryable,
        operator_action=action,
    )


__all__ = [
    "ComplianceBlockerCategory",
    "ComplianceBlockerCode",
    "ComplianceBlockerMapping",
    "map_compliance_blocker",
]
