"""FastAPI browser worker. Mock mode by default; live mode fails closed."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from m365_browser_worker.lifecycle import browser_lifespan
from m365_browser_worker.readiness import WorkerReadiness, evaluate_worker_readiness
from planner_mcp.auth import AuthState
from planner_mcp.errors import PlannerMcpError
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
    broker_viability_provider: Callable[[], bool] | None = None,
    protocol_compatibility_provider: Callable[[], bool] | None = None,
    lock_viability_provider: Callable[[], bool] | None = None,
) -> FastAPI:
    """Build the worker app with separate liveness and live-readiness semantics."""
    configure_logging(os.getenv("PLANNER_LOG_LEVEL", "INFO"))
    worker_browser = browser or PersistentBrowser(BrowserConfig.from_env())
    profile_usable = profile_viability_provider or (lambda: False)
    current_auth_state = auth_state_provider or (
        lambda: AuthState.AUTHENTICATED if _is_mock() else AuthState.UNKNOWN
    )
    broker_viable = broker_viability_provider or (lambda: False)
    protocol_compatible = protocol_compatibility_provider or (lambda: False)
    lock_viable = lock_viability_provider or (lambda: False)
    app = FastAPI(
        title="planner-browser-worker",
        version=__version__,
        lifespan=browser_lifespan(worker_browser),
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
        }

    @app.get("/account/context")
    async def account_context() -> dict[str, Any]:
        if _is_mock():
            return dict(mock_data.ACCOUNT_CONTEXT)
        live_guard("account_context")
        return {}

    @app.get("/account/license")
    async def account_license() -> dict[str, Any]:
        if _is_mock():
            return dict(mock_data.LICENSE)
        live_guard("account_license")
        return {"premium_detected": False, "evidence": "unattested"}

    @app.get("/planner/plans")
    async def plans() -> dict[str, Any]:
        if _is_mock():
            return {"plans": mock_data.PLANS}
        live_guard("plan_list")
        return {"plans": []}

    @app.get("/planner/plans/{plan_id}")
    async def plan_get(plan_id: str) -> dict[str, Any]:
        if not _is_mock():
            live_guard("plan_get")
            return {"plan": None}
        plan = mock_data.plan(plan_id)
        if plan is None:
            raise HTTPException(status_code=404, detail={"error": "PLAN_NOT_FOUND"})
        return {"plan": plan}

    @app.get("/planner/tasks")
    async def task_list(plan_id: str) -> dict[str, Any]:
        if not _is_mock():
            live_guard("task_list")
            return {"tasks": []}
        return {"plan_id": plan_id, "tasks": mock_data.tasks_for(plan_id)}

    @app.get("/planner/tasks/{task_id}")
    async def task_get(task_id: str) -> dict[str, Any]:
        if not _is_mock():
            live_guard("task_get")
            return {"task": None}
        task = mock_data.task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail={"error": "TASK_NOT_FOUND"})
        return {"task": task}

    @app.get("/planner/plans/{plan_id}/snapshot")
    async def snapshot(plan_id: str) -> dict[str, Any]:
        if not _is_mock():
            live_guard("project_snapshot")
            return {"plan": None, "tasks": []}
        plan = mock_data.plan(plan_id)
        if plan is None:
            raise HTTPException(status_code=404, detail={"error": "PLAN_NOT_FOUND"})
        tasks = mock_data.tasks_for(plan_id)
        return {
            "plan": plan,
            "tasks": tasks,
            "buckets": plan.get("buckets", []),
            "counts": {"tasks": len(tasks)},
            "read_only": True,
        }

    return app


app = create_app()
