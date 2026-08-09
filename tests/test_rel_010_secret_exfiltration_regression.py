"""REL-010 — Secret and session exfiltration regression suite.

End-to-end assurance that no public projection of the product — tool results,
registry snapshots, contract documents, health/readiness payloads or structured
logs — can carry credential or session material out of the trust boundary.

Runs entirely against the in-process mock worker. No tenant, no network.
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Any

import httpx
import pytest

from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.tool_registry import default_tool_registry
from m365_mcp.ui_contract_store import load_ui_contract_set
from planner_browser_worker.app import create_app
from planner_mcp.config import Settings
from planner_mcp.contracts import contracts_dir
from planner_mcp.logging_setup import JsonFormatter
from planner_mcp.redaction import REDACTED, SENSITIVE_KEYS, redact
from planner_mcp.tools import PlannerTools
from planner_mcp.worker_client import WorkerClient

FORBIDDEN_KEYS = frozenset(SENSITIVE_KEYS) | {
    "storage_state",
    "session_cookie",
    "auth_header",
    "bearer",
    "private_key",
}

FORBIDDEN_VALUE_MARKERS = (
    "-----BEGIN",
    "eyJhbGciOi",
    "Bearer ",
    "Set-Cookie",
)


class _InProcessWorkerClient(WorkerClient):
    """Worker client bound to the mock ASGI app; never reaches the network."""

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


def _walk(payload: Any, path: str = "$") -> list[tuple[str, str, Any]]:
    """Flatten a payload into (path, key, value) triples."""
    found: list[tuple[str, str, Any]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            found.append((f"{path}.{key}", str(key), value))
            found.extend(_walk(value, f"{path}.{key}"))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            found.extend(_walk(value, f"{path}[{index}]"))
    return found


def _assert_clean(payload: Any, origin: str) -> None:
    for node_path, key, value in _walk(payload):
        if key.lower() in FORBIDDEN_KEYS:
            assert value in (None, "", REDACTED, False), (origin, node_path, key)
        if isinstance(value, str):
            for marker in FORBIDDEN_VALUE_MARKERS:
                assert marker not in value, (origin, node_path, marker)


@pytest.fixture()
def mock_tools() -> Any:
    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(mode="mock", state_path=Path(tmp) / "state.sqlite3")
        yield PlannerTools(settings, _InProcessWorkerClient(settings))


async def test_no_read_tool_result_carries_credential_or_session_material(
    mock_tools: PlannerTools,
) -> None:
    results = {
        "planner_health": await mock_tools.planner_health(),
        "planner_readiness": await mock_tools.planner_readiness(),
        "planner_capabilities": await mock_tools.planner_capabilities(),
        "planner_agent_card": await mock_tools.planner_agent_card(),
        "planner_ui_contract_status": await mock_tools.planner_ui_contract_status(),
        "planner_auth_status": await mock_tools.planner_auth_status(),
        "planner_auth_start": await mock_tools.planner_auth_start(),
        "planner_auth_resume": await mock_tools.planner_auth_resume(),
        "planner_auth_session_info": await mock_tools.planner_auth_session_info(),
        "planner_account_context": await mock_tools.planner_account_context(),
        "planner_license_capabilities": await mock_tools.planner_license_capabilities(),
        "planner_smoke_test": await mock_tools.planner_smoke_test(),
    }
    for name, payload in results.items():
        _assert_clean(payload, name)


async def test_content_read_results_are_clean_and_serialize_without_secrets(
    mock_tools: PlannerTools,
) -> None:
    plans = (await mock_tools.planner_plan_list())["data"]["plans"]
    plan_id = plans[0]["id"]
    tasks = (await mock_tools.planner_task_list(plan_id))["data"]["tasks"]

    payloads = {
        "planner_plan_list": {"plans": plans},
        "planner_plan_get": await mock_tools.planner_plan_get(plan_id),
        "planner_task_list": {"tasks": tasks},
        "planner_task_get": await mock_tools.planner_task_get(tasks[0]["id"]),
        "planner_project_snapshot": await mock_tools.planner_project_snapshot(plan_id),
    }
    for name, payload in payloads.items():
        _assert_clean(payload, name)
        json.dumps(payload)  # public results must stay JSON-serializable


async def test_auth_projections_never_expose_password_token_or_storage_state(
    mock_tools: PlannerTools,
) -> None:
    auth = (await mock_tools.planner_auth_start())["data"]
    session = (await mock_tools.planner_auth_session_info())["data"]

    assert session["secrets_stored_in_state"] is False
    for blob in (auth, session):
        flat = json.dumps(blob).lower()
        for token in ("password", "refresh_token", "storage_state", "set-cookie"):
            assert token not in flat


def test_registry_and_contract_projections_expose_no_secret_material() -> None:
    _assert_clean(list(default_tool_registry().snapshot()), "tool_registry.snapshot")
    _assert_clean(list(default_capability_registry().snapshot()), "capability_registry")
    _assert_clean(load_ui_contract_set().canonical_payload(), "ui_contract_set")

    for document in sorted(contracts_dir().glob("*.json")):
        payload = json.loads(document.read_text(encoding="utf-8"))
        _assert_clean(payload, f"contracts/{document.name}")


def test_structured_logs_redact_every_sensitive_key() -> None:
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "op", None, None)
    for key in ("password", "token", "cookie", "authorization", "storage_state"):
        setattr(record, key, "should-never-appear")
    payload = json.loads(JsonFormatter().format(record))
    for key in ("password", "token", "cookie", "authorization", "storage_state"):
        assert payload[key] == REDACTED
    assert "should-never-appear" not in json.dumps(payload)


def test_redaction_survives_nested_and_listed_secret_material() -> None:
    payload = redact(
        {
            "outer": [
                {"token": "abc"},
                {"nested": {"client_secret": "xyz", "safe": "value"}},
            ],
            "text": "bearer eyJhbGciOi.eyJzdWIiOm.Sflkxwsd",
        }
    )
    assert payload["outer"][0]["token"] == REDACTED
    assert payload["outer"][1]["nested"]["client_secret"] == REDACTED
    assert payload["outer"][1]["nested"]["safe"] == "value"
    assert "eyJhbGciOi" not in payload["text"]
