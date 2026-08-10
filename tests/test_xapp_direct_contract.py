from __future__ import annotations

import pytest

from m365_mcp.application_registry import ApplicationKey
from m365_mcp.xapp_direct_contract import (
    DirectContractState,
    DirectExecutionRequest,
    prepare_direct_execution,
)


def test_direct_contract_is_semantic_policy_bound_and_non_executing() -> None:
    request = DirectExecutionRequest(
        operation_key="op-001",
        application=ApplicationKey.PLANNER,
        tool_name="planner.list_tasks",
        input_reference_ids=("ref-001",),
    )
    contract = prepare_direct_execution(request)
    projection = contract.to_projection()
    assert contract.state is DirectContractState.PREPARED
    assert contract.executable is False
    assert projection["policy_required"] is True
    assert projection["evidence_required"] is True
    assert projection["generic_executor_available"] is False
    assert not {"url", "selector", "script", "callable", "payload"} & set(projection)


def test_direct_request_fails_closed_for_unsafe_or_duplicate_references() -> None:
    with pytest.raises(ValueError, match="must not encode a URL"):
        DirectExecutionRequest(
            operation_key="https://unsafe.example",
            application=ApplicationKey.PLANNER,
            tool_name="planner.list_tasks",
        )
    with pytest.raises(ValueError, match="must be unique"):
        DirectExecutionRequest(
            operation_key="op-002",
            application=ApplicationKey.OUTLOOK,
            tool_name="outlook.synthetic",
            input_reference_ids=("ref-1", "ref-1"),
        )
