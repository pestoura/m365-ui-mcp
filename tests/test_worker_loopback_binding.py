"""NET-001 — Worker host exposure is loopback-only and the socket-level guard is preserved.

Two distinct proofs:

* The compose deployment publishes the browser worker on the host ONLY at
  ``127.0.0.1:8090`` (never ``0.0.0.0``, never a public interface). This is the
  minimal network change that lets a host-local operator reach the worker at
  ``127.0.0.1:8090`` while keeping every other interface closed.
* The worker's socket-level loopback admission guard (``is_loopback_peer``) keeps
  rejecting non-loopback socket peers, so publishing the port does not widen the
  admission policy of any operator-only endpoint.
"""

from __future__ import annotations

import re
from pathlib import Path

from m365_browser_worker.bootstrap_navigation import is_loopback_peer

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docker-compose.yml"

_LOOPBACK_PEERS = ("127.0.0.1", "::1", "::ffff:127.0.0.1")
_NON_LOOPBACK_PEERS = ("100.98.227.66", "192.168.1.113", "172.18.0.7", "10.0.0.5")


def _worker_block() -> str:
    text = COMPOSE.read_text(encoding="utf-8")
    services = text.split("services:", maxsplit=1)[1].split("\nnetworks:", maxsplit=1)[0]
    current = ""
    blocks: dict[str, str] = {}
    for line in services.splitlines():
        match = re.match(r"^  ([a-z0-9-]+):\s*$", line)
        if match:
            current = match.group(1)
            blocks[current] = ""
            continue
        if current:
            blocks[current] += line + "\n"
    return blocks["browser-worker"]


def test_compose_worker_publishes_loopback_8090_only() -> None:
    worker = _worker_block()
    # Parse only declared port mappings (quoted "- HOST:CONTAINER"), not comments.
    ports = re.findall(r'^\s*-\s*"([^"]+)"', worker, flags=re.MULTILINE)
    assert ports == ["127.0.0.1:8090:8090"], ports
    assert not any(p.startswith("0.0.0.0") for p in ports)  # noqa: S104 - asserting absence of all-interfaces bind


def test_worker_loopback_guard_accepts_only_loopback_peers() -> None:
    for peer in _LOOPBACK_PEERS:
        assert is_loopback_peer(peer) is True, peer
    # Leading/trailing whitespace and case must not defeat the guard.
    assert is_loopback_peer(" 127.0.0.1 ") is True
    for peer in _NON_LOOPBACK_PEERS:
        assert is_loopback_peer(peer) is False, peer
    # Missing / header-derived values are never loopback.
    assert is_loopback_peer(None) is False
    assert is_loopback_peer("") is False
