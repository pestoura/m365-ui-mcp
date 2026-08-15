"""AUTH-115: prove the worker service DNS alias `browser-worker` is declared canonic

The control-plane reaches the browser-worker exclusively via the service DNS name
`http://browser-worker:8090` (PLANNER_WORKER_URL / M365_WORKER_URL). Docker's
embedded DNS resolves that name ONLY for containers that are members of the same
compose stack. The alias must therefore be declared explicitly on the worker
service's networks in `docker-compose.yml`; relying on the auto-generated container
name is fragile (a worker started by a manual `docker run` never registers it, which
makes the control-plane healthcheck fail with `worker_health: false` / NXDOMAIN).

This test loads the rendered compose configuration and asserts the durable contract
without requiring a running Docker daemon, so it runs in CI and locally.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"

EXPECTED_WORKER_ALIAS = "browser-worker"
WORKER_URL = "http://browser-worker:8090"


def _load_compose_config() -> dict:
    """Load the rendered compose config via `docker compose config` if available,
    otherwise parse the raw YAML (valid because the alias contract is static)."""
    env = dict(os.environ)
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "docker", "compose", "config"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return yaml.safe_load(proc.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    # Fall back to raw YAML parse (compose short/long syntax is valid YAML).
    with open(COMPOSE_FILE, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _service_networks(compose: dict, service: str) -> dict:
    """Normalize the service `networks` mapping into {net_name: {aliases: [..]}}."""
    svc = compose["services"][service]
    raw = svc.get("networks", {})
    normalized: dict[str, dict] = {}
    if isinstance(raw, list):
        for item in raw:
            normalized[item] = {}
    else:
        for name, spec in raw.items():
            normalized[name] = spec or {}
    return normalized


def test_worker_service_declares_canonical_dns_alias():
    compose = _load_compose_config()
    assert "browser-worker" in compose["services"], "browser-worker service missing"
    nets = _service_networks(compose, "browser-worker")
    # The alias must be present on the private control-plane/worker network.
    assert "browser-internal" in nets, "worker not attached to browser-internal"
    aliases = nets["browser-internal"].get("aliases") or []
    assert EXPECTED_WORKER_ALIAS in aliases, (
        f"canonical alias {EXPECTED_WORKER_ALIAS!r} missing on browser-internal; "
        f"got {aliases!r}"
    )


def _control_plane_env(compose: dict) -> dict:
    cp = compose["services"]["control-plane"]
    env = cp.get("environment", {})
    env_dict: dict[str, str] = {}
    if isinstance(env, list):
        for item in env:
            if isinstance(item, str) and "=" in item:
                k, v = item.split("=", 1)
                env_dict[k] = v
    else:
        for k, v in env.items():
            env_dict[k] = v
    return env_dict


def test_control_plane_points_at_canonical_worker_dns():
    compose = _load_compose_config()
    env_dict = _control_plane_env(compose)
    # The base compose always defines PLANNER_WORKER_URL pointing at the canonical
    # service DNS alias (the worker URL is overlayed to M365_WORKER_URL in live mode,
    # but both must target `browser-worker`, never a container-name or IP).
    assert env_dict.get("PLANNER_WORKER_URL") == WORKER_URL, (
        f"control-plane PLANNER_WORKER_URL must be {WORKER_URL}; "
        f"got {env_dict.get('PLANNER_WORKER_URL')!r}"
    )
    # When M365_WORKER_URL is declared (e.g. via the live overlay), it must also use
    # the canonical alias — never a brittle container name or IP.
    if "M365_WORKER_URL" in env_dict:
        assert env_dict["M365_WORKER_URL"] == WORKER_URL, (
            f"control-plane M365_WORKER_URL must be {WORKER_URL}; "
            f"got {env_dict.get('M365_WORKER_URL')!r}"
        )


def test_overlay_preserves_canonical_worker_dns():
    """If a live overlay exists beside the base compose, it must keep targeting the
    canonical `browser-worker` alias (regression guard against container-name hardcoding)."""
    overlay = REPO_ROOT / "compose.live.yml"
    if not overlay.exists():
        pytest.skip("no compose.live.yml overlay present")
    with open(overlay, "r", encoding="utf-8") as fh:
        overlay_cfg = yaml.safe_load(fh)
    cp_env = overlay_cfg.get("services", {}).get("control-plane", {}).get(
        "environment", {}
    )
    env_dict = {}
    for item in cp_env if isinstance(cp_env, list) else cp_env.items():
        if isinstance(item, str) and "=" in item:
            k, v = item.split("=", 1)
            env_dict[k] = v
        elif isinstance(item, tuple):
            env_dict[item[0]] = item[1]
    for key in ("PLANNER_WORKER_URL", "M365_WORKER_URL"):
        if key in env_dict:
            assert env_dict[key] == WORKER_URL, (
                f"overlay {key} must keep canonical alias {WORKER_URL}; "
                f"got {env_dict[key]!r}"
            )


def test_worker_attached_to_control_plane_network():
    """The worker and control-plane must share the browser-internal network so the
    embedded DNS alias is resolvable from the control-plane."""
    compose = _load_compose_config()
    worker_nets = set(_service_networks(compose, "browser-worker").keys())
    cp_nets = set(_service_networks(compose, "control-plane").keys())
    assert "browser-internal" in worker_nets
    assert "browser-internal" in cp_nets
    assert worker_nets & cp_nets, "worker and control-plane share no network"
