#!/usr/bin/env python3
"""Fail-closed contract and JSON Schema gate for P-001/P-004."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from planner_mcp.version import (  # noqa: E402
    CONTRACT_VERSION,
    PRODUCT_VERSION,
    SCHEMA_VERSION,
    TOOL_CATALOG_VERSION,
    UI_CONTRACT_VERSION,
)

CONTRACTS = ROOT / "contracts"
SCHEMAS = ROOT / "docs" / "schemas" / SCHEMA_VERSION

CONTRACT_SCHEMA_MAP = {
    "agent_card.json": "agent-card.schema.json",
    "capability_manifest.json": "capability-manifest.schema.json",
    "extended_tool_manifest.json": "extended-tool-manifest.schema.json",
    "tool_manifest.json": "tool-manifest.schema.json",
    "ui_contract.json": "ui-contract.schema.json",
    "version.json": "version.schema.json",
}
EXPECTED_TOOLS = (
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
)
SUPPORT_STATES = (
    "UNVERIFIED_LIVE",
    "DISCOVERED",
    "READ_SUPPORTED",
    "MUTATION_SUPPORTED",
    "DEGRADED",
    "BLOCKED",
    "OUT_OF_SCOPE",
)
TRUST_LEVELS = {"untrusted_ui_derived", "system_derived"}
MUTATION_CLASSES = {"READ", "SAFE_WRITE", "GOVERNED_WRITE", "DESTRUCTIVE"}
REVERSIBILITY = {"yes", "with_compensation", "no"}
IDEMPOTENCY_CLASSES = {"naturally_idempotent", "key_required", "non_idempotent"}
APPROVAL_REQUIREMENTS = {"none", "configurable", "always"}
ATTESTATION_STATES = {
    "UNVERIFIED_LIVE",
    "DISCOVERED",
    "UI_ATTESTED",
    "READ_ATTESTED",
    "MUTATION_ATTESTED",
    "SUPPORTED",
    "UI_DRIFT",
}

errors: list[str] = []


def load_json(path: Path, display: str) -> dict[str, Any]:
    """Load a JSON object, recording a stable gate error on failure."""
    if not path.is_file():
        errors.append(f"MISSING JSON: {display}")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"INVALID JSON: {display}: {type(exc).__name__}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"INVALID ROOT: {display} must be a JSON object")
        return {}
    return data


def check_equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        errors.append(f"{label}: expected {expected!r}, found {actual!r}")


def validate_schema(contract_name: str, schema_name: str) -> None:
    """Validate one contract against a versioned Draft 2020-12 schema."""
    contract = load_json(CONTRACTS / contract_name, f"contracts/{contract_name}")
    schema = load_json(SCHEMAS / schema_name, f"docs/schemas/{SCHEMA_VERSION}/{schema_name}")
    if not contract or not schema:
        return

    check_equal(f"{schema_name} $schema", schema.get("$schema"), Draft202012Validator.META_SCHEMA["$id"])
    schema_id = schema.get("$id")
    if not isinstance(schema_id, str) or f"/{SCHEMA_VERSION}/" not in schema_id:
        errors.append(f"{schema_name}: $id must contain /{SCHEMA_VERSION}/")

    try:
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(contract)
    except SchemaError as exc:
        errors.append(f"INVALID SCHEMA: {schema_name}: {exc.validator!r}")
    except ValidationError as exc:
        path = ".".join(str(part) for part in exc.absolute_path) or "<root>"
        errors.append(f"SCHEMA MISMATCH: {contract_name} at {path}: {exc.validator!r}")


def check_tool_sets(base: dict[str, Any], extended: dict[str, Any]) -> None:
    base_tools = base.get("tools")
    ext_tools = extended.get("tools")
    if not isinstance(base_tools, list) or not isinstance(ext_tools, list):
        errors.append("TOOL MANIFESTS: 'tools' must be arrays")
        return

    base_names = [entry.get("name") for entry in base_tools if isinstance(entry, dict)]
    ext_names = [entry.get("name") for entry in ext_tools if isinstance(entry, dict)]
    expected = list(EXPECTED_TOOLS)
    check_equal("ToolManifest tool order/set", base_names, expected)
    check_equal("ExtendedToolManifest tool order/set", ext_names, expected)

    if len(set(base_names)) != len(base_names):
        errors.append("ToolManifest contains duplicate tool names")
    if len(set(ext_names)) != len(ext_names):
        errors.append("ExtendedToolManifest contains duplicate tool names")

    for entry in base_tools:
        if not isinstance(entry, dict):
            errors.append("ToolManifest contains a non-object tool entry")
            continue
        if entry.get("read_only") is not True:
            errors.append(f"{entry.get('name')}: ToolManifest read_only must be true in 0.1.0")

    required = {
        "name",
        "trust_level",
        "mutation_class",
        "reversible",
        "idempotency_class",
        "approval_requirement",
        "attestation_status",
    }
    for entry in ext_tools:
        if not isinstance(entry, dict):
            errors.append("ExtendedToolManifest contains a non-object tool entry")
            continue
        name = str(entry.get("name", "<unknown>"))
        missing = sorted(required - set(entry))
        if missing:
            errors.append(f"{name}: missing ExtendedToolManifest fields {missing}")
            continue
        if entry["trust_level"] not in TRUST_LEVELS:
            errors.append(f"{name}: invalid trust_level {entry['trust_level']!r}")
        if entry["mutation_class"] not in MUTATION_CLASSES:
            errors.append(f"{name}: invalid mutation_class {entry['mutation_class']!r}")
        if entry["mutation_class"] != "READ":
            errors.append(f"{name}: 0.1.0 permits READ tools only")
        if entry["reversible"] not in REVERSIBILITY:
            errors.append(f"{name}: invalid reversible {entry['reversible']!r}")
        if entry["idempotency_class"] not in IDEMPOTENCY_CLASSES:
            errors.append(f"{name}: invalid idempotency_class {entry['idempotency_class']!r}")
        if entry["approval_requirement"] not in APPROVAL_REQUIREMENTS:
            errors.append(
                f"{name}: invalid approval_requirement {entry['approval_requirement']!r}"
            )
        if entry["attestation_status"] not in ATTESTATION_STATES:
            errors.append(f"{name}: invalid attestation_status {entry['attestation_status']!r}")
        if entry["attestation_status"] != "UNVERIFIED_LIVE":
            errors.append(
                f"{name}: Foundation 0.1.0 must not claim live attestation without evidence"
            )

    by_name = {entry.get("name"): entry for entry in ext_tools if isinstance(entry, dict)}
    if by_name.get("planner_auth_start", {}).get("idempotency_class") != "key_required":
        errors.append("planner_auth_start must be key_required (TOOL-021/AUTH-055)")
    resume = by_name.get("planner_auth_resume", {}).get("idempotency_class")
    if resume != "naturally_idempotent":
        errors.append("planner_auth_resume must be naturally_idempotent (TOOL-021)")


def main() -> int:
    docs = {
        name: load_json(CONTRACTS / name, f"contracts/{name}")
        for name in CONTRACT_SCHEMA_MAP
    }

    for contract_name, schema_name in CONTRACT_SCHEMA_MAP.items():
        validate_schema(contract_name, schema_name)

    version = docs["version.json"]
    version_expectations = {
        "product_version": PRODUCT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "ui_contract_version": UI_CONTRACT_VERSION,
        "tool_catalog_version": TOOL_CATALOG_VERSION,
    }
    for key, expected in version_expectations.items():
        check_equal(f"version.json {key}", version.get(key), expected)
    check_equal("version.json read_tools", version.get("read_tools"), 17)
    check_equal("version.json mutation_tools", version.get("mutation_tools"), 0)

    agent = docs["agent_card.json"]
    check_equal("AgentCard version", agent.get("version"), PRODUCT_VERSION)
    check_equal("AgentCard contract_version", agent.get("contract_version"), CONTRACT_VERSION)
    check_equal("AgentCard graph_api_backend", agent.get("graph_api_backend"), False)
    check_equal("AgentCard mutations_supported", agent.get("mutations_supported"), False)
    safety = agent.get("safety")
    if not isinstance(safety, dict) or safety.get("fail_closed") is not True:
        errors.append("AgentCard safety.fail_closed must be true")

    capability = docs["capability_manifest.json"]
    check_equal(
        "CapabilityManifest contract_version",
        capability.get("contract_version"),
        CONTRACT_VERSION,
    )
    check_equal(
        "CapabilityManifest CAP-030 states",
        capability.get("support_levels"),
        list(SUPPORT_STATES),
    )

    base = docs["tool_manifest.json"]
    extended = docs["extended_tool_manifest.json"]
    check_equal("ToolManifest contract_version", base.get("contract_version"), CONTRACT_VERSION)
    check_equal(
        "ToolManifest tool_catalog_version",
        base.get("tool_catalog_version"),
        TOOL_CATALOG_VERSION,
    )
    check_equal(
        "ExtendedToolManifest contract_version",
        extended.get("contract_version"),
        CONTRACT_VERSION,
    )
    check_tool_sets(base, extended)

    ui = docs["ui_contract.json"]
    check_equal("UIContract version", ui.get("ui_contract_version"), UI_CONTRACT_VERSION)
    if ui.get("attested") is not False:
        errors.append("Foundation UIContract must remain unattested until live evidence exists")
    check_equal("UIContract attestation_status", ui.get("attestation_status"), "UNVERIFIED_LIVE")
    selectors = ui.get("selectors")
    if not isinstance(selectors, dict):
        errors.append("UIContract selectors must be an object")
    else:
        for key, selector in selectors.items():
            if not isinstance(selector, dict):
                errors.append(f"UIContract selector {key!r} must be an object")
                continue
            if selector.get("value") is not None:
                errors.append(f"UIContract selector {key!r} must be null before live attestation")
            if selector.get("status") != "UNVERIFIED_LIVE":
                errors.append(f"UIContract selector {key!r} must be UNVERIFIED_LIVE")

    print(f"contracts checked : {len(CONTRACT_SCHEMA_MAP)}")
    print(f"schemas checked   : {len(CONTRACT_SCHEMA_MAP)} @ {SCHEMA_VERSION}")
    print(f"tools checked     : {len(EXPECTED_TOOLS)}")
    print(f"errors            : {len(errors)}")
    for error in errors:
        print(f"  ERROR {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
