"""P-002 package-layout acceptance tests."""

from __future__ import annotations

import importlib


ARCHITECTURAL_PACKAGES = (
    "planner_mcp.control_plane",
    "planner_mcp.worker",
    "planner_mcp.browser",
    "planner_mcp.policy",
    "planner_mcp.state",
)


def test_architectural_subpackages_import() -> None:
    loaded = [importlib.import_module(name) for name in ARCHITECTURAL_PACKAGES]
    assert all(module.__package__ for module in loaded)


def test_package_boundaries_expose_expected_api() -> None:
    control_plane = importlib.import_module("planner_mcp.control_plane")
    worker = importlib.import_module("planner_mcp.worker")
    browser = importlib.import_module("planner_mcp.browser")
    policy = importlib.import_module("planner_mcp.policy")
    state = importlib.import_module("planner_mcp.state")

    assert callable(control_plane.build_server)
    assert callable(control_plane.run)
    assert worker.WorkerClient.__name__ == "WorkerClient"
    assert callable(browser.require_attested)
    assert callable(policy.evaluate)
    assert callable(state.initialise)
    assert callable(state.health)
