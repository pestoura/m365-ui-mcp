"""Typed DIRECT execution contract for XAPP-001.

This module defines the semantic envelope for one direct operation. It does not
invoke tools, browser primitives, callables, URLs, scripts, or arbitrary payloads.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.application_registry import ApplicationKey

_MAX_REFERENCES = 32


class DirectContractState(StrEnum):
    PREPARED = "PREPARED"
    REJECTED = "REJECTED"


def _token(field: str, value: str) -> None:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{field} must be a non-empty semantic token")
    if "://" in value:
        raise ValueError(f"{field} must not encode a URL")


@dataclass(frozen=True)
class DirectExecutionRequest:
    operation_key: str
    application: ApplicationKey
    tool_name: str
    mutation: bool = False
    input_reference_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _token("operation_key", self.operation_key)
        _token("tool_name", self.tool_name)
        if len(self.input_reference_ids) > _MAX_REFERENCES:
            raise ValueError("DIRECT input references exceed bounded size")
        if len(set(self.input_reference_ids)) != len(self.input_reference_ids):
            raise ValueError("DIRECT input references must be unique")
        for value in self.input_reference_ids:
            _token("input_reference_id", value)

    def to_projection(self) -> dict[str, object]:
        return {
            "operation_key": self.operation_key,
            "application": self.application.value,
            "tool_name": self.tool_name,
            "mutation": self.mutation,
            "input_reference_ids": self.input_reference_ids,
        }


@dataclass(frozen=True)
class DirectExecutionContract:
    request: DirectExecutionRequest
    state: DirectContractState = DirectContractState.PREPARED
    policy_required: bool = True
    evidence_required: bool = True
    generic_executor_available: bool = False

    def __post_init__(self) -> None:
        if self.generic_executor_available:
            raise ValueError("generic DIRECT execution is not available")
        if not self.policy_required or not self.evidence_required:
            raise ValueError("DIRECT contract cannot bypass policy or evidence")

    @property
    def executable(self) -> bool:
        return False

    def to_projection(self) -> dict[str, object]:
        return {
            "request": self.request.to_projection(),
            "state": self.state.value,
            "policy_required": True,
            "evidence_required": True,
            "generic_executor_available": False,
            "executable": False,
        }


def prepare_direct_execution(request: DirectExecutionRequest) -> DirectExecutionContract:
    """Prepare one semantic DIRECT contract; never execute it here."""
    return DirectExecutionContract(request=request)


__all__ = [
    "DirectContractState",
    "DirectExecutionContract",
    "DirectExecutionRequest",
    "prepare_direct_execution",
]
