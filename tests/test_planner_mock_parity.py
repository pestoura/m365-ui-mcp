"""PLN-MIG-008 — Planner mock parity suite.

Executes the complete preserved 17-tool Planner public surface in mock mode and
asserts that the normalized outputs still match the canonical pre-extraction
parity baseline. Mock parity never implies live support.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from m365_mcp.apps.planner.mock_parity import (
    VOLATILE_PLACEHOLDER,
    normalize,
    parity_digest,
    parity_snapshot,
)
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


class InProcessWorkerClient(WorkerClient):
    """WorkerClient bound to the in-process mock worker ASGI app."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._transport = httpx.ASGITransport(app=create_app())

    async def _get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(
            transport=self._transport, base_url="http://worker"
        ) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data


async def _collect(tools: PlannerTools) -> dict[str, dict[str, Any]]:
    plans = (await tools.planner_plan_list())["data"]["plans"]
    plan_id = str(plans[0]["id"])
    tasks = (await tools.planner_task_list(plan_id))["data"]["tasks"]
    task_id = str(tasks[0]["id"])

    return {
        "planner_health": await tools.planner_health(),
        "planner_readiness": await tools.planner_readiness(),
        "planner_capabilities": await tools.planner_capabilities(),
        "planner_agent_card": await tools.planner_agent_card(),
        "planner_ui_contract_status": await tools.planner_ui_contract_status(),
        "planner_auth_status": await tools.planner_auth_status(),
        "planner_auth_start": await tools.planner_auth_start(),
        "planner_auth_resume": await tools.planner_auth_resume(),
        "planner_auth_session_info": await tools.planner_auth_session_info(),
        "planner_plan_list": await tools.planner_plan_list(),
        "planner_plan_get": await tools.planner_plan_get(plan_id),
        "planner_task_list": await tools.planner_task_list(plan_id),
        "planner_task_get": await tools.planner_task_get(task_id),
        "planner_project_snapshot": await tools.planner_project_snapshot(plan_id),
        "planner_account_context": await tools.planner_account_context(),
        "planner_license_capabilities": await tools.planner_license_capabilities(),
        "planner_smoke_test": await tools.planner_smoke_test(),
    }


@pytest.fixture()
def tools(state_path: Path) -> PlannerTools:
    settings = Settings(mode="mock", state_path=state_path)
    return PlannerTools(settings, InProcessWorkerClient(settings))


def _baseline() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return payload


def test_baseline_covers_exact_preserved_public_abi() -> None:
    baseline = _baseline()

    assert tuple(baseline["tools"]) == PLANNER_PUBLIC_TOOL_NAMES
    assert len(baseline["tools"]) == 17
    assert baseline["live_support_claimed"] is False
    assert baseline["mode"] == "mock"


async def test_normalized_mock_outputs_match_frozen_parity_baseline(
    tools: PlannerTools,
) -> None:
    snapshot = parity_snapshot(await _collect(tools))
    baseline = _baseline()

    assert list(snapshot) == list(baseline["tools"])
    for name in snapshot:
        assert snapshot[name] == baseline["tools"][name], f"mock parity drift in {name}"
    assert parity_digest(snapshot) == baseline["digest"]


async def test_mock_parity_is_deterministic_across_repeated_runs(
    tools: PlannerTools,
) -> None:
    first = parity_snapshot(await _collect(tools))
    second = parity_snapshot(await _collect(tools))

    assert first == second
    assert parity_digest(first) == parity_digest(second)


async def test_mock_parity_preserves_read_only_governance_flags(
    tools: PlannerTools,
) -> None:
    snapshot = parity_snapshot(await _collect(tools))

    assert all(envelope["read_only"] is True for envelope in snapshot.values())
    assert all(envelope["graph_api_used"] is False for envelope in snapshot.values())
    assert snapshot["planner_smoke_test"]["data"]["mutations_performed"] == 0


def test_normalization_masks_only_volatile_values() -> None:
    normalized = normalize(
        {
            "expires_at": "2026-01-01T00:00:00Z",
            "operation_id": "mock-op-1",
            "state": "MFA_REQUIRED",
            "items": [{"timestamp": 1, "title": "Alpha"}],
        }
    )

    assert normalized == {
        "expires_at": VOLATILE_PLACEHOLDER,
        "items": [{"timestamp": VOLATILE_PLACEHOLDER, "title": "Alpha"}],
        "operation_id": VOLATILE_PLACEHOLDER,
        "state": "MFA_REQUIRED",
    }


def test_parity_digest_changes_when_semantic_payload_changes() -> None:
    base = {"planner_plan_list": {"data": {"plans": [{"id": "plan-alpha"}]}}}
    changed = {"planner_plan_list": {"data": {"plans": [{"id": "plan-omega"}]}}}

    assert parity_digest(parity_snapshot(base)) != parity_digest(parity_snapshot(changed))
