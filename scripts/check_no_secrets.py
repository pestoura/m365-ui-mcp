#!/usr/bin/env python3
"""Repository invariant: no credential material is committed.

Fails the build if a tracked file looks like it contains a password, cookie jar,
bearer token, JWT, private key or Playwright storage state.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_PATH_PATTERNS = (
    re.compile(r"storage_state.*\.json$"),
    re.compile(r"cookies?\.(json|txt)$"),
    re.compile(r"\.pem$|\.pfx$|\.p12$|\.key$"),
    re.compile(r"(^|/)\.env$"),
)

FORBIDDEN_CONTENT_PATTERNS = (
    ("private_key_block", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("bearer_token", re.compile(r"(?i)authorization\s*[:=]\s*['\"]?bearer\s+\S{20,}")),
    (
        "password_assignment",
        re.compile(r"(?i)\b(password|passwd|client_secret)\s*[:=]\s*['\"][^'\"]{6,}['\"]"),
    ),
)

TEXT_SUFFIXES = {".py", ".md", ".json", ".yml", ".yaml", ".toml", ".txt", ".cfg", ".ini", ""}


def tracked_files() -> list[str]:
    """Return git-tracked files."""
    out = subprocess.run(  # noqa: S603
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True  # noqa: S607
    )
    return [line for line in out.stdout.splitlines() if line]


def main() -> None:
    """Run the invariant check."""
    violations: list[dict[str, str]] = []
    for rel in tracked_files():
        path = ROOT / rel
        for pattern in FORBIDDEN_PATH_PATTERNS:
            if pattern.search(rel):
                violations.append({"file": rel, "rule": "forbidden_path"})
        if path.suffix not in TEXT_SUFFIXES or not path.is_file():
            continue
        if rel == "scripts/check_no_secrets.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for name, pattern in FORBIDDEN_CONTENT_PATTERNS:
            if pattern.search(text):
                violations.append({"file": rel, "rule": name})
    report = {"control": "no-committed-secrets", "violations": violations,
              "status": "PASS" if not violations else "FAIL"}
    print(json.dumps(report, indent=2, sort_keys=True))
    sys.exit(0 if not violations else 1)


if __name__ == "__main__":
    main()
