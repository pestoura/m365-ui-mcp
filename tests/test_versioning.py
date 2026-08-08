"""P-004 contract and schema versioning acceptance tests."""

from __future__ import annotations

import json
from importlib.metadata import version as installed_version
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from planner_mcp.version import (
    CONTRACT_VERSION,
    PRODUCT_VERSION,
    SCHEMA_VERSION,
    TOOL_CATALOG_VERSION,
    UI_CONTRACT_VERSION,
    __version__,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "docs" / "schemas" / SCHEMA_VERSION

SCHEMAS = (
    "agent-card.schema.json",
    "capability-manifest.schema.json",
    "extended-tool-manifest.schema.json",
    "tool-manifest.schema.json",
    "ui-contract.schema.json",
    "version.schema.json",
)


def test_single_version_source_drives_package_metadata() -> None:
    assert __version__ == PRODUCT_VERSION == "0.1.0"
    assert CONTRACT_VERSION == SCHEMA_VERSION == PRODUCT_VERSION
    assert UI_CONTRACT_VERSION == TOOL_CATALOG_VERSION == PRODUCT_VERSION
    assert installed_version("planner-mcp") == PRODUCT_VERSION


def test_all_schema_ids_are_versioned_and_valid() -> None:
    for schema_name in SCHEMAS:
        schema = json.loads((SCHEMA_DIR / schema_name).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert f"/{SCHEMA_VERSION}/" in schema["$id"]


def test_version_mismatch_is_rejected_by_schema() -> None:
    schema = json.loads((SCHEMA_DIR / "version.schema.json").read_text(encoding="utf-8"))
    contract = json.loads((ROOT / "contracts" / "version.json").read_text(encoding="utf-8"))
    contract["product_version"] = "9.9.9"

    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(contract)
