#!/usr/bin/env python3
"""Base image digest pinning gate (P-020).

All Docker base images must be pinned by digest. The gate is blocking by default and can
only be relaxed with an explicit, auditable waiver (PLANNER_ENFORCE_DIGEST_PINNING=0).
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROM_RE = re.compile(r"^FROM\s+(\S+)", re.MULTILINE)


def main() -> None:
    """Scan Dockerfiles and emit a pinning report."""
    findings = []
    for dockerfile in sorted((ROOT / "docker").glob("Dockerfile.*")):
        text = dockerfile.read_text(encoding="utf-8")
        for image in FROM_RE.findall(text):
            if image.upper() == "SCRATCH":
                continue
            findings.append(
                {
                    "file": dockerfile.name,
                    "image": image,
                    "pinned_by_digest": "@sha256:" in image,
                }
            )
    unpinned = [f for f in findings if not f["pinned_by_digest"]]
    report = {
        "control": "base-image-digest-pinning",
        "status": "COMPLETE" if not unpinned else "INCOMPLETE",
        "backlog_id": "P-020",
        "enforced": os.getenv("PLANNER_ENFORCE_DIGEST_PINNING", "1") != "0",
        "findings": findings,
    }
    out = ROOT / "artifacts"
    out.mkdir(exist_ok=True)
    (out / "base-image-pinning.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if unpinned and report["enforced"]:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
