"""Console entry point for the browser worker."""

from __future__ import annotations

import os


def main() -> None:
    """Run the worker with uvicorn on the private network only."""
    import uvicorn

    uvicorn.run(
        "planner_browser_worker.app:app",
        host=os.getenv("PLANNER_WORKER_HOST", "127.0.0.1"),
        port=int(os.getenv("PLANNER_WORKER_PORT", "8090")),
        log_config=None,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
