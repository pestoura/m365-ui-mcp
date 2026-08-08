"""Guard: assert the running environment cannot reach a live Microsoft tenant.

Used by the isolated acceptance job. CI must never authenticate to, read from or mutate a
real Planner tenant; live acceptance is a separate, manual, read-only procedure.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

FORBIDDEN_ENV = (
    "MICROSOFT_PASSWORD",
    "PLANNER_PASSWORD",
    "ENTRA_PASSWORD",
    "PLANNER_TENANT_ID",
    "PLANNER_SESSION_STATE",
    "PLANNER_BROWSER_PROFILE",
)
FORBIDDEN_PATHS = (
    Path("browser-profile"),
    Path("profiles"),
    Path("data/sessions"),
)


def main() -> int:
    errors: list[str] = []

    if os.environ.get("PLANNER_MCP_LIVE_TENANT") != "forbidden":
        errors.append("PLANNER_MCP_LIVE_TENANT must be set to 'forbidden' in automation")

    for name in FORBIDDEN_ENV:
        if os.environ.get(name):
            errors.append(f"environment variable {name} must not be set in automation")

    for path in FORBIDDEN_PATHS:
        if path.exists():
            errors.append(f"session/profile artefact present in workspace: {path}")

    for error in errors:
        print(f"FAIL {error}")
    if errors:
        return 1

    print("no live tenant configuration reachable; acceptance runs against the mock UI only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
