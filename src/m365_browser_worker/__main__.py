"""Canonical console entry point for the private M365 browser worker."""

from __future__ import annotations

import os


def main() -> None:
    """Run the worker on the private network through the M365 namespace."""
    import uvicorn

    uvicorn.run(
        "m365_browser_worker.app:app",
        host=os.getenv("PLANNER_WORKER_HOST", "127.0.0.1"),
        port=int(os.getenv("PLANNER_WORKER_PORT", "8090")),
        log_config=None,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
