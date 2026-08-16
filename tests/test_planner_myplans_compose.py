"""Deployment contract for account-wide Planner discovery.

The first-delivery ``planner_plan_list`` read must start from the account-wide
Planner My Plans hub rather than a single plan deep link or the marketing root.
The compose default remains operator-overridable, but the safe default must be
My Plans so the worker can discover all plans accessible to the professional
account through the UI.
"""

from __future__ import annotations

from pathlib import Path

COMPOSE_FILE = Path(__file__).resolve().parents[1] / "docker-compose.yml"
EXPECTED_BOOTSTRAP = (
    "PLANNER_WEB_BOOTSTRAP_URL: "
    "${PLANNER_WEB_BOOTSTRAP_URL:-https://planner.cloud.microsoft/webui/myplans/}"
)


def test_browser_worker_defaults_to_account_wide_my_plans_surface() -> None:
    compose = COMPOSE_FILE.read_text(encoding="utf-8")
    assert EXPECTED_BOOTSTRAP in compose
