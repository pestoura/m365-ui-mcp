"""REL-012 — Planner parity acceptance.

REL-012 is the *acceptance* statement over the two parity mechanisms that
PLN-MIG-008 (mock output parity) and PLN-MIG-009 (governance parity) provide.
Those suites prove each mechanism internally. This suite proves the acceptance
claim they are supposed to jointly support:

1. both parity baselines describe the same, complete, canonically ordered
   17-tool preserved Planner public ABI;
2. neither baseline claims live support, and neither can be used to promote a
   capability;
3. the observed mock output digest and the observed governance digest both
   match their frozen baselines *in the same run*, so parity cannot be
   declared from a stale half;
4. no preserved tool is a mutation, is Graph-backed, or lost a capability
   constraint;
5. the acceptance itself is falsifiable — a perturbation of either baseline
   is detected.

The suite is mock/isolated. It contacts no Microsoft 365 tenant, starts no
browser and attests nothing about live behaviour.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from m365_mcp.apps.planner.mock_parity import parity_digest, parity_snapshot
from m365_mcp.apps.planner.policy_parity import (
    governance_regressions,
    policy_parity_digest,
    policy_parity_snapshot,
)
from m365_mcp.apps.planner.public_surface import PLANNER_PUBLIC_TOOL_NAMES
from m365_mcp.tool_registry import MutationClass, default_tool_registry
from planner_browser_worker.app import create_app
from planner_mcp.config import Settings
from planner_mcp.tools import PlannerTools
from planner_mcp.worker_client import WorkerClient

ROOT = Path(__file__).resolve().parents[1]
MOCK_BASELINE_PATH = ROOT / "tests" / "data" / "planner_mock_parity_baseline.json"
POLICY_BASELINE_PATH = ROOT / "tests" / "data" / "planner_policy_parity_baseline.json"

#: The preserved public ABI is a release invariant, not an incidental count.
PRESERVED_PUBLIC_TOOL_COUNT = 17


class _InProcessWorkerClient(WorkerClient):
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


@pytest.fixture
def tools(tmp_path: Path) -> PlannerTools:
    settings = Settings(mode="mock", state_path=tmp_path / "state.sqlite3")
    return PlannerTools(settings, _InProcessWorkerClient(settings))


async def _collect(planner_tools: PlannerTools) -> dict[str, dict[str, Any]]:
    plans = (await planner_tools.planner_plan_list())["data"]["plans"]
    plan_id = str(plans[0]["id"])
    tasks = (await planner_tools.planner_task_list(plan_id))["data"]["tasks"]
    task_id = str(tasks[0]["id"])

    return {
        "planner_health": await planner_tools.planner_health(),
        "planner_readiness": await planner_tools.planner_readiness(),
        "planner_capabilities": await planner_tools.planner_capabilities(),
        "planner_agent_card": await planner_tools.planner_agent_card(),
        "planner_ui_contract_status": await planner_tools.planner_ui_contract_status(),
        "planner_auth_status": await planner_tools.planner_auth_status(),
        "planner_auth_start": await planner_tools.planner_auth_start(),
        "planner_auth_resume": await planner_tools.planner_auth_resume(),
        "planner_auth_session_info": await planner_tools.planner_auth_session_info(),
        "planner_plan_list": await planner_tools.planner_plan_list(),
        "planner_plan_get": await planner_tools.planner_plan_get(plan_id),
        "planner_task_list": await planner_tools.planner_task_list(plan_id),
        "planner_task_get": await planner_tools.planner_task_get(task_id),
        "planner_project_snapshot": await planner_tools.planner_project_snapshot(plan_id),
        "planner_account_context": await planner_tools.planner_account_context(),
        "planner_license_capabilities": await planner_tools.planner_license_capabilities(),
        "planner_smoke_test": await planner_tools.planner_smoke_test(),
    }


def _mock_baseline() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(MOCK_BASELINE_PATH.read_text(encoding="utf-8"))
    return payload


def _policy_baseline() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(POLICY_BASELINE_PATH.read_text(encoding="utf-8"))
    return payload


def test_both_parity_baselines_describe_the_same_preserved_public_abi() -> None:
    mock_baseline = _mock_baseline()
    policy_baseline = _policy_baseline()

    assert tuple(mock_baseline["tools"]) == PLANNER_PUBLIC_TOOL_NAMES
    assert tuple(policy_baseline["tools"]) == PLANNER_PUBLIC_TOOL_NAMES
    assert tuple(policy_baseline["governance"]) == PLANNER_PUBLIC_TOOL_NAMES
    assert len(PLANNER_PUBLIC_TOOL_NAMES) == PRESERVED_PUBLIC_TOOL_COUNT
    assert len(set(PLANNER_PUBLIC_TOOL_NAMES)) == PRESERVED_PUBLIC_TOOL_COUNT


def test_parity_acceptance_never_claims_live_support() -> None:
    for baseline in (_mock_baseline(), _policy_baseline()):
        assert baseline["live_support_claimed"] is False
        assert baseline["mode"] == "mock"

    for record in _policy_baseline()["governance"].values():
        assert record["implementation_state"] != "IMPLEMENTED_LIVE"


async def test_output_and_governance_parity_hold_in_the_same_run(
    tools: PlannerTools,
) -> None:
    """Both halves of the parity claim must be observed together."""
    output_snapshot = parity_snapshot(await _collect(tools))
    governance_snapshot = policy_parity_snapshot()

    assert list(output_snapshot) == list(PLANNER_PUBLIC_TOOL_NAMES)
    assert list(governance_snapshot) == list(PLANNER_PUBLIC_TOOL_NAMES)
    assert parity_digest(output_snapshot) == _mock_baseline()["digest"]
    assert policy_parity_digest(governance_snapshot) == _policy_baseline()["digest"]
    assert governance_regressions(governance_snapshot, _policy_baseline()["governance"]) == ()


async def test_preserved_surface_stays_read_only_and_graph_free(
    tools: PlannerTools,
) -> None:
    output_snapshot = parity_snapshot(await _collect(tools))
    registry = default_tool_registry()

    for name in PLANNER_PUBLIC_TOOL_NAMES:
        assert registry.get(name).mutation_class is MutationClass.READ, name
        assert output_snapshot[name]["read_only"] is True, name
        assert output_snapshot[name]["graph_api_used"] is False, name


def test_governance_parity_preserves_every_capability_constraint() -> None:
    snapshot = policy_parity_snapshot()
    baseline = _policy_baseline()["governance"]

    for tool, expected in baseline.items():
        assert set(expected["capability_keys"]) <= set(snapshot[tool]["capability_keys"]), tool


def test_parity_acceptance_is_falsifiable_on_output_drift() -> None:
    """A perturbed output baseline must not still digest to the frozen value."""
    perturbed = json.loads(json.dumps(_mock_baseline()["tools"]))
    perturbed["planner_plan_list"]["read_only"] = False

    assert parity_digest(perturbed) != _mock_baseline()["digest"]


def test_parity_acceptance_is_falsifiable_on_governance_drift() -> None:
    """A weakened governance baseline must be reported as a regression."""
    weakened = json.loads(json.dumps(_policy_baseline()["governance"]))
    weakened["planner_task_get"]["security_tier"] = 0

    assert policy_parity_digest(weakened) != _policy_baseline()["digest"]
    assert governance_regressions(weakened, _policy_baseline()["governance"]) == (
        "planner_task_get",
    )


def test_parity_acceptance_records_contain_no_tenant_or_credential_material() -> None:
    payload = json.dumps([_mock_baseline(), _policy_baseline()]).lower()

    for token in (
        "graph.microsoft.com",
        "bearer ",
        "refresh_token",
        "client_secret",
        "password",
        "cookie",
        "@outlook.com",
        "/home/",
    ):
        assert token not in payload, token
