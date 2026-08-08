"""CORE-003 canonical M365 namespace and Planner compatibility tests."""

from __future__ import annotations

import tomllib
from pathlib import Path

from m365_browser_worker.app import app as m365_worker_app
from m365_mcp import CONTRACT_VERSION as M365_CONTRACT_VERSION
from m365_mcp import SCHEMA_VERSION as M365_SCHEMA_VERSION
from m365_mcp import __version__ as M365_VERSION
from m365_mcp.server import build_server as m365_build_server
from m365_mcp.version import PRODUCT_VERSION as M365_PRODUCT_VERSION
from planner_browser_worker.app import app as planner_worker_app
from planner_mcp import CONTRACT_VERSION as PLANNER_CONTRACT_VERSION
from planner_mcp import SCHEMA_VERSION as PLANNER_SCHEMA_VERSION
from planner_mcp import __version__ as PLANNER_VERSION
from planner_mcp.server import build_server as planner_build_server
from planner_mcp.tools import TOOL_NAMES

ROOT = Path(__file__).resolve().parents[1]


def test_canonical_m365_version_is_planner_compatible() -> None:
    assert M365_PRODUCT_VERSION == M365_VERSION == "0.1.0"
    assert M365_VERSION == PLANNER_VERSION
    assert M365_CONTRACT_VERSION == PLANNER_CONTRACT_VERSION
    assert M365_SCHEMA_VERSION == PLANNER_SCHEMA_VERSION


def test_namespace_facades_reference_same_runtime_objects() -> None:
    assert m365_build_server is planner_build_server
    assert m365_worker_app is planner_worker_app


def test_planner_public_tool_compatibility_is_unchanged() -> None:
    assert len(TOOL_NAMES) == 17
    assert all(name.startswith("planner_") for name in TOOL_NAMES)


def test_packaging_exposes_canonical_and_compatibility_entry_points() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = data["project"]["scripts"]

    assert scripts["m365-ui-mcp"] == "m365_mcp.__main__:main"
    assert scripts["m365-browser-worker"] == "m365_browser_worker.__main__:main"
    assert scripts["m365-ui-mcp-healthcheck"] == "m365_mcp.healthcheck:main"
    assert scripts["planner-mcp"] == "planner_mcp.__main__:main"
    assert scripts["planner-browser-worker"] == "planner_browser_worker.__main__:main"
    assert scripts["planner-mcp-healthcheck"] == "planner_mcp.healthcheck:main"
    assert data["tool"]["hatch"]["version"]["path"] == "src/m365_mcp/version.py"


def test_wheel_keeps_both_namespaces_during_migration() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    packages = set(data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"])
    assert packages == {
        "src/m365_mcp",
        "src/m365_browser_worker",
        "src/planner_mcp",
        "src/planner_browser_worker",
    }
