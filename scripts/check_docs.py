#!/usr/bin/env python3
"""Fail-closed documentation gate for the canonical Planner MCP A1 specification."""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

CANONICAL_DOCS = [
    "architecture.md",
    "threat-model.md",
    "security.md",
    "governance.md",
    "privacy-boundary.md",
    "authentication-and-mfa.md",
    "ui-contract.md",
    "browser-worker.md",
    "planner-premium-capabilities.md",
    "tool-catalog.md",
]

A1_3_DOCS = [
    "reconciliation.md",
    "idempotency.md",
    "state-model.md",
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

ADRS = {
    "ADR-001-browser-automation.md": "001",
    "ADR-002-control-plane-worker-separation.md": "002",
    "ADR-003-reconciliation-first.md": "003",
    "ADR-004-human-in-loop-mfa.md": "004",
    "ADR-005-hermes-bridge-foundation.md": "005",
    "ADR-006-ui-contract-attestation.md": "006",
    "ADR-007-professional-profile-boundary.md": "007",
    "ADR-008-graph-api-non-dependency.md": "008",
}

TARGETS = CANONICAL_DOCS + A1_3_DOCS
CANONICAL_CRITICAL_PATH = (
    "P-001 → P-011 → P-014 → P-018 → P-025 → P-026 → P-027 → P-030 → "
    "P-031 → P-050 → P-069 → P-071 → P-073 → P-074"
)

# Original A1 namespaces plus namespaces that A1.3 may define explicitly.
DEF_PREFIXES = (
    "ARCH", "SEC", "PRIV", "GOV", "THR", "AUTH", "UI", "WORKER", "CAP", "TOOL",
    "REC", "RECON", "IDEM", "STATE", "OBS", "TEST", "ACC", "DEPLOY", "CF",
    "HERMES", "REPORT", "ROADMAP", "BACKLOG", "REL", "TRACE", "DOD",
)
PREFIX_ALT = "|".join(sorted(DEF_PREFIXES, key=len, reverse=True))
ID_RE = re.compile(rf"\b({PREFIX_ALT})-(\d{{3}})\b")
DEF_RE = re.compile(
    rf"^(?:\|\s*)?\*\*(?:TB-\d+\s*/\s*)?({PREFIX_ALT})-(\d{{3}})\b",
    re.MULTILINE,
)
LINK_RE = re.compile(r"\[[^\]]*\]\((?!https?://|mailto:)([^)#]+)(?:#[^)]*)?\)")
ADR_REF_RE = re.compile(r"\bADR-(\d{3,4})\b")
LEGACY_R_RE = re.compile(r"\bR-\d{2,3}\b")

errors: list[str] = []
warnings: list[str] = []
defined: set[str] = set()
referenced: dict[str, set[str]] = {}


def validate_text(path: Path, display: str, *, require_vision: bool = False) -> None:
    if not path.is_file():
        errors.append(f"MISSING FILE: {display}")
        return

    text = path.read_text(encoding="utf-8")

    for target in LINK_RE.findall(text):
        if not target or ":" in target.split("/", 1)[0]:
            continue
        resolved = (path.parent / target).resolve()
        if not resolved.exists():
            errors.append(f"BROKEN LINK: {display} -> {target}")

    if require_vision and "vision.md" not in text:
        errors.append(f"NO VISION CROSS-LINK: {display}")

    local_defs = [f"{p}-{n}" for p, n in DEF_RE.findall(text)]
    for dupe in sorted(i for i, c in Counter(local_defs).items() if c > 1):
        errors.append(f"DUPLICATE ID DEFINITION: {dupe} in {display}")
    for rid in local_defs:
        if rid in defined:
            errors.append(f"DUPLICATE GLOBAL ID DEFINITION: {rid} (seen again in {display})")
        defined.add(rid)

    for prefix, num in ID_RE.findall(text):
        referenced.setdefault(f"{prefix}-{num}", set()).add(display)

    for bad in (
        "BEGIN PRIVATE KEY",
        "Authorization: Bearer ey",
        "BEGIN OPENSSH PRIVATE KEY",
    ):
        if bad in text:
            errors.append(f"POSSIBLE SECRET IN DOC: {display} contains {bad!r}")

    # A1 has exactly ADR-001..ADR-008. Four-digit ADR-000x references came from a
    # parallel/non-canonical specification and must never re-enter A1.
    for number in ADR_REF_RE.findall(text):
        if len(number) != 3 or not 1 <= int(number) <= 8:
            errors.append(f"INVALID ADR REFERENCE: {display} contains ADR-{number}")

    # R-nn was an unrelated traceability namespace introduced by the parallel
    # specification. Canonical requirements retain their named namespaces.
    for legacy in sorted(set(LEGACY_R_RE.findall(text))):
        errors.append(f"LEGACY REQUIREMENT REFERENCE: {display} contains {legacy}")

    # Detect the old semantic numbering from the parallel branch even when the
    # numeric shape itself is valid.
    for lineno, line in enumerate(text.splitlines(), start=1):
        low = line.lower()
        if "adr-006" in low and "graph" in low:
            errors.append(f"LEGACY ADR MAPPING: {display}:{lineno} maps Graph to ADR-006; use ADR-008")
        if "adr-007" in low and ("ui contract" in low or "uicontract" in low or "ui-contract" in low):
            errors.append(f"LEGACY ADR MAPPING: {display}:{lineno} maps UIContract to ADR-007; use ADR-006")
        if "adr-008" in low and any(
            term in low
            for term in ("personal device", "privacy boundary", "enrolment", "enrollment", "managed device")
        ):
            errors.append(f"LEGACY ADR MAPPING: {display}:{lineno} maps profile/privacy to ADR-008; use ADR-007")


for name in TARGETS:
    validate_text(DOCS / name, f"docs/{name}", require_vision=name in CANONICAL_DOCS)

adr_dir = DOCS / "adr"
for filename, number in ADRS.items():
    path = adr_dir / filename
    display = f"docs/adr/{filename}"
    validate_text(path, display)
    if path.is_file():
        first = path.read_text(encoding="utf-8").splitlines()[0:1]
        expected = f"# ADR-{number}"
        if not first or not first[0].startswith(expected):
            errors.append(f"ADR HEADING MISMATCH: {display} must start with {expected!r}")

if adr_dir.is_dir():
    actual = {p.name for p in adr_dir.glob("ADR-00[1-8]-*.md")}
    expected = set(ADRS)
    for extra in sorted(actual - expected):
        errors.append(f"UNEXPECTED ADR FILE: docs/adr/{extra}")

# Every recognized requirement reference must resolve to a definition.
for rid, where in sorted(referenced.items()):
    if rid not in defined:
        warnings.append(f"UNDEFINED ID REFERENCE: {rid} (referenced in {', '.join(sorted(where))})")

# Backlog integrity: exactly P-001..P-074 as item headings and EPIC-01..EPIC-10.
backlog = DOCS / "backlog.md"
if backlog.is_file():
    text = backlog.read_text(encoding="utf-8")
    item_keys = re.findall(r"^###\s+(P-\d{3})\b", text, flags=re.MULTILINE)
    expected_keys = [f"P-{n:03d}" for n in range(1, 75)]
    if item_keys != expected_keys:
        missing = sorted(set(expected_keys) - set(item_keys))
        extra = sorted(set(item_keys) - set(expected_keys))
        errors.append(
            f"BACKLOG KEY SET/ORDER INVALID: count={len(item_keys)} missing={missing} extra={extra}"
        )
    for key, count in Counter(item_keys).items():
        if count != 1:
            errors.append(f"DUPLICATE BACKLOG ITEM: {key} appears {count} times")

    epic_ids = re.findall(r"^##\s+(EPIC-\d{2})\b", text, flags=re.MULTILINE)
    expected_epics = [f"EPIC-{n:02d}" for n in range(1, 11)]
    if epic_ids != expected_epics:
        errors.append(f"EPIC SET/ORDER INVALID: found={epic_ids}")

    for raw in re.findall(r"\bP-(\d{1,3})\b", text):
        if len(raw) != 3:
            errors.append(f"NON-ZERO-PADDED BACKLOG REFERENCE: P-{raw}")

# The same critical path must be present in the three canonical planning surfaces.
for rel in ("backlog.md", "roadmap.md", "traceability.md"):
    path = DOCS / rel
    if path.is_file() and CANONICAL_CRITICAL_PATH not in path.read_text(encoding="utf-8"):
        errors.append(f"CRITICAL PATH MISMATCH: docs/{rel}")

print(f"files checked      : {len(TARGETS) + len(ADRS)}")
print(f"requirement IDs    : {len(defined)} defined, {len(referenced)} distinct referenced")
print(f"errors             : {len(errors)}")
print(f"warnings           : {len(warnings)}")
for e in errors:
    print(f"  ERROR   {e}")
for w in warnings:
    print(f"  WARN    {w}")

# A1 is GREEN only with errors=0 AND warnings=0.
sys.exit(1 if errors or warnings else 0)
