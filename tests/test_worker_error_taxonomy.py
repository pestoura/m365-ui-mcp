"""CORE-030 sanitized worker error taxonomy tests."""

from __future__ import annotations

from fastapi import HTTPException
from fastapi.testclient import TestClient

from m365_browser_worker.protocol import WorkerOperation
from m365_browser_worker.worker_errors import WorkerErrorCode, project_worker_error
from planner_browser_worker.app import create_app
from planner_mcp.errors import PolicyDenied, WorkerBusy


def test_internal_error_text_and_arbitrary_context_never_cross_boundary() -> None:
    secret_url = "https://tenant.example.invalid/private?token=super-secret"
    exc = WorkerBusy(
        f"raw internal failure at {secret_url}",
        token="super-secret",
        selector="#private-selector",
        tenant="contoso-secret",
    )

    status, envelope = project_worker_error(
        exc,
        request_id="req-safe",
        operation=WorkerOperation.PLANNER_TASK_LIST,
    )
    payload = envelope.model_dump_json()

    assert status == 503
    assert envelope.error.code is WorkerErrorCode.WORKER_BUSY
    assert envelope.error.application == "planner"
    assert envelope.error.capability == "tasks.read"
    assert envelope.error.retryable is True
    assert "super-secret" not in payload
    assert "private-selector" not in payload
    assert "contoso-secret" not in payload
    assert secret_url not in payload


def test_policy_mapping_derives_scope_from_closed_operation_not_exception_context() -> None:
    exc = PolicyDenied(
        "unsafe raw explanation",
        application="outlook",
        capability="browser.execute.javascript",
    )
    status, envelope = project_worker_error(
        exc,
        request_id="req-policy",
        operation=WorkerOperation.PLANNER_PROJECT_SNAPSHOT,
    )

    assert status == 403
    assert envelope.error.code is WorkerErrorCode.POLICY_DENIED
    assert envelope.error.application == "planner"
    assert envelope.error.capability == "project_snapshot.read"
    assert "outlook" not in envelope.model_dump_json()
    assert "javascript" not in envelope.model_dump_json()


def test_safe_not_found_code_is_preserved_without_raw_http_detail() -> None:
    exc = HTTPException(
        status_code=404,
        detail={
            "error": "PLAN_NOT_FOUND",
            "message": "tenant/private-plan-id",
            "context": {"url": "https://private.invalid"},
        },
    )
    status, envelope = project_worker_error(
        exc,
        request_id="req-not-found",
        operation=WorkerOperation.PLANNER_PLAN_GET,
    )

    assert status == 404
    assert envelope.error.code is WorkerErrorCode.PLAN_NOT_FOUND
    assert envelope.error.message == "Planner plan was not found"
    payload = envelope.model_dump_json()
    assert "private-plan-id" not in payload
    assert "private.invalid" not in payload


def test_typed_operations_fail_closed_until_protocol_is_negotiated() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/operations",
            json={
                "request_id": "req-protocol",
                "operation": "planner.plan.list",
                "arguments": {"kind": "none"},
            },
        )

    assert response.status_code == 503
    assert response.json() == {
        "schema_version": "1",
        "request_id": "req-protocol",
        "operation": "planner.plan.list",
        "error": {
            "code": "PROTOCOL_INCOMPATIBLE",
            "message": "Control-plane and worker protocol versions are incompatible",
            "retryable": False,
            "application": "planner",
            "capability": "plans.read",
        },
    }


def test_not_found_through_typed_dispatch_is_sanitized() -> None:
    app = create_app()
    with TestClient(app) as client:
        client.post("/protocol/negotiate", json={"supported_versions": ["1"]})
        response = client.post(
            "/operations",
            json={
                "request_id": "req-missing",
                "operation": "planner.plan.get",
                "arguments": {"kind": "plan", "plan_id": "private-plan-reference"},
            },
        )

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "PLAN_NOT_FOUND"
    assert payload["error"]["application"] == "planner"
    assert payload["error"]["capability"] == "plans.read"
    assert "private-plan-reference" not in response.text


def test_validation_errors_do_not_echo_malformed_browser_shaped_input() -> None:
    secret_url = "https://private.invalid/?token=never-echo"
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/operations",
            json={
                "request_id": "req-invalid",
                "operation": "planner.plan.list",
                "arguments": {"kind": "none"},
                "url": secret_url,
            },
        )

    assert response.status_code == 422
    assert response.json() == {
        "error": "INVALID_REQUEST",
        "message": "Request validation failed",
    }
    assert secret_url not in response.text
    assert "never-echo" not in response.text
