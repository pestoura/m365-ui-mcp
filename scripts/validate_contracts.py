"""Static contract and repository invariant validation.

Runs offline. No network, no browser, no tenant. Exit code 1 on any violation.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

from planner_mcp.contracts import CONTRACT_VERSION, AgentCard, CapabilityManifest
from planner_mcp.enums import MutationClass
from planner_mcp.tool_catalog import CATALOG_0_1_0, FORBIDDEN_NAME_FRAGMENTS
from planner_mcp.ui_contract import load_contract

REPO = Path(__file__).resolve().parents[1]
REQUIRED_TOOLS = {
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
}
BACKLOG_KEYS = {f"P-{n:03d}" for n in range(1, 75)}


def check_catalog(errors: list[str]) -> None:
    names = {t.name for t in CATALOG_0_1_0}
    missing = REQUIRED_TOOLS - names
    if missing:
        errors.append(f"catalog: missing required 0.1.0 tools: {sorted(missing)}")
    for tool in CATALOG_0_1_0:
        if tool.mutation_class is not MutationClass.READ:
            errors.append(f"catalog: {tool.name} must be READ in 0.1.0")
        for fragment in FORBIDDEN_NAME_FRAGMENTS:
            if fragment in tool.name:
                errors.append(f"catalog: {tool.name} looks like a generic browser primitive")
    if len(names) != len(CATALOG_0_1_0):
        errors.append("catalog: duplicate tool names")


def check_manifests(errors: list[str]) -> None:
    card = AgentCard()
    if card.graph_is_functional_gate:
        errors.append("agent card: Graph must never be a functional gate")
    if card.contract_version != CONTRACT_VERSION:
        errors.append("agent card: contract version mismatch")
    manifest = CapabilityManifest(tools=CATALOG_0_1_0)
    if manifest.graph_is_functional_gate:
        errors.append("capability manifest: Graph must never be a functional gate")


def check_ui_contracts(errors: list[str]) -> None:
    root = REPO / "browser" / "selectors"
    files = sorted(root.glob("*.yaml"))
    if not files:
        errors.append("ui contract: no contract documents found under browser/selectors")
    for path in files:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        contract = load_contract(payload)
        for selector in contract.selectors:
            if not selector.is_attested():
                errors.append(f"ui contract: {path.name}:{selector.id} has no attestation")
            elif not selector.is_usable():
                errors.append(f"ui contract: {path.name}:{selector.id} has no usable locator")


def check_backlog(errors: list[str]) -> None:
    path = REPO / "docs" / "backlog.md"
    if not path.exists():
        errors.append("backlog: docs/backlog.md is missing")
        return
    text = path.read_text(encoding="utf-8")
    found = set(re.findall(r"\bP-\d{3}\b", text))
    missing = BACKLOG_KEYS - found
    if missing:
        errors.append(f"backlog: missing keys {sorted(missing)[:10]} (total {len(missing)})")


def check_docs(errors: list[str]) -> None:
    required = [
        "vision",
        "architecture",
        "threat-model",
        "security",
        "governance",
        "authentication-and-mfa",
        "privacy-boundary",
        "planner-premium-capabilities",
        "tool-catalog",
        "reconciliation",
        "idempotency",
        "state-model",
        "ui-contract",
        "browser-worker",
        "observability",
        "testing",
        "acceptance",
        "deployment",
        "cloudflare-mcp-portal",
        "hermes-integration",
        "reporting",
        "roadmap",
        "backlog",
        "release-process",
        "traceability",
        "definition-of-done",
    ]
    for name in required:
        if not (REPO / "docs" / f"{name}.md").exists():
            errors.append(f"docs: docs/{name}.md is missing")
    for n in range(1, 9):
        matches = list((REPO / "docs" / "adr").glob(f"ADR-{n:03d}-*.md"))
        if not matches:
            errors.append(f"docs: ADR-{n:03d} is missing")


def main() -> int:
    errors: list[str] = []
    check_catalog(errors)
    check_manifests(errors)
    check_ui_contracts(errors)
    check_backlog(errors)
    check_docs(errors)
    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1
    print("contract validation OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
