#!/usr/bin/env python3
"""Sanity check for planner-mcp docs: relative links, requirement IDs, cross-references."""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"
TARGETS = [
    "architecture.md",
    "threat-model.md",
    "security.md",
    "governance.md",
    "privacy-boundary.md",
]
ID_RE = re.compile(r"\b(ARCH|SEC|PRIV|GOV|THR|TB|A|AC)-(\d{2,3})\b")
# A definition is a requirement ID opening a bold span at the start of a line or of a
# table cell, e.g. "**SEC-001 — ...", "| **THR-001** | ..." or "| **TB-1 / ARCH-050** | ...".
DEF_RE = re.compile(
    r"^(?:\|\s*)?\*\*(?:TB-\d+\s*/\s*)?(ARCH|SEC|PRIV|GOV|THR)-(\d{3})\b",
    re.MULTILINE,
)
LINK_RE = re.compile(r"\[[^\]]*\]\((?!https?://)([^)#]+)(?:#[^)]*)?\)")

errors: list[str] = []
warnings: list[str] = []
defined: set[str] = set()
referenced: dict[str, set[str]] = {}

for name in TARGETS:
    path = DOCS / name
    if not path.is_file():
        errors.append(f"MISSING FILE: docs/{name}")
        continue
    text = path.read_text(encoding="utf-8")

    # 1. relative link targets must exist
    for target in LINK_RE.findall(text):
        resolved = (path.parent / target).resolve()
        if not resolved.exists():
            errors.append(f"BROKEN LINK: docs/{name} -> {target}")

    # 2. must cross-link vision.md
    if "vision.md" not in text:
        errors.append(f"NO VISION CROSS-LINK: docs/{name}")

    # 3. collect requirement ID definitions (bold at line start / table cell)
    local_defs = [f"{p}-{n}" for p, n in DEF_RE.findall(text)]
    dupes = [i for i, c in Counter(local_defs).items() if c > 1]
    for dupe in sorted(dupes):
        errors.append(f"DUPLICATE ID DEFINITION: {dupe} in docs/{name}")
    defined.update(local_defs)

    # 4. collect all references
    for prefix, num in ID_RE.findall(text):
        if prefix in {"ARCH", "SEC", "PRIV", "GOV", "THR"} and len(num) == 3:
            referenced.setdefault(f"{prefix}-{num}", set()).add(name)

    # 5. forbidden literal secret-looking content in docs
    for bad in ("BEGIN PRIVATE KEY", "Authorization: Bearer ey"):
        if bad in text:
            errors.append(f"POSSIBLE SECRET IN DOC: docs/{name} contains {bad!r}")

# 6. every referenced ID must be defined somewhere (ranges in index tables excluded)
RANGE_HINT = re.compile(r"…|\.\.\.")
for rid, where in sorted(referenced.items()):
    if rid not in defined:
        warnings.append(f"UNDEFINED ID REFERENCE: {rid} (referenced in {', '.join(sorted(where))})")

print(f"files checked      : {len(TARGETS)}")
print(f"requirement IDs    : {len(defined)} defined, {len(referenced)} distinct referenced")
print(f"errors             : {len(errors)}")
print(f"warnings           : {len(warnings)}")
for e in errors:
    print(f"  ERROR   {e}")
for w in warnings:
    print(f"  WARN    {w}")

sys.exit(1 if errors else 0)
