"""Canonical console entry point for the private M365 browser worker."""

from __future__ import annotations

import json
import sys

from m365_mcp.config import worker_bind_settings
from planner_mcp.errors import ConfigurationError


def main() -> None:
    """Run the worker on the private network through canonical M365 config."""
    import uvicorn

    try:
        host, port = worker_bind_settings()
    except ConfigurationError as exc:
        print(json.dumps(exc.to_dict(), sort_keys=True), file=sys.stderr)
        raise SystemExit(2) from None

    uvicorn.run(
        "m365_browser_worker.app:app",
        host=host,
        port=port,
        log_config=None,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
