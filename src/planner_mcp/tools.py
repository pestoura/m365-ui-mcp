"""Implementation of the 17 read-only Foundation 0.1.0 tools."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from . import CONTRACT_VERSION, SCHEMA_VERSION, __version__
from .auth import AuthState
from .capabilities import build_capabilities
from .config import Settings, load_settings
from .contracts import load_contract, version_metadata
from .errors import PlannerMcpError, PolicyDenied
from .metrics import TOOL_CALLS, TOOL_LATENCY, UI_CONTRACT_ATTESTED, WORKER_UP
from .policy import evaluate
from .redaction import redact
from .state import health as sqlite_health
from .state import initialise
from .ui_contract import load_status as ui_status
from .worker_client import WorkerClient

TOOL_NAMES: tuple[str, ...] = (
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
)


def _envelope(tool: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Wrap a tool payload with version metadata and redact it."""
    body = {
        "tool": tool,
        "product_version": __version__,
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "read_only": True,
        "graph_api_used": False,
        "data": payload,
    }
    return dict(redact(body))


async def _guarded(
    tool: str, settings: Settings, fn: Callable[[], Awaitable[dict[str, Any]]]
) -> dict[str, Any]:
    """Apply policy, metrics and typed error handling around a tool body."""
    decision = evaluate(tool, settings)
    if not decision.allowed:
        TOOL_CALLS.labels(tool=tool, outcome="denied").inc()
        return _envelope(tool, PolicyDenied(decision.reason).to_dict())
    started = time.perf_counter()
    try:
        payload = await fn()
        TOOL_CALLS.labels(tool=tool, outcome="ok").inc()
        return _envelope(tool, payload)
    except PlannerMcpError as exc:
        TOOL_CALLS.labels(tool=tool, outcome="error").inc()
        return _envelope(tool, exc.to_dict())
    finally:
        TOOL_LATENCY.labels(tool=tool).observe(time.perf_counter() - started)


