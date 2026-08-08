"""Specification-foundation tests (backlog P-001).

These validate the canonical documents and schemas that later implementation
must not silently drift from. They run offline and never touch a tenant.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SCHEMAS = DOCS / "schemas"

REQUIRED_DOCS = [
    "vision.md",
    "architecture.md",
    "threat-model.md",
    "security.md",
    "governance.md",
    "authentication-and-mfa.md",
    "privacy-boundary.md",
    "planner-premium-capabilities.md",
    "tool-catalog.md",
    "reconciliation.md",
    "idempotency.md",
    "state-model.md",
    "ui-contract.md",
    "browser-worker.md",
    "observability.md",
    "testing.md",
    "acceptance.md",
    "deployment.md",
    "cloudflare-mcp-portal.md",
    "hermes-integration.md",
    "reporting.md",
    "roadmap.md",
    "backlog.md",
    "release-process.md",
    "traceability.md",
    "definition-of-done.md",
]

REQUIRED_ADRS = [
    "ADR-001-browser-automation.md",
    "ADR-002-control-plane-worker-separation.md",
    "ADR-003-reconciliation-first.md",
    "ADR-004-human-in-loop-mfa.md",
    "ADR-005-hermes-bridge-foundation.md",
    "ADR-006-graph-not-a-functional-gate.md",
    "ADR-007-ui-contract-attestation.md",
    "ADR-008-personal-device-privacy-boundary.md",
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

CAPABILITY_STATES = [
    "UNVERIFIED_LIVE",
    "DISCOVERED",
    "UI_ATTESTED",
    "READ_ATTESTED",
    "MUTATION_ATTESTED",
    "SUPPORTED",
    "UI_DRIFT",
    "BLOCKED_CONDITIONAL_ACCESS",
    "UNSUPPORTED_TENANT",
]

AUTH_STATES = [
    "UNKNOWN",
    "READY",
    "AUTH_REQUIRED",
    "MFA_REQUIRED",
    "WAITING_FOR_MFA",
    "AUTHENTICATED",
    "SESSION_EXPIRED",
    "AUTH_FAILED",
]


@pytest.mark.parametrize("name", REQUIRED_DOCS)
def test_required_document_exists_and_is_substantive(name: str) -> None:
    path = DOCS / name
    assert path.is_file(), f"missing required document: docs/{name}"
    assert len(path.read_text(encoding="utf-8").strip()) > 800, f"docs/{name} looks like a stub"


@pytest.mark.parametrize("name", REQUIRED_ADRS)
def test_required_adr_exists(name: str) -> None:
    path = DOCS / "adr" / name
    assert path.is_file(), f"missing ADR: {name}"
    text = path.read_text(encoding="utf-8")
    assert "## Decision" in text, f"{name} has no Decision section"
    assert "## Consequences" in text, f"{name} has no Consequences section"


def test_readme_exists() -> None:
    assert (ROOT / "README.md").is_file()


@pytest.mark.parametrize(
    "name",
    ["SECURITY.md", "CONTRIBUTING.md", "LICENSE", ".gitignore", ".editorconfig", "pyproject.toml"],
)
def test_repo_baseline_files(name: str) -> None:
    assert (ROOT / name).is_file(), f"missing repo baseline file: {name}"


@pytest.mark.parametrize(
    "name",
    [
        ".github/CODEOWNERS",
        ".github/dependabot.yml",
        ".github/pull_request_template.md",
        ".github/workflows/ci.yml",
    ],
)
def test_github_baseline_files(name: str) -> None:
    assert (ROOT / name).is_file(), f"missing: {name}"
