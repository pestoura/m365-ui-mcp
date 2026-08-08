"""Internal healthcheck: SQLite + control-plane TCP + worker health.

Deliberately does NOT call GET /mcp, which is not a valid health probe for
Streamable HTTP MCP.
"""

from __future__ import annotations

import json
import socket
import sys
import urllib.error
import urllib.request
from typing import Any

from .config import load_settings
from .state import health as sqlite_health
from .state import initialise


def _tcp_ok(host: str, port: int, timeout: float = 3.0) -> bool:
    probe_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host  # noqa: S104
    try:
        with socket.create_connection((probe_host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _worker_ok(base_url: str, timeout: float = 5.0) -> bool:
    url = f"{base_url.rstrip('/')}/health"
    if not url.startswith(("http://", "https://")):
        return False
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
            if response.status != 200:
                return False
            payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
            return bool(payload.get("ok"))
    except (urllib.error.URLError, OSError, ValueError):
        return False


def check() -> dict[str, Any]:
    """Run all health probes and return a JSON-serialisable report."""
    settings = load_settings()
    initialise(settings.state_path)
    db = sqlite_health(settings.state_path)
    tcp = _tcp_ok(settings.host, settings.port)
    worker = _worker_ok(settings.worker_base_url)
    return {
        "ok": bool(db.get("ok")) and tcp and worker,
        "sqlite": db,
        "control_plane_tcp": tcp,
        "worker_health": worker,
    }


def main() -> None:
    """CLI entry point: exit 0 when healthy, 1 otherwise."""
    report = check()
    sys.stdout.write(json.dumps(report, sort_keys=True) + "\n")
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":  # pragma: no cover
    main()
