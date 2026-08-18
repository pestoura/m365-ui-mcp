"""AUTH-115 regression gate: the live browser-worker MUST be compose-managed.

This is the durable guard against the WORKER_UNAVAILABLE regression seen after
PR #634: a worker started by a manual `docker run` (outside the compose stack)
never receives the `com.docker.compose.*` project labels, and on the
`browser-internal` network it registers NO `browser-worker` DNS alias. The
control-plane reaches the worker exclusively via `http://browser-worker:8090`
(PLANNER_WORKER_URL / M365_WORKER_URL), so the missing alias produces a
ConnectError / NXDOMAIN and the control-plane healthcheck fails
(`worker_health: false`).

The durable fix is NOT to hardcode the container name into the control-plane;
it is to keep the worker compose-managed by the SAME project/path/overlay as the
control-plane so Docker emits the alias automatically. This test proves both the
live runtime state and the deployment-path contract.

These tests inspect the live Docker daemon. They SKIP (not fail) when there is
no Docker daemon, no worker container, or no control-plane to resolve against —
so they are safe in CI, but they are authoritative on the deployment host.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

# Resolve the docker executable to an absolute path so the static analysis gate
# (S607) treats the subprocess invocation as a trusted binary.
DOCKER_BIN = shutil.which("docker")

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"

# The canonical deployment helper lives on the deployment host at
# ~/.cache/m365-deploy/deploy-local-runtime.sh (intentionally outside the Git
# repo). We resolve it from a few candidate locations so the gate is meaningful
# on the deployment host and SKIPs cleanly in CI where the file is absent.
DEPLOY_SCRIPT_CANDIDATES = [
    Path.home() / ".cache" / "m365-deploy" / "deploy-local-runtime.sh",
    REPO_ROOT / ".cache" / "m365-deploy" / "deploy-local-runtime.sh",
    REPO_ROOT / "scripts" / "deploy-local-runtime.sh",
]


def _resolve_deploy_script() -> Path | None:
    for cand in DEPLOY_SCRIPT_CANDIDATES:
        if cand.is_file():
            return cand
    return None

EXPECTED_PROJECT = "planner-mcp"
WORKER_IMAGE = "planner-browser-worker:0.1.0"
INTERNAL_NET = "planner-mcp_browser-internal"
WORKER_ALIAS = "browser-worker"


def _docker_available() -> bool:
    return DOCKER_BIN is not None


def _run_json(args: list[str]) -> Any | None:
    if not _docker_available():
        return None
    try:
        proc = subprocess.run(  # noqa: S603
            [DOCKER_BIN, *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def _find_worker_container() -> str | None:
    """Return the live worker container id/name, or None if not running."""
    ps = _run_json(
        ["ps", "--filter", f"ancestor={WORKER_IMAGE}", "--format", "{{json .}}"]
    )
    if ps is None:
        # ancestor filter may miss a renamed tag; fall back to name pattern.
        ps = _run_json(
            [
                "ps",
                "--filter",
                "name=planner-mcp-browser-worker",
                "--format",
                "{{json .}}",
            ]
        )
    if not ps:
        return None
    items = ps if isinstance(ps, list) else [ps]
    for item in items:
        if isinstance(item, dict) and item.get("Names"):
            return item["Names"]
    return None


def _network_has_alias(network: str, container: str, alias: str) -> bool:
    """Best-effort alias check; on Docker versions that omit the Aliases key we
    treat the network membership as provisionally present and rely on the DNS
    resolution test below as the authoritative proof."""
    insp = _run_json(["network", "inspect", network])
    if not insp:
        return False
    containers = insp[0].get("Containers", {})
    for meta in containers.values():
        if meta.get("Name") == container:
            aliases = meta.get("Aliases") or []
            if alias in aliases:
                return True
    return False


def _control_plane_resolves(alias: str) -> bool:
    """Authoritative proof: does the control-plane container resolve the alias?"""
    cp = _find_control_plane()
    if not cp:
        return False
    proc = subprocess.run(  # noqa: S603
        [DOCKER_BIN, "exec", cp, "getent", "hosts", alias],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return proc.returncode == 0 and alias in proc.stdout


def _find_control_plane() -> str | None:
    ps = _run_json(
        [
            "ps",
            "--filter",
            "name=planner-mcp-control-plane",
            "--format",
            "{{json .}}",
        ]
    )
    if not ps:
        return None
    items = ps if isinstance(ps, list) else [ps]
    for item in items:
        if isinstance(item, dict) and item.get("Names"):
            return item["Names"]
    return None


def _inspect_labels(container: str) -> dict:
    insp = _run_json(["inspect", container])
    if not insp:
        return {}
    return (insp[0].get("Config", {}).get("Labels", {})) or {}


@pytest.mark.skipif(
    not _docker_available(), reason="docker daemon not available"
)
def test_worker_live_container_is_compose_managed():
    """The running browser-worker must carry the compose project label, proving
    it was brought up by compose and not by a manual `docker run`."""
    worker = _find_worker_container()
    if worker is None:
        pytest.skip("no live browser-worker container running")
    labels = _inspect_labels(worker)
    project = labels.get("com.docker.compose.project")
    assert project == EXPECTED_PROJECT, (
        f"live worker {worker!r} is NOT compose-managed: "
        f"com.docker.compose.project={project!r} (expected {EXPECTED_PROJECT!r}). "
        f"A manual `docker run` worker bypasses the DNS alias and breaks the "
        f"control-plane. Migrate it into the compose stack."
    )


@pytest.mark.skipif(
    not _docker_available(), reason="docker daemon not available"
)
def test_worker_live_dns_alias_resolvable_from_control_plane():
    """Authoritative proof that the control-plane can resolve `browser-worker`.
    This is exactly the condition that failed during the WORKER_UNAVAILABLE
    regression (NXDOMAIN -> ConnectError)."""
    worker = _find_worker_container()
    cp = _find_control_plane()
    if worker is None or cp is None:
        pytest.skip("live worker/control-plane not both running")
    assert _control_plane_resolves(WORKER_ALIAS), (
        f"control-plane cannot resolve alias {WORKER_ALIAS!r} -> worker. "
        f"This is the WORKER_UNAVAILABLE regression: the live worker is not "
        f"compose-managed and Docker never emitted the service DNS alias."
    )


@pytest.mark.skipif(
    not _docker_available(), reason="docker daemon not available"
)
def test_worker_attached_to_internal_network():
    worker = _find_worker_container()
    if worker is None:
        pytest.skip("no live browser-worker container running")
    insp = _run_json(["inspect", worker])
    if not insp:
        pytest.skip("cannot inspect worker")
    nets = (insp[0].get("NetworkSettings", {}).get("Networks", {})) or {}
    assert INTERNAL_NET in nets, (
        f"live worker not attached to {INTERNAL_NET}; got {list(nets.keys())}. "
        f"The alias is only resolvable within the shared compose network."
    )


def test_deploy_script_uses_canonical_compose_project():
    """The deployment helper must bring the worker up under the SAME compose
    project the running stack uses (`planner-mcp`, declared via `name:` in
    docker-compose.yml). Using a different `-p` value would create a SECOND
    orphaned stack and re-introduce the manual-worker regression class."""
    script = _resolve_deploy_script()
    if script is None:
        pytest.skip("deploy script not present in this environment")
    text = script.read_text(encoding="utf-8")
    # The script must NOT hardcode a divergent project name that spawns a
    # parallel stack (the exact bug that allowed a non-compose worker).
    assert "-p m365-ui-mcp" not in text, (
        "deploy script uses `-p m365-ui-mcp`, which creates a divergent stack "
        "instead of the live `planner-mcp` project. The worker would not inherit "
        "the compose DNS alias. Rely on the `name: planner-mcp` field instead."
    )
    # The base compose must still declare the canonical project name so the
    # script has a single source of truth.
    assert COMPOSE_FILE.exists()
    assert "name: planner-mcp" in COMPOSE_FILE.read_text(encoding="utf-8"), (
        "docker-compose.yml must declare `name: planner-mcp` so the worker and "
        "control-plane share one compose project and DNS namespace."
    )
    # The worker must be driven through compose `up`, not a manual `docker run`
    # that would bypass labels/alias. Any `docker run` for the worker service is
    # forbidden; the only acceptable `docker run` forms are throwaway `--rm`
    # smoke checks.
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("docker run") and "--rm" not in stripped:
            pytest.fail(
                "deploy script contains a non-rm `docker run`; the worker must "
                "be compose-managed to inherit the DNS alias. Found: "
                + stripped
            )
