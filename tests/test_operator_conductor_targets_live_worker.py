"""TDD proof: operator conductor scripts must target the ACTUAL live worker.

The live Planner MCP browser-worker stack runs as Docker compose project
``planner-mcp`` with the running container named
``planner-mcp-browser-worker-1`` (verified via ``docker ps`` and
``docker inspect ... com.docker.compose.project``). The earlier hard-coded
value ``m365-ui-mcp-browser-worker-1`` does not exist on this host, so every
``docker exec`` in the canonical sign-in flow failed with "No such container",
making real browser authentication impossible. The container name is a fixed,
non-configurable constant by design (no env/getenv override); this suite only
pins it to the value that actually exists.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# The only container name that exists on the live host for the running worker.
LIVE_WORKER_CONTAINER = "planner-mcp-browser-worker-1"
STALE_WORKER_CONTAINER = "m365-ui-mcp-browser-worker-1"


def _load_module(filename: str, modname: str):
    spec = importlib.util.spec_from_file_location(
        modname, ROOT / "scripts" / filename
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def operator_auth_run():
    return _load_module("operator_auth_run.py", "operator_auth_run_tdw")


@pytest.fixture
def operator_auth_begin_email():
    return _load_module("operator_auth_begin_email.py", "operator_auth_begin_email_tdw")


def test_run_targets_live_worker_container(operator_auth_run) -> None:
    assert operator_auth_run._WORKER_CONTAINER == LIVE_WORKER_CONTAINER
    assert operator_auth_run._WORKER_CONTAINER != STALE_WORKER_CONTAINER


def test_begin_email_targets_live_worker_container(operator_auth_begin_email) -> None:
    assert operator_auth_begin_email._WORKER_CONTAINER == LIVE_WORKER_CONTAINER
    assert operator_auth_begin_email._WORKER_CONTAINER != STALE_WORKER_CONTAINER


def test_begin_email_wrapper_shell_targets_live_worker() -> None:
    script = ROOT / "scripts" / "operator_auth_bootstrap_begin_signin.sh"
    text = script.read_text(encoding="utf-8")
    assert LIVE_WORKER_CONTAINER in text
    assert STALE_WORKER_CONTAINER not in text


def test_navigate_wrapper_shell_targets_live_worker() -> None:
    script = ROOT / "scripts" / "operator_auth_bootstrap_navigate.sh"
    text = script.read_text(encoding="utf-8")
    assert LIVE_WORKER_CONTAINER in text
    assert STALE_WORKER_CONTAINER not in text
