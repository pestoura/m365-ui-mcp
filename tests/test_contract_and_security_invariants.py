"""Contract, schema and security-invariant tests (backlog P-004, P-005, P-063)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SCHEMAS = DOCS / "schemas"

SCHEMA_FILES = [
    "agent-card.schema.json",
    "capability-manifest.schema.json",
    "tool-manifest.schema.json",
    "extended-tool-manifest.schema.json",
    "worker-operation-envelope.schema.json",
    "mfa-event.schema.json",
]

REQUIRED_TOOLS_0_1_0 = [
    "planner_health",
    "planner_readiness",
    "planner_capabilities",
    "planner_agent_card",
    "planner_ui_contract_status",
    "planner_auth_status",
    "planner_auth_start",
    "planner_auth_resume",
    "planner_auth_session_info",
    "planner_plan_list",
    "planner_plan_get",
    "planner_task_list",
    "planner_task_get",
    "planner_project_snapshot",
    "planner_account_context",
    "planner_license_capabilities",
    "planner_smoke_test",
]


@pytest.mark.parametrize("name", SCHEMA_FILES)
def test_schema_is_valid_json_and_versioned(name: str) -> None:
    path = SCHEMAS / name
    assert path.is_file(), f"missing schema {name}"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["$schema"].startswith("https://json-schema.org/draft/2020-12")
    assert "0.1.0" in data["$id"], f"{name} $id must carry the 0.1.0 contract version"


@pytest.mark.parametrize("name", SCHEMA_FILES)
def test_schemas_reject_unknown_fields(name: str) -> None:
    data = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    assert data.get("additionalProperties") is False, (
        f"{name} must set additionalProperties=false at the root (SEC-022)"
    )


def test_versions_agree_with_code() -> None:
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from planner_mcp.version import CONTRACT_VERSION, PRODUCT_VERSION, SCHEMA_VERSION

    assert PRODUCT_VERSION == CONTRACT_VERSION == SCHEMA_VERSION == "0.1.0"


def test_mfa_event_schema_allows_only_the_five_permitted_fields() -> None:
    data = json.loads((SCHEMAS / "mfa-event.schema.json").read_text(encoding="utf-8"))
    assert set(data["properties"]) == {
        "operation_id",
        "service",
        "description",
        "mfa_number",
        "expires_at",
    }, "the sanitized MFA event must not gain fields (ADR-004)"
    assert data["additionalProperties"] is False


def test_worker_envelope_has_closed_operation_enum() -> None:
    data = json.loads((SCHEMAS / "worker-operation-envelope.schema.json").read_text("utf-8"))
    ops = data["properties"]["operation"]["enum"]
    assert ops, "operation enum must not be empty"
    forbidden = {"click", "type", "goto", "navigate", "evaluate", "press", "screenshot"}
    assert not (forbidden & set(ops)), "raw navigation primitives must never be operations"


def test_tool_catalog_lists_every_0_1_0_tool() -> None:
    catalog = (DOCS / "tool-catalog.md").read_text(encoding="utf-8")
    for tool in REQUIRED_TOOLS_0_1_0:
        assert tool in catalog, f"{tool} missing from the tool catalog"


def test_tool_catalog_exposes_no_raw_navigation_tool() -> None:
    catalog = (DOCS / "tool-catalog.md").read_text(encoding="utf-8")
    for bad in (
        "planner_click",
        "planner_type",
        "planner_goto",
        "planner_navigate",
        "planner_evaluate",
        "browser_click",
    ):
        assert bad not in catalog, f"raw navigation tool {bad} must not be exposed (ADR-001)"


def test_capability_matrix_declares_all_states() -> None:
    matrix = (DOCS / "planner-premium-capabilities.md").read_text(encoding="utf-8")
    for state in (
        "UNVERIFIED_LIVE",
        "DISCOVERED",
        "UI_ATTESTED",
        "READ_ATTESTED",
        "MUTATION_ATTESTED",
        "SUPPORTED",
        "UI_DRIFT",
        "BLOCKED_CONDITIONAL_ACCESS",
        "UNSUPPORTED_TENANT",
    ):
        assert state in matrix, f"capability state {state} not defined"


def test_capability_matrix_claims_no_live_support_yet() -> None:
    """No row may claim SUPPORTED/attested state without evidence in this block."""
    matrix = (DOCS / "planner-premium-capabilities.md").read_text(encoding="utf-8")
    rows = [ln for ln in matrix.splitlines() if ln.startswith("| ") and "UNVERIFIED_LIVE" in ln]
    assert len(rows) >= 20, "capability matrix should enumerate the Premium discovery areas"
    for ln in matrix.splitlines():
        if ln.startswith("| ") and "| SUPPORTED |" in ln:
            pytest.fail("a capability claims SUPPORTED without recorded browser evidence")


def test_matrix_states_graph_is_not_a_gate() -> None:
    matrix = (DOCS / "planner-premium-capabilities.md").read_text(encoding="utf-8").lower()
    assert "graph availability does not determine support" in matrix


def test_auth_states_documented() -> None:
    doc = (DOCS / "authentication-and-mfa.md").read_text(encoding="utf-8")
    for state in (
        "UNKNOWN",
        "READY",
        "AUTH_REQUIRED",
        "MFA_REQUIRED",
        "WAITING_FOR_MFA",
        "AUTHENTICATED",
        "SESSION_EXPIRED",
        "AUTH_FAILED",
    ):
        assert state in doc, f"auth state {state} not documented"


def test_conditional_access_is_fail_closed_everywhere() -> None:
    for name in ("security.md", "authentication-and-mfa.md", "privacy-boundary.md"):
        text = (DOCS / name).read_text(encoding="utf-8")
        assert "BLOCKER_CONDITIONAL_ACCESS" in text, f"{name} must state the CA blocker"


def test_no_secret_material_committed() -> None:
    """Crude repository hygiene gate (SEC-070/071)."""
    # Assembled at runtime so this test file is not itself a match.
    patterns = (
        "BEGIN RSA PRIVATE" + " KEY",
        "BEGIN PRIVATE" + " KEY",
        "xoxb" + "-",
        "ghp" + "_",
    )
    skip_dirs = (".git/", ".venv/", "__pycache__/", ".ruff_cache/", ".mypy_cache/")
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in str(path) for part in skip_dirs):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pat in patterns:
            assert pat not in text, f"possible secret material in {path}"


def test_gitignore_excludes_session_and_state_material() -> None:
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for entry in ("profile/", "evidence/", ".env", "*.sqlite"):
        assert entry in ignore, f".gitignore must exclude {entry}"
