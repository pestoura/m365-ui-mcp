"""Regenerate the frozen Planner mock-parity baseline deterministically.

Uses the in-process ASGI app (mock mode) exactly like the parity suite, so the
newly produced baseline matches what the tests collect. Run from the repo root:

    python scripts/regenerate_mock_parity_baseline.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import httpx

from m365_mcp.apps.planner.mock_parity import parity_digest, parity_snapshot
from m365_mcp.apps.planner.public_surface import PLANNER_PUBLIC_TOOL_NAMES
from planner_browser_worker.app import create_app
from planner_mcp.config import Settings
from planner_mcp.tools import PlannerTools
from planner_mcp.worker_client import WorkerClient

BASELINE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "data"
    / "planner_mock_parity_baseline.json"
)


class _InProcessWorkerClient(WorkerClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._transport = httpx.ASGITransport(app=create_app())

    async def _get(self, path, params=None):
        async with httpx.AsyncClient(
            transport=self._transport, base_url="http://worker"
        ) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()


async def _collect(tools: PlannerTools) -> dict[str, dict[str, object]]:
    # Emit tools in canonical PLANNER_PUBLIC_TOOL_NAMES order (not call order),
    # matching the parity baseline contract.
    plan_id = "plan-alpha"
    task_id = "task-1"
    plans = (await tools.planner_plan_list())["data"]["plans"]
    if plans:
        plan_id = str(plans[0]["id"])
        tasks = (await tools.planner_task_list(plan_id))["data"]["tasks"]
        if tasks:
            task_id = str(tasks[0]["id"])

    collected: dict[str, dict[str, object]] = {}
    for name in PLANNER_PUBLIC_TOOL_NAMES:
        if name == "planner_plan_list":
            collected[name] = await tools.planner_plan_list()
        elif name == "planner_plan_get":
            collected[name] = await tools.planner_plan_get(plan_id)
        elif name == "planner_task_list":
            collected[name] = await tools.planner_task_list(plan_id)
        elif name == "planner_task_get":
            collected[name] = await tools.planner_task_get(task_id)
        elif name == "planner_project_snapshot":
            collected[name] = await tools.planner_project_snapshot(plan_id)
        elif name == "planner_capabilities":
            collected[name] = await tools.planner_capabilities()
        elif name == "planner_health":
            collected[name] = await tools.planner_health()
        elif name == "planner_readiness":
            collected[name] = await tools.planner_readiness()
        elif name == "planner_agent_card":
            collected[name] = await tools.planner_agent_card()
        elif name == "planner_ui_contract_status":
            collected[name] = await tools.planner_ui_contract_status()
        elif name == "planner_auth_status":
            collected[name] = await tools.planner_auth_status()
        elif name == "planner_auth_start":
            collected[name] = await tools.planner_auth_start()
        elif name == "planner_auth_resume":
            collected[name] = await tools.planner_auth_resume()
        elif name == "planner_auth_session_info":
            collected[name] = await tools.planner_auth_session_info()
        elif name == "planner_account_context":
            collected[name] = await tools.planner_account_context()
        elif name == "planner_license_capabilities":
            collected[name] = await tools.planner_license_capabilities()
        elif name == "planner_smoke_test":
            collected[name] = await tools.planner_smoke_test()
        else:
            raise AssertionError(f"unhandled public tool {name}")
    return collected


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        state_path = Path(tmp) / "regenerate-parity-state.json"
        settings = Settings(mode="mock", state_path=state_path)
        tools = PlannerTools(settings, _InProcessWorkerClient(settings))
        results = await _collect(tools)
        snapshot = parity_snapshot(results)
        # Restore canonical PLANNER_PUBLIC_TOOL_NAMES ordering (normalize sorts
        # keys alphabetically); the parity contract compares against this exact
        # order.
        ordered = {name: snapshot[name] for name in PLANNER_PUBLIC_TOOL_NAMES}
        baseline = {
            "mode": "mock",
            "live_support_claimed": False,
            "tools": ordered,
            "digest": parity_digest(ordered),
        }
        BASELINE_PATH.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {BASELINE_PATH} digest={baseline['digest']}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
