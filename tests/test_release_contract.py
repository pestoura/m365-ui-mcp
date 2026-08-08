"""Release contract validation: versions, manifests, catalog and docs."""

from __future__ import annotations

import json
from pathlib import Path

from planner_mcp import CONTRACT_VERSION, SCHEMA_VERSION, __version__
from planner_mcp.contracts import load_contract
from planner_mcp.tools import TOOL_NAMES

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DOCS = (
    "vision.md", "architecture.md", "threat-model.md", "security.md", "governance.md",
    "authentication-and-mfa.md", "privacy-boundary.md", "planner-premium-capabilities.md",
    "tool-catalog.md", "reconciliation.md", "idempotency.md", "state-model.md",
    "ui-contract.md", "browser-worker.md", "observability.md", "testing.md",
    "acceptance.md", "deployment.md", "cloudflare-mcp-portal.md",
    "hermes-integration.md", "reporting.md", "roadmap.md", "backlog.md",
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


def test_required_docs_exist() -> None:
    missing = [d for d in REQUIRED_DOCS if not (ROOT / "docs" / d).is_file()]
    assert not missing, f"missing docs: {missing}"
    for index in range(1, 6):
        matches = list((ROOT / "docs" / "adr").glob(f"ADR-00{index}-*.md"))
        assert matches, f"missing ADR-00{index}"


def test_capability_matrix_columns() -> None:
    text = (ROOT / "docs" / "planner-premium-capabilities.md").read_text(encoding="utf-8")
    for column in (
        "capability", "tenant/license availability", "UI observed", "UIContract status",
        "read attestation", "mutation attestation", "support level", "evidence/notes",
    ):
        assert column in text


def test_backlog_ids_and_critical_path() -> None:
    text = (ROOT / "docs" / "backlog.md").read_text(encoding="utf-8")
    for index in range(1, 75):
        assert f"P-{index:03d}" in text, f"missing P-{index:03d}"
    for epic in range(1, 11):
        assert f"EPIC-{epic:02d}" in text
    critical = ["P-001", "P-011", "P-014", "P-018", "P-025", "P-026", "P-027",
                "P-030", "P-031", "P-050", "P-069", "P-071", "P-073", "P-074"]
    assert " -> ".join(critical) in text


def test_backlog_json_dependencies_zero_padded() -> None:
    data = json.loads((ROOT / "docs" / "backlog.json").read_text(encoding="utf-8"))
    ids = {item["id"] for item in data["items"]}
    assert len(ids) == 74
    for item in data["items"]:
        for dep in item["depends_on"]:
            assert len(dep) == 5 and dep.startswith("P-") and dep[2:].isdigit()
            assert dep in ids
    p030 = next(i for i in data["items"] if i["id"] == "P-030")
    assert "P-019" in p030["depends_on"] and "P-025" in p030["depends_on"]
