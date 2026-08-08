"""CORE-028 closed typed worker operation protocol tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from m365_browser_worker.protocol import (
    FORBIDDEN_PROTOCOL_FIELDS,
    NoArguments,
    PlanArguments,
    TaskArguments,
    WorkerOperation,
    WorkerRequestEnvelope,
    WorkerResponseEnvelope,
)
from planner_browser_worker.app import create_app


def test_request_envelope_accepts_only_matching_argument_shape() -> None:
    request = WorkerRequestEnvelope(
        request_id="req-plan-get",
        operation=WorkerOperation.PLANNER_PLAN_GET,
        arguments=PlanArguments(plan_id="plan-alpha"),
    )
    assert request.operation is WorkerOperation.PLANNER_PLAN_GET
    assert isinstance(request.arguments, PlanArguments)

    with pytest.raises(ValidationError, match="operation requires plan arguments"):
        WorkerRequestEnvelope(
            request_id="req-mismatch",
            operation=WorkerOperation.PLANNER_PLAN_GET,
            arguments=TaskArguments(task_id="task-1"),
        )

    with pytest.raises(ValidationError, match="operation requires no arguments"):
        WorkerRequestEnvelope(
            request_id="req-mismatch-empty",
            operation=WorkerOperation.AUTH_STATUS,
            arguments=PlanArguments(plan_id="plan-alpha"),
        )


def test_wire_decode_rejects_unknown_operation_and_extra_browser_fields() -> None:
    app = create_app()
    with TestClient(app) as client:
        unknown = client.post(
            "/operations",
            json={
                "request_id": "req-unknown",
                "operation": "browser.navigate",
                "arguments": {"kind": "none"},
            },
        )
        extra = client.post(
            "/operations",
            json={
                "request_id": "req-extra",
                "operation": "planner.plan.list",
                "arguments": {"kind": "none"},
                "url": "https://example.com/",
            },
        )

    assert unknown.status_code == 422
    assert extra.status_code == 422


def test_protocol_schema_contains_no_generic_browser_primitive_fields() -> None:
    request_schema = WorkerRequestEnvelope.model_json_schema()
    response_schema = WorkerResponseEnvelope.model_json_schema()
    serialized = f"{request_schema} {response_schema}".lower()

    for field in FORBIDDEN_PROTOCOL_FIELDS:
        assert f"'{field}'" not in serialized
        assert f'"{field}"' not in serialized


def test_closed_operation_enum_matches_current_semantic_worker_surface() -> None:
    assert {operation.value for operation in WorkerOperation} == {
        "auth.status",
        "auth.start",
        "auth.resume",
        "auth.session",
        "account.context",
        "account.license",
        "planner.plan.list",
        "planner.plan.get",
        "planner.task.list",
        "planner.task.get",
        "planner.project.snapshot",
    }


def test_typed_dispatch_preserves_mock_planner_semantics() -> None:
    app = create_app()
    with TestClient(app) as client:
        negotiation = client.post(
            "/protocol/negotiate",
            json={"supported_versions": ["1"]},
        )
        response = client.post(
            "/operations",
            json={
                "request_id": "req-plan-get",
                "operation": "planner.plan.get",
                "arguments": {"kind": "plan", "plan_id": "plan-alpha"},
            },
        )
        compatibility = client.get("/planner/plans/plan-alpha")

    assert negotiation.status_code == 200
    assert negotiation.json()["compatible"] is True
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "1"
    assert payload["request_id"] == "req-plan-get"
    assert payload["operation"] == "planner.plan.get"
    assert payload["result"] == compatibility.json()


def test_typed_dispatch_uses_explicit_empty_arguments() -> None:
    request = WorkerRequestEnvelope(
        request_id="req-list",
        operation=WorkerOperation.PLANNER_PLAN_LIST,
        arguments=NoArguments(),
    )
    assert request.arguments.kind == "none"

    app = create_app()
    with TestClient(app) as client:
        client.post("/protocol/negotiate", json={"supported_versions": ["1"]})
        response = client.post("/operations", json=request.model_dump(mode="json"))

    assert response.status_code == 200
    assert response.json()["result"]["plans"]


def test_core_028_does_not_promote_protocol_readiness() -> None:
    app = create_app()
    with TestClient(app) as client:
        readiness = client.get("/readyz")

    assert readiness.status_code == 503
    assert readiness.json()["protocol_compatible"] is False