class PlannerTools:
    """Callable implementations shared by the MCP server and the tests."""

    def __init__(
        self,
        settings: Settings | None = None,
        worker: WorkerClient | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.worker = worker or WorkerClient(self.settings)

    # ---- system -------------------------------------------------------
    async def planner_health(self) -> dict[str, Any]:
        async def body() -> dict[str, Any]:
            return {
                "status": "ok",
                "mode": self.settings.mode,
                "versions": version_metadata(),
            }

        return await _guarded("planner_health", self.settings, body)

    async def planner_readiness(self) -> dict[str, Any]:
        async def body() -> dict[str, Any]:
            initialise(self.settings.state_path)
            db = sqlite_health(self.settings.state_path)
            ui = ui_status()
            UI_CONTRACT_ATTESTED.set(1 if ui.attested else 0)
            try:
                worker = await self.worker.health()
                worker_ok = bool(worker.get("ok", False))
            except PlannerMcpError as exc:
                worker, worker_ok = exc.to_dict(), False
            WORKER_UP.set(1 if worker_ok else 0)
            ready = bool(db.get("ok")) and worker_ok
            return {
                "ready": ready,
                "configuration": self.settings.public_summary(),
                "sqlite": db,
                "worker": worker,
                "ui_contract": ui.to_dict(),
                "live_reads_blocked": self.settings.is_live and not ui.attested,
            }

        return await _guarded("planner_readiness", self.settings, body)

    async def planner_agent_card(self) -> dict[str, Any]:
        async def body() -> dict[str, Any]:
            return {
                "agent_card": load_contract("agent_card"),
                "tool_manifest": load_contract("tool_manifest"),
                "extended_tool_manifest": load_contract("extended_tool_manifest"),
            }

        return await _guarded("planner_agent_card", self.settings, body)

    async def planner_capabilities(self) -> dict[str, Any]:
        async def body() -> dict[str, Any]:
            try:
                auth_evidence = await self.worker.auth_status()
            except PlannerMcpError as exc:
                auth_evidence = exc.to_dict()
            try:
                account_context = await self.worker.account_context()
            except PlannerMcpError as exc:
                account_context = exc.to_dict()
            try:
                license_evidence = await self.worker.license_capabilities()
            except PlannerMcpError as exc:
                license_evidence = exc.to_dict()
            try:
                runtime = await self.worker.health()
                runtime_ok = bool(runtime.get("ok", False))
            except PlannerMcpError:
                runtime_ok = False

            policy_allowed = evaluate("planner_capabilities", self.settings).allowed
            return build_capabilities(
                auth_evidence=auth_evidence,
                account_context=account_context,
                license_evidence=license_evidence,
                runtime_ok=runtime_ok,
                policy_allowed=policy_allowed,
                live_evidence=self.settings.is_live,
            )

        return await _guarded("planner_capabilities", self.settings, body)

    async def planner_ui_contract_status(self) -> dict[str, Any]:
        async def body() -> dict[str, Any]:
            return ui_status().to_dict()

        return await _guarded("planner_ui_contract_status", self.settings, body)

    # ---- auth ---------------------------------------------------------
    async def planner_auth_status(self) -> dict[str, Any]:
        async def body() -> dict[str, Any]:
            data = await self.worker.auth_status()
            state = str(data.get("state", AuthState.UNKNOWN.value))
            return {"state": state, "detail": data}

        return await _guarded("planner_auth_status", self.settings, body)

    async def planner_auth_start(self) -> dict[str, Any]:
        async def body() -> dict[str, Any]:
            return await self.worker.auth_start()

        return await _guarded("planner_auth_start", self.settings, body)

    async def planner_auth_resume(self) -> dict[str, Any]:
        async def body() -> dict[str, Any]:
            return await self.worker.auth_resume()

        return await _guarded("planner_auth_resume", self.settings, body)

    async def planner_auth_session_info(self) -> dict[str, Any]:
        async def body() -> dict[str, Any]:
            return await self.worker.session_info()

        return await _guarded("planner_auth_session_info", self.settings, body)

    async def planner_account_context(self) -> dict[str, Any]:
        async def body() -> dict[str, Any]:
            return await self.worker.account_context()

        return await _guarded("planner_account_context", self.settings, body)

    async def planner_license_capabilities(self) -> dict[str, Any]:
        async def body() -> dict[str, Any]:
            return await self.worker.license_capabilities()

        return await _guarded("planner_license_capabilities", self.settings, body)

    # ---- planner reads -------------------------------------------------
    async def planner_plan_list(self) -> dict[str, Any]:
        async def body() -> dict[str, Any]:
            return await self.worker.plan_list()

        return await _guarded("planner_plan_list", self.settings, body)

    async def planner_plan_get(self, plan_id: str) -> dict[str, Any]:
        async def body() -> dict[str, Any]:
            return await self.worker.plan_get(plan_id)

        return await _guarded("planner_plan_get", self.settings, body)

    async def planner_task_list(self, plan_id: str) -> dict[str, Any]:
        async def body() -> dict[str, Any]:
            return await self.worker.task_list(plan_id)

        return await _guarded("planner_task_list", self.settings, body)

    async def planner_task_get(self, task_id: str) -> dict[str, Any]:
        async def body() -> dict[str, Any]:
            return await self.worker.task_get(task_id)

        return await _guarded("planner_task_get", self.settings, body)

    async def planner_project_snapshot(self, plan_id: str) -> dict[str, Any]:
        async def body() -> dict[str, Any]:
            return await self.worker.project_snapshot(plan_id)

        return await _guarded("planner_project_snapshot", self.settings, body)

    async def planner_smoke_test(self) -> dict[str, Any]:
        async def body() -> dict[str, Any]:
            steps: list[dict[str, Any]] = []
            readiness = await self.planner_readiness()
            steps.append(
                {"step": "readiness", "ok": bool(readiness["data"].get("ready"))}
            )
            plans = await self.planner_plan_list()
            plan_items = (
                plans["data"].get("plans", []) if isinstance(plans["data"], dict) else []
            )
            steps.append(
                {"step": "plan_list", "ok": bool(plan_items), "count": len(plan_items)}
            )
            if plan_items:
                plan_id = str(plan_items[0].get("id"))
                tasks = await self.planner_task_list(plan_id)
                task_items = (
                    tasks["data"].get("tasks", [])
                    if isinstance(tasks["data"], dict)
                    else []
                )
                steps.append(
                    {"step": "task_list", "ok": bool(task_items), "count": len(task_items)}
                )
                snapshot = await self.planner_project_snapshot(plan_id)
                steps.append(
                    {"step": "project_snapshot", "ok": "plan" in snapshot["data"]}
                )
            return {
                "passed": all(step["ok"] for step in steps),
                "steps": steps,
                "mutations_performed": 0,
            }

        return await _guarded("planner_smoke_test", self.settings, body)
