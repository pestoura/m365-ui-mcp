"""FastAPI browser worker. Mock mode by default; live mode fails closed."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from m365_browser_worker.account_context import AccountContext, unverified_account_context
from m365_browser_worker.apps.planner import PlannerWorkerAdapter
from m365_browser_worker.executor import ProfileSerializedExecutor
from m365_browser_worker.lifecycle import browser_lifespan
from m365_browser_worker.protocol import (
    WorkerOperation,
    WorkerRequestEnvelope,
    WorkerResponseEnvelope,
)
from m365_browser_worker.protocol_negotiation import (
    ProtocolNegotiationRequest,
    ProtocolNegotiationResponse,
    ProtocolNegotiator,
)
from m365_browser_worker.readiness import WorkerReadiness, evaluate_worker_readiness
from m365_browser_worker.session_broker import SessionCapabilityBroker
from m365_browser_worker.worker_errors import project_worker_error
from m365_mcp.capability_registry import default_capability_registry
from planner_mcp.auth import AuthState
from planner_mcp.errors import PlannerMcpError, ProtocolIncompatible
from planner_mcp.logging_setup import configure_logging
from planner_mcp.ui_contract import load_status

from . import __version__, mock_data
from .browser import BrowserConfig, PersistentBrowser


def _mode() -> str:
    return os.getenv("PLANNER_MODE", "mock").lower()


def _is_mock() -> bool:
    return _mode() != "live"


def create_app(
    browser: PersistentBrowser | None = None,
    *,
    profile_viability_provider: Callable[[], bool] | None = None,
    auth_state_provider: Callable[[], AuthState] | None = None,
    account_context_provider: Callable[[], AccountContext] | None = None,
    broker: SessionCapabilityBroker | None = None,
    executor: ProfileSerializedExecutor | None = None,
    protocol_negotiator: ProtocolNegotiator | None = None,
    broker_viability_provider: Callable[[], bool] | None = None,
    protocol_compatibility_provider: Callable[[], bool] | None = None,
    lock_viability_provider: Callable[[], bool] | None = None,
) -> FastAPI:
    """Build the worker app with separate liveness and live-readiness semantics."""
    configure_logging(os.getenv("PLANNER_LOG_LEVEL", "INFO"))
    worker_browser = browser or PersistentBrowser(BrowserConfig.from_env())
    profile_executor = executor or ProfileSerializedExecutor()
    worker_protocol = protocol_negotiator or ProtocolNegotiator()
    profile_usable = profile_viability_provider or (lambda: False)
    current_auth_state = auth_state_provider or (
        lambda: AuthState.AUTHENTICATED if _is_mock() else AuthState.UNKNOWN
    )
    current_account_context = account_context_provider or unverified_account_context
    session_broker = broker or SessionCapabilityBroker(
        browser=worker_browser,
        registry=default_capability_registry(),
        auth_state_provider=current_auth_state,
        account_context_provider=current_account_context,
    )
    broker_viable = broker_viability_provider or (lambda: session_broker.viable)
    protocol_compatible = protocol_compatibility_provider or (lambda: worker_protocol.compatible)
    lock_viable = lock_viability_provider or (lambda: profile_executor.viable)
    app = FastAPI(
        title="planner-browser-worker",
        version=__version__,
        lifespan=browser_lifespan(worker_browser),
    )
    # Internal ownership only; no generic executor/browser endpoint is exposed.
    app.state.profile_executor = profile_executor
    app.state.protocol_negotiator = worker_protocol

    @app.exception_handler(RequestValidationError)
    async def sanitized_validation_error(
        _request: Request,
        _exc: RequestValidationError,
    ) -> JSONResponse:
        """Never echo malformed request values back across the worker boundary."""
        return JSONResponse(
            status_code=422,
            content={
                "error": "INVALID_REQUEST",
                "message": "Request validation failed",
            },
        )

    def current_readiness() -> WorkerReadiness:
        ui = load_status()
        return evaluate_worker_readiness(
            browser_started=worker_browser.started,
            profile_usable=profile_usable(),
            auth_state=current_auth_state(),
            ui_contract_attested=ui.attested,
            broker_viable=broker_viable(),
            protocol_compatible=protocol_compatible(),
            lock_viable=lock_viable(),
        )

    def live_guard(operation: str) -> None:
        if _is_mock():
            return
        try:
            worker_browser.ensure_live_allowed(operation)
        except PlannerMcpError as exc:
            raise HTTPException(status_code=503, detail=exc.to_dict()) from exc

    def capability_guard(capability: str) -> None:
        if _is_mock():
            return
        try:
            session_broker.authorize(application="planner", capability=capability)
        except PlannerMcpError as exc:
            raise HTTPException(status_code=503, detail=exc.to_dict()) from exc

    planner_adapter = PlannerWorkerAdapter(
        is_mock=_is_mock,
        capability_guard=capability_guard,
        data_provider=mock_data,
    )
    app.state.planner_adapter = planner_adapter

    @app.get("/livez")
    async def livez() -> dict[str, object]:
        return {"alive": True, "version": __version__}

    @app.get("/readyz")
    async def readyz() -> JSONResponse:
        readiness = current_readiness()
        return JSONResponse(
            status_code=200 if readiness.ready else 503,
            content=readiness.to_dict(),
        )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        ui = load_status()
        readiness = current_readiness()
        return {
            "ok": True,
            "mode": _mode(),
            "version": __version__,
            "ui_contract_version": ui.version,
            "ui_contract_set_digest": ui.contract_set_digest,
            "ui_contract_attested": ui.attested,
            "live_ready": readiness.ready,
        }

    @app.get("/protocol")
    async def protocol_status() -> dict[str, object]:
        return worker_protocol.snapshot()

    @app.post("/protocol/negotiate", response_model=ProtocolNegotiationResponse)
    async def protocol_negotiate(
        request: ProtocolNegotiationRequest,
    ) -> ProtocolNegotiationResponse:
        return worker_protocol.negotiate(request.supported_versions)

    @app.get("/auth/status")
    async def auth_status() -> dict[str, Any]:
        if _is_mock():
            return {"state": AuthState.AUTHENTICATED.value, "mode": "mock"}
        live_guard("auth_status")
        return {"state": AuthState.UNKNOWN.value, "mode": "live"}

    @app.get("/auth/start")
    async def auth_start() -> dict[str, Any]:
        if _is_mock():
            expires = (datetime.now(UTC) + timedelta(seconds=120)).isoformat()
            return {
                "state": AuthState.MFA_REQUIRED.value,
                "mfa": {
                    "mfa_number": "42",
                    "operation_id": "mock-op-1",
                    "service": "microsoft-entra-id",
                    "description": "Sign in to Microsoft Planner",
                    "expires_at": expires,
                    "approval_channel": "microsoft_authenticator",
                },
            }
        live_guard("auth_start")
        return {"state": AuthState.UNKNOWN.value}

    @app.get("/auth/resume")
    async def auth_resume() -> dict[str, Any]:
        if _is_mock():
            return {"state": AuthState.AUTHENTICATED.value, "mode": "mock"}
        live_guard("auth_resume")
        return {"state": AuthState.UNKNOWN.value}

    @app.get("/auth/session")
    async def auth_session() -> dict[str, Any]:
        return {
            "profile": "professional-isolated",
            "persistent_profile": True,
            "secrets_stored_in_state": False,
            "mode": _mode(),
            "broker": session_broker.snapshot(),
        }

    @app.get("/account/context")
    async def account_context() -> dict[str, Any]:
        if _is_mock():
            return dict(mock_data.ACCOUNT_CONTEXT)
        live_guard("account_context")
        return current_account_context().to_dict()

    @app.get("/account/license")
    async def account_license() -> dict[str, Any]:
        if _is_mock():
            return dict(mock_data.LICENSE)
        live_guard("account_license")
        return {"premium_detected": False, "evidence": "unattested"}

    @app.get("/planner/plans")
    async def plans() -> dict[str, Any]:
        return await planner_adapter.plan_list()

    @app.get("/planner/plans/{plan_id}")
    async def plan_get(plan_id: str) -> dict[str, Any]:
        return await planner_adapter.plan_get(plan_id)

    @app.get("/planner/tasks")
    async def task_list(plan_id: str) -> dict[str, Any]:
        return await planner_adapter.task_list(plan_id)

    @app.get("/planner/tasks/{task_id}")
    async def task_get(task_id: str) -> dict[str, Any]:
        return await planner_adapter.task_get(task_id)

    @app.get("/planner/plans/{plan_id}/snapshot")
    async def snapshot(plan_id: str) -> dict[str, Any]:
        return await planner_adapter.project_snapshot(plan_id)

    async def dispatch_semantic_operation(request: WorkerRequestEnvelope) -> dict[str, Any]:
        operation = request.operation

        if operation is WorkerOperation.AUTH_STATUS:
            return await auth_status()
        if operation is WorkerOperation.AUTH_START:
            return await auth_start()
        if operation is WorkerOperation.AUTH_RESUME:
            return await auth_resume()
        if operation is WorkerOperation.AUTH_SESSION:
            return await auth_session()
        if operation is WorkerOperation.ACCOUNT_CONTEXT:
            return await account_context()
        if operation is WorkerOperation.ACCOUNT_LICENSE:
            return await account_license()
        if planner_adapter.owns(operation):
            return await planner_adapter.dispatch(request)

        raise HTTPException(status_code=422, detail="unsupported worker operation")

    @app.post("/operations", response_model=WorkerResponseEnvelope)
    async def execute_operation(
        request: WorkerRequestEnvelope,
    ) -> WorkerResponseEnvelope | JSONResponse:
        """Execute one negotiated semantic operation with sanitized typed failures."""
        try:
            if not worker_protocol.compatible:
                raise ProtocolIncompatible("typed worker protocol is not negotiated")
            result = await profile_executor.execute(
                request.operation.value,
                lambda: dispatch_semantic_operation(request),
            )
        except (PlannerMcpError, HTTPException) as exc:
            status_code, envelope = project_worker_error(
                exc,
                request_id=request.request_id,
                operation=request.operation,
            )
            return JSONResponse(
                status_code=status_code,
                content=envelope.model_dump(mode="json"),
            )

        return WorkerResponseEnvelope(
            request_id=request.request_id,
            operation=request.operation,
            result=result,
        )

    return app


app = create_app()
