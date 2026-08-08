"""Release contract validation: versions, manifests, catalog and canonical docs."""

from __future__ import annotations

from pathlib import Path

from planner_mcp import CONTRACT_VERSION, SCHEMA_VERSION, __version__
from planner_mcp.contracts import load_contract
from planner_mcp.tools import TOOL_NAMES

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DOCS = (
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
)

CANONICAL_CRITICAL_PATH = (
    "P-001 → P-011 → P-014 → P-018 → P-025 → P-026 → P-027 → P-030 → "
    "P-031 → P-050 → P-069 → P-071 → P-073 → P-074"
)


def test_version_alignment() -> None:
    version = load_contract("version")
    assert version["product_version"] == __version__ == "0.1.0"
    assert version["schema_version"] == SCHEMA_VERSION
    assert version["contract_version"] == CONTRACT_VERSION
    assert version["mutation_tools"] == 0
    assert version["read_tools"] == len(TOOL_NAMES)


def test_manifests_match_catalog() -> None:
    manifest = {t["name"] for t in load_contract("tool_manifest")["tools"]}
    extended = {t["name"] for t in load_contract("extended_tool_manifest")["tools"]}
    assert manifest == extended == set(TOOL_NAMES)


def test_agent_card_declares_no_graph_and_no_mutations() -> None:
    card = load_contract("agent_card")
    assert card["graph_api_backend"] is False
    assert card["mutations_supported"] is False


def test_required_docs_and_adrs_exist() -> None:
    missing = [d for d in REQUIRED_DOCS if not (ROOT / "docs" / d).is_file()]
    assert not missing, f"missing docs: {missing}"
    for index in range(1, 9):
        matches = list((ROOT / "docs" / "adr").glob(f"ADR-{index:03d}-*.md"))
        assert len(matches) == 1, f"expected one canonical ADR-{index:03d}, found {matches}"


def test_capability_matrix_columns() -> None:
    text = (ROOT / "docs" / "planner-premium-capabilities.md").read_text(encoding="utf-8")
    for column in (
        "Capability / domain",
        "Tenant / licence observed",
        "UI observed",
        "UIContract attestation",
        "READ validated",
        "MUTATION validated",
        "Support state",
        "Required policy / mutation class",
        "Read-back strategy",
        "Drift / failure behaviour",
        "Evidence / notes",
    ):
        assert column in text


def test_backlog_ids_epics_and_critical_path() -> None:
    text = (ROOT / "docs" / "backlog.md").read_text(encoding="utf-8")
    for index in range(1, 75):
        assert f"P-{index:03d}" in text, f"missing P-{index:03d}"
    for epic in range(1, 11):
        assert f"EPIC-{epic:02d}" in text
    assert CANONICAL_CRITICAL_PATH in text


def test_release_is_read_only_and_catalog_has_17_tools() -> None:
    assert len(TOOL_NAMES) == 17
    extended = load_contract("extended_tool_manifest")["tools"]
    assert all(tool.get("mutation_class") == "READ" for tool in extended)
