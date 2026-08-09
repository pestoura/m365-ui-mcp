"""REL-009 — Repository-wide no-generic-browser-operation regression suite.

Existing per-module tests assert the absence of generic primitives in the
worker protocol, lifecycle exports and registration source. This suite
generalises that invariant across the whole published surface so a future
application cannot reintroduce a generic click/type/navigate/eval capability
through a new module, tool name or worker operation.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from m365_browser_worker.protocol import (
    FORBIDDEN_PROTOCOL_FIELDS,
    WorkerOperation,
    WorkerRequestEnvelope,
    WorkerResponseEnvelope,
)
from m365_mcp.tool_registry import default_tool_registry
from planner_mcp import registration, tools

ROOT = Path(__file__).resolve().parents[1]

GENERIC_TOOL_TOKENS = (
    "browser_exec",
    "browser_run",
    "raw_action",
    "execute_script",
    "run_script",
    "eval",
    "click",
    "type_text",
    "keypress",
    "navigate",
    "goto",
    "screenshot",
    "dom_query",
    "xpath",
    "selector",
)

DANGEROUS_SOURCE_TOKENS = (
    "eval(",
    "exec(",
    "os.system",
    "subprocess.popen",
    "page.evaluate",
    "add_init_script",
)

PUBLIC_SOURCE_MODULES = (
    "src/m365_mcp/server.py",
    "src/m365_mcp/tool_registry.py",
    "src/planner_mcp/registration.py",
    "src/planner_mcp/tools.py",
    "src/m365_browser_worker/protocol.py",
)


def test_no_public_tool_name_exposes_a_generic_browser_primitive() -> None:
    names = set(default_tool_registry().names()) | set(tools.TOOL_NAMES)
    for name in names:
        lowered = name.lower()
        for token in GENERIC_TOOL_TOKENS:
            assert token not in lowered, (name, token)


def test_no_worker_operation_exposes_a_generic_browser_primitive() -> None:
    for operation in WorkerOperation:
        lowered = operation.value.lower()
        assert lowered.count(".") >= 1, operation.value
        for token in GENERIC_TOOL_TOKENS:
            assert token not in lowered, (operation.value, token)


def test_worker_envelopes_never_accept_transport_or_primitive_fields() -> None:
    serialized = (
        f"{WorkerRequestEnvelope.model_json_schema()} "
        f"{WorkerResponseEnvelope.model_json_schema()}"
    ).lower()
    for field in FORBIDDEN_PROTOCOL_FIELDS:
        assert f"'{field}'" not in serialized
        assert f'"{field}"' not in serialized


def test_registration_surface_binds_only_registry_backed_semantic_tools() -> None:
    source = inspect.getsource(registration).lower()
    for token in DANGEROUS_SOURCE_TOKENS:
        assert token not in source, token


def test_public_control_plane_modules_contain_no_dynamic_execution_sinks() -> None:
    for relative in PUBLIC_SOURCE_MODULES:
        path = ROOT / relative
        assert path.is_file(), relative
        lowered = path.read_text(encoding="utf-8").lower()
        for token in DANGEROUS_SOURCE_TOKENS:
            assert token not in lowered, (relative, token)


def test_registry_tool_schemas_never_accept_url_or_selector_inputs() -> None:
    registry = default_tool_registry()
    for name in registry.names():
        properties = registry.get(name).input_schema.get("properties", {})
        for field in properties:
            lowered = field.lower()
            assert lowered not in FORBIDDEN_PROTOCOL_FIELDS, (name, field)
            for token in ("xpath", "selector", "script", "javascript"):
                assert token not in lowered, (name, field)
