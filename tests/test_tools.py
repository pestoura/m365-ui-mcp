"""Control-plane tool tests against the in-process mock worker."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest

from planner_browser_worker.app import create_app
from planner_mcp.config import Settings
from planner_mcp.tools import TOOL_NAMES, PlannerTools
from planner_mcp.version import CONTRACT_VERSION
from planner_mcp.worker_client import WorkerClient


class InProcessWorkerClient(WorkerClient):
    """WorkerClient bound to the ASGI app instead of a TCP socket."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._transport = httpx.ASGITransport(app=create_app())

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(
            transport=self._transport, base_url="http://worker"
        ) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data


@pytest.fixture()
def tools(state_path: Path) -> PlannerTools:
    settings = Settings(mode="mock", state_path=state_path)
    return PlannerTools(settings, InProcessWorkerClient(settings))


def test_catalog_has_17_read_tools() -> None:
    assert len(TOOL_NAMES) == 17
    assert len(set(TOOL_NAMES)) == 17


async def test_health_and_versions(tools: PlannerTools) -> None:
    out = await tools.planner_health()
    assert out["product_version"] == "0.1.0"
    assert out["schema_version"] == "0.1.0"
    assert out["contract_version"] == "0.1.0"
    assert out["graph_api_used"] is False


async def test_every_tool_response_contains_contract_version(tools: PlannerTools) -> None:
    plans = (await tools.planner_plan_list())["data"]["plans"]
    plan_id = str(plans[0]["id"])
    tasks = (await tools.planner_task_list(plan_id))["data"]["tasks"]
    task_id = str(tasks[0]["id"])

    responses = [
        await tools.planner_health(),
        await tools.planner_readiness(),
        await tools.planner_capabilities(),
        await tools.planner_agent_card(),
        await tools.planner_ui_contract_status(),
        await tools.planner_auth_status(),
        await tools.planner_auth_start(),
        await tools.planner_auth_resume(),
        await tools.planner_auth_session_info(),
        await tools.planner_plan_list(),
        await tools.planner_plan_get(plan_id),
        await tools.planner_task_list(plan_id),
        await tools.planner_task_get(task_id),
        await tools.planner_project_snapshot(plan_id),
        await tools.planner_account_context(),
        await tools.planner_license_capabilities(),
        await tools.planner_smoke_test(),
    ]

    assert len(responses) == len(TOOL_NAMES) == 17
    assert {str(response["tool"]) for response in responses} == set(TOOL_NAMES)
    assert all(response["contract_version"] == CONTRACT_VERSION for response in responses)


async def test_readiness(tools: PlannerTools) -> None:
    out = await tools.planner_readiness()
    data = out["data"]
    assert data["ready"] is True
    assert data["sqlite"]["ok"] is True
    assert data["ui_contract"]["attested"] is False
    assert data["configuration"]["mode"] == "mock"
    assert data["configuration"]["host"] == "[REDACTED]"
    assert data["configuration"]["worker_base_url"] == "[REDACTED]"
    assert data["configuration"]["state_path"] == "[REDACTED]"
    assert data["configuration"]["allow_mutations"] is False


async def test_agent_card_metadata(tools: PlannerTools) -> None:
    data = (await tools.planner_agent_card())["data"]
    extended = data["extended_tool_manifest"]["tools"]
    assert len(extended) == 17
    for entry in extended:
        assert set(entry) >= {
            "trust_level",
            "mutation_class",
            "reversible",
            "idempotency_class",
            "approval_requirement",
            "attestation_status",
        }
        assert entry["mutation_class"] == "READ"
        assert entry["attestation_status"] == "UNVERIFIED_LIVE"


async def test_reads(tools: PlannerTools) -> None:
    plans = (await tools.planner_plan_list())["data"]["plans"]
    plan_id = plans[0]["id"]
    assert (await tools.planner_plan_get(plan_id))["data"]["plan"]["id"] == plan_id
    tasks = (await tools.planner_task_list(plan_id))["data"]["tasks"]
    assert tasks
    task_id = tasks[0]["id"]
    assert (await tools.planner_task_get(task_id))["data"]["task"]["id"] == task_id
    snapshot = (await tools.planner_project_snapshot(plan_id))["data"]
    assert snapshot["plan"]["id"] == plan_id


async def test_capabilities_and_license(tools: PlannerTools) -> None:
    caps = (await tools.planner_capabilities())["data"]
    assert caps["graph_api_used"] is False
    assert all(row["support_level"] == "UNVERIFIED_LIVE" for row in caps["capabilities"])
    lic = (await tools.planner_license_capabilities())["data"]
    assert lic["premium_detected"] is True
    assert lic["graph_api_used"] is False


async def test_auth_tools_sanitized(tools: PlannerTools) -> None:
    start = (await tools.planner_auth_start())["data"]
    assert start["mfa"]["mfa_number"] == "42"
    assert start["mfa"]["approval_channel"] == "microsoft_authenticator"
    session = (await tools.planner_auth_session_info())["data"]
    assert session["secrets_stored_in_state"] is False


async def test_smoke_test_passes_with_no_mutations(tools: PlannerTools) -> None:
    out = (await tools.planner_smoke_test())["data"]
    assert out["passed"] is True
    assert out["mutations_performed"] == 0
