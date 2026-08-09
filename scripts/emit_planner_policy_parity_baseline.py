"""Emit the canonical PLN-MIG-009 Planner policy parity baseline to stdout."""

from __future__ import annotations

import json

from m365_mcp.apps.planner.policy_parity import (
    policy_parity_digest,
    policy_parity_snapshot,
)
from m365_mcp.apps.planner.public_surface import PLANNER_PUBLIC_TOOL_NAMES


def main() -> None:
    snapshot = policy_parity_snapshot()
    document = {
        "tools": list(PLANNER_PUBLIC_TOOL_NAMES),
        "live_support_claimed": False,
        "mode": "mock",
        "governance": snapshot,
        "digest": policy_parity_digest(snapshot),
    }
    print(json.dumps(document, indent=2))


if __name__ == "__main__":
    main()
