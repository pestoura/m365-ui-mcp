#!/usr/bin/env python3
"""Isolated acceptance: exercises all 17 read-only tools against the in-process mock worker.

Never touches real Planner, never mutates anything, never performs a live sign-in.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ["PLANNER_MODE"] = "mock"

import httpx  # noqa: E402

from m365_mcp.config import Settings as ControlPlaneSettings  # noqa: E402
from m365_mcp.policy import evaluate as evaluate_policy  # noqa: E402
from planner_browser_worker.app import create_app  # noqa: E402
from planner_mcp.config import Settings  # noqa: E402
from planner_mcp.tools import TOOL_NAMES, PlannerTools  # noqa: E402
from planner_mcp.worker_client import WorkerClient  # noqa: E402


class InProcessWorkerClient(WorkerClient):
    """Worker client bound to the ASGI app."""

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


# REL-011: every check is mapped to the canonical IA scenario family in
# docs/acceptance.md so isolated acceptance coverage is machine-verifiable.
SCENARIO_MAP: dict[str, str] = {
    "tool_catalog_has_17": "IA-01",
    "versions_are_0_1_0": "IA-01",
    "no_graph_backend": "IA-01",
    "readiness_true": "IA-01",
    "sqlite_healthy": "IA-01",
    "ui_contract_fails_closed": "IA-05",
    "extended_manifest_complete": "IA-16",
    "capabilities_evidence_based": "IA-16",
    "mfa_sanitized_authenticator_only": "IA-06",
    "no_secrets_in_session": "IA-14",
    "plan_list_ok": "IA-03",
    "plan_get_ok": "IA-03",
    "task_list_ok": "IA-03",
    "task_get_ok": "IA-03",
    "snapshot_ok": "IA-04",
    "account_context_ok": "IA-03",
    "license_evidence_ok": "IA-16",
    "ui_contract_status_ok": "IA-05",
    "auth_status_ok": "IA-06",
    "auth_resume_ok": "IA-06",
    "smoke_passed": "IA-01",
    "zero_mutations": "IA-11",
    "mock_mode_enforced": "IA-02",
    "snapshot_deterministic": "IA-04",
    "policy_denies_unregistered_tool": "IA-09",
}


async def run() -> dict[str, Any]:
    """Execute the acceptance checks and return a report."""
    checks: list[dict[str, Any]] = []

    def record(name: str, ok: bool, detail: Any = None) -> None:
        checks.append(
            {
                "check": name,
                "scenario": SCENARIO_MAP.get(name, "UNMAPPED"),
                "ok": bool(ok),
                "detail": detail,
            }
        )

    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(mode="mock", state_path=Path(tmp) / "state.sqlite3")
        tools = PlannerTools(settings, InProcessWorkerClient(settings))

        record("tool_catalog_has_17", len(TOOL_NAMES) == 17, len(TOOL_NAMES))

        health = await tools.planner_health()
        record(
            "versions_are_0_1_0",
            health["product_version"] == health["schema_version"] == health["contract_version"]
            == "0.1.0",
        )
        record("no_graph_backend", health["graph_api_used"] is False)

        readiness = (await tools.planner_readiness())["data"]
        record("readiness_true", readiness["ready"] is True)
        record("sqlite_healthy", readiness["sqlite"]["ok"] is True)
        record(
            "ui_contract_fails_closed",
            readiness["ui_contract"]["attested"] is False
            and readiness["ui_contract"]["fail_closed_error"] == "UI_CONTRACT_UNATTESTED",
        )

        card = (await tools.planner_agent_card())["data"]
        extended_tools = card["extended_tool_manifest"]["tools"]
        record(
            "extended_manifest_complete",
            len(extended_tools) == 17
            and all(tool["mutation_class"] == "READ" for tool in extended_tools)
            and all(tool["attestation_status"] == "UNVERIFIED_LIVE" for tool in extended_tools),
        )

        caps = (await tools.planner_capabilities())["data"]
        record(
            "capabilities_evidence_based",
            caps["graph_api_used"] is False
            and bool(caps["capabilities"])
            and all(
                row["support_level"] == "UNVERIFIED_LIVE" for row in caps["capabilities"]
            ),
        )

        auth = (await tools.planner_auth_start())["data"]
        mfa = auth.get("mfa", {})
        record(
            "mfa_sanitized_authenticator_only",
            mfa.get("approval_channel") == "microsoft_authenticator"
            and len(str(mfa.get("mfa_number", ""))) == 2
            and "password" not in mfa
            and "token" not in mfa,
        )

        session = (await tools.planner_auth_session_info())["data"]
        record("no_secrets_in_session", session["secrets_stored_in_state"] is False)

        plans = (await tools.planner_plan_list())["data"]["plans"]
        record("plan_list_ok", bool(plans), len(plans))
        plan_id = plans[0]["id"]
        record(
            "plan_get_ok",
            (await tools.planner_plan_get(plan_id))["data"]["plan"]["id"] == plan_id,
        )
        tasks = (await tools.planner_task_list(plan_id))["data"]["tasks"]
        record("task_list_ok", bool(tasks), len(tasks))
        record(
            "task_get_ok",
            (await tools.planner_task_get(tasks[0]["id"]))["data"]["task"]["id"]
            == tasks[0]["id"],
        )
        snapshot = (await tools.planner_project_snapshot(plan_id))["data"]
        record("snapshot_ok", snapshot["plan"]["id"] == plan_id)
        record("account_context_ok", bool((await tools.planner_account_context())["data"]))
        record(
            "license_evidence_ok",
            (await tools.planner_license_capabilities())["data"]["graph_api_used"] is False,
        )
        record(
            "ui_contract_status_ok",
            (await tools.planner_ui_contract_status())["data"]["attested"] is False,
        )
        record("auth_status_ok", bool((await tools.planner_auth_status())["data"]["state"]))
        record("auth_resume_ok", bool((await tools.planner_auth_resume())["data"]))

        smoke = (await tools.planner_smoke_test())["data"]
        record("smoke_passed", smoke["passed"] is True)
        record("zero_mutations", smoke["mutations_performed"] == 0)

        # REL-011 additions: isolation, determinism and fail-closed policy.
        record(
            "mock_mode_enforced",
            settings.mode == "mock" and os.environ.get("PLANNER_MODE") == "mock",
            settings.mode,
        )
        repeat = (await tools.planner_project_snapshot(plan_id))["data"]
        record(
            "snapshot_deterministic",
            json.dumps(repeat, sort_keys=True) == json.dumps(snapshot, sort_keys=True),
        )
        decision = evaluate_policy(
            "planner_not_a_real_tool", ControlPlaneSettings(mode="mock")
        )
        record(
            "policy_denies_unregistered_tool",
            decision.decision.value == "DENY" and decision.reason == "TOOL_NOT_REGISTERED",
            decision.reason,
        )

    unmapped = sorted(c["check"] for c in checks if c["scenario"] == "UNMAPPED")
    scenarios = sorted({c["scenario"] for c in checks})
    return {
        "passed": all(c["ok"] for c in checks) and not unmapped,
        "requirement": "REL-011",
        "scenarios_covered": scenarios,
        "unmapped_checks": unmapped,
        "checks": checks,
    }


def main() -> None:
    """Entry point."""
    report = asyncio.run(run())
    out = Path("artifacts")
    out.mkdir(exist_ok=True)
    (out / "isolated-acceptance.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    sys.exit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
