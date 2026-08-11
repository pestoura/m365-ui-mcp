from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest

from planner_mcp.errors import UiContractUnattested, WorkerUnavailable
from planner_mcp.worker_client import WorkerClient, _typed_worker_error


def _response(status: int, payload: object) -> httpx.Response:
    request = httpx.Request("GET", "http://browser-worker:8090/auth/status")
    return httpx.Response(status, json=payload, request=request)


def test_typed_worker_error_preserves_closed_legacy_code_only() -> None:
    response = _response(
        503,
        {
            "detail": {
                "error": "UI_CONTRACT_UNATTESTED",
                "message": "do not reflect this worker supplied message",
                "context": {"secret_like_value": "must-not-cross-boundary"},
            }
        },
    )

    error = _typed_worker_error(response, path="/auth/status")

    assert isinstance(error, UiContractUnattested)
    assert error.to_dict() == {
        "error": "UI_CONTRACT_UNATTESTED",
        "message": "Required UI contract is not attested",
        "context": {"path": "/auth/status"},
    }


def test_typed_worker_error_accepts_sanitized_operations_envelope() -> None:
    response = _response(
        503,
        {
            "schema_version": "1",
            "request_id": "request-1",
            "operation": "auth_status",
            "error": {
                "code": "UI_CONTRACT_UNATTESTED",
                "message": "Required UI contract is not attested",
                "retryable": False,
            },
        },
    )

    error = _typed_worker_error(response, path="/operations")

    assert isinstance(error, UiContractUnattested)
    assert error.context == {"path": "/operations"}


def test_unknown_worker_http_error_is_not_reprojected() -> None:
    response = _response(503, {"detail": {"error": "UNRECOGNIZED_WORKER_ERROR"}})

    assert _typed_worker_error(response, path="/auth/status") is None


@pytest.mark.asyncio
async def test_worker_client_raises_typed_error_for_known_http_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _response(
        503,
        {"detail": {"error": "UI_CONTRACT_UNATTESTED", "message": "ignored"}},
    )

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(
            self,
            _url: str,
            *,
            params: dict[str, Any] | None = None,
        ) -> httpx.Response:
            assert params is None
            return response

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    settings = cast(
        Any,
        SimpleNamespace(worker_base_url="http://browser-worker:8090", request_timeout_s=5.0),
    )

    with pytest.raises(UiContractUnattested) as captured:
        await WorkerClient(settings).auth_status()

    assert captured.value.context == {"path": "/auth/status"}


@pytest.mark.asyncio
async def test_worker_client_keeps_transport_failure_generic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = httpx.Request("GET", "http://browser-worker:8090/auth/status")

    class FailingAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> FailingAsyncClient:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(
            self,
            _url: str,
            *,
            params: dict[str, Any] | None = None,
        ) -> httpx.Response:
            del params
            raise httpx.ConnectError("transport unavailable", request=request)

    monkeypatch.setattr(httpx, "AsyncClient", FailingAsyncClient)
    settings = cast(
        Any,
        SimpleNamespace(worker_base_url="http://browser-worker:8090", request_timeout_s=5.0),
    )

    with pytest.raises(WorkerUnavailable) as captured:
        await WorkerClient(settings).auth_status()

    assert captured.value.to_dict() == {
        "error": "WORKER_UNAVAILABLE",
        "message": "browser worker request failed",
        "context": {"path": "/auth/status", "error": "ConnectError"},
    }
