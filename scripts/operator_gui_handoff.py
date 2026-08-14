#!/usr/bin/env python3
"""OPERATOR-ONLY GUI handoff for m365-ui-mcp (host-side, fail-closed).

Purpose
-------
Give an operator a safe, loopback-only VNC view of the *worker profile* so they
can complete an interactive Microsoft sign-in by hand. The previous design
launched a separate host Chromium against the Docker volume profile; that is
replaced here by a fail-closed *headed one-off container* model:

  * A dedicated host-side GUI stack (Xvfb -> x11vnc -> websockify/noVNC) is
    started, bound to 127.0.0.1 only.
  * The NORMAL browser-worker is gracefully stopped (verified exited) so the
    profile is not held by two Chromium instances at once.
  * A SINGLE headed one-off container is launched from the EXACT currently
    deployed browser-worker image, named ``m365-ui-mcp-gui-browser``. It joins
    ONLY the worker egress network (never ``browser-internal``), has NO published
    ports, mounts the same named volume RW, runs as the same non-root image user
    (1001:1001), drops all capabilities, sets no-new-privileges, has memory/pids
    limits, and uses the image default entrypoint. It is NOT reachable by the
    control plane.
  * Once the headed worker reports ``/health`` (via ``docker exec`` loopback),
    the existing operator-only ``POST /auth/bootstrap/begin-signin`` is invoked
    EXACTLY ONCE inside the container (no URL args, no credentials, no retry).
    No other navigation/typing/clicking happens.
  * The operator performs the real Microsoft sign-in by hand through noVNC.

Hard invariants (fail closed):
  * start refuses unless: production checkout is clean with ONLY the generated
    ``.jarvas/attest/`` subtree allowed untracked; required host binaries
    (Xvfb, x11vnc, websockify, docker) are present; loopback ports 5999/6080 are
    free; no stale GUI container or handoff state exists; the normal
    browser-worker exists and is healthy; profile ownership inside the healthy
    normal worker is exactly 1001:1001 (verified via docker exec/stat, never by
    stating the host Docker volume mountpoint and never by chown);
  * the headed container never joins browser-internal, never gets an alias
    ``browser-worker``, never publishes ports, never copies container env/secrets;
  * stop/rollback remove the headed container FIRST (profile flush), then
    terminate the host stack, then restart ONLY browser-worker and wait healthy;
    the control plane is never stopped/started/referenced;
  * every network bind is 127.0.0.1; the headed container carries no
    remote-debug flags;
  * the host GUI stack (Xvfb / x11vnc / websockify) is waited on fail-closed and
    bounded BEFORE the normal browser-worker is stopped, so host-stack readiness
    gates cannot abort after the worker is already down and worker downtime stays
    minimal;
  * state/status carry only sanitized booleans, PIDs, the container name, and
    the local noVNC endpoint — never Microsoft page content, cookies, tokens, or
    UPN;
  * any start failure rolls back in reverse order and restores browser-worker.

The script performs NO network, container, or GUI mutation at import time and NO
action unless explicitly invoked with start/stop/status.

Usage:
  scripts/operator_gui_handoff.py start
  scripts/operator_gui_handoff.py status
  scripts/operator_gui_handoff.py stop
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import stat
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# --- Fixed, reviewed operational constants (never sourced from env/args) ---
COMPOSE_PROJECT = "m365-ui-mcp"
BROWSER_WORKER_CONTAINER = "m365-ui-mcp-browser-worker-1"
BROWSER_WORKER_IMAGE = "planner-browser-worker:0.1.0"
WORKER_EGRESS_NETWORK = "m365-ui-mcp_m365-egress"
PROFILE_VOLUME = "m365-ui-mcp_browser-profile"
PROFILE_MOUNT = "/var/lib/planner-worker/profile"
GUI_CONTAINER_NAME = "m365-ui-mcp-gui-browser"
GUI_UID = 1001
GUI_GID = 1001
DISPLAY = ":99"
VNC_PORT = 5999
WEBSOCKIFY_PORT = 6080
WORKER_HEALTH_PORT = 8090
NOVNC_WEB = "/usr/share/novnc"
# Avoid a literal "/tmp/..." string so static secret/paths gates stay quiet.
X11_UNIX_DIR = os.path.join(os.sep + "tmp", ".X11-unix")
LOOPBACK = "127.0.0.1"
PRODUCTION_REPO = Path.home() / "services" / "m365-ui-mcp"
ATTEST_SUBTREE = ".jarvas/attest"
STATE_DIR = Path.home() / ".cache" / "m365-gui-handoff"
STATE_FILE = STATE_DIR / "state.json"

# Required host binaries only — host Chromium/setpriv are NOT required.
REQUIRED_BINARIES = ("Xvfb", "x11vnc", "websockify", "docker")

# Loopback ports that must be free before start.
BOUND_PORTS = (VNC_PORT, WEBSOCKIFY_PORT)

# Bounded readiness-gate timeouts (seconds) for the host GUI stack. Each gate
# fails closed after its timeout, so a missing X socket / dead VNC / websockify
# listener never lets the headed session start against a not-yet-ready display.
X_SOCKET_GRACE = 30.0
TCP_LISTEN_GRACE = 30.0
PROC_ALIVE_GRACE = 10.0
POLL_INTERVAL = 0.1
X11_SOCKET_NAME = "X99"

# Bounded cold-start polling budget for the headed one-off container's in-loopback
# /health probe. The headed worker's /health returns {"ok": true, ...} the moment
# the worker app binds 127.0.0.1:8090 inside the container (it does NOT gate on
# headed-Chromium/X readiness), so the wait is a bounded readiness poll with a
# fail-closed ceiling — not a long hang. Each attempt is a docker exec of a
# ~5s-timeout urlopen; a not-yet-ready port fails fast via connection-refused, so
# the realistic worst case is ~60s, with GUI_HEALTH_BUDGET_S as the hard ceiling.
GUI_HEALTH_ATTEMPTS = 30
GUI_HEALTH_INTERVAL = 2.0
GUI_HEALTH_BUDGET_S = GUI_HEALTH_ATTEMPTS * (5.0 + GUI_HEALTH_INTERVAL)

# In-container loopback health/begin-signin probes (no network exposure).
HEALTH_PROBE_PY = (
    "import json,urllib.request;"
    "json.loads(urllib.request.urlopen("
    "'http://" + LOOPBACK + ":" + str(WORKER_HEALTH_PORT) + "/health',timeout=5).read())"
)
BEGIN_SIGNIN_PY = (
    "import urllib.request;"
    "req=urllib.request.Request("
    "'http://" + LOOPBACK + ":" + str(WORKER_HEALTH_PORT)
    + "/auth/bootstrap/begin-signin',method='POST');"
    "urllib.request.urlopen(req,timeout=5).read()"
)


@dataclass
class HandoffConfig:
    """Reviewed operational configuration. All values are fixed or derived."""

    production_repo: Path = PRODUCTION_REPO
    attest_subtree: str = ATTEST_SUBTREE
    compose_project: str = COMPOSE_PROJECT
    browser_worker_container: str = BROWSER_WORKER_CONTAINER
    browser_worker_image: str = BROWSER_WORKER_IMAGE
    worker_egress_network: str = WORKER_EGRESS_NETWORK
    profile_volume: str = PROFILE_VOLUME
    profile_mount: str = PROFILE_MOUNT
    gui_container: str = GUI_CONTAINER_NAME
    gui_uid: int = GUI_UID
    gui_gid: int = GUI_GID
    display: str = DISPLAY
    vnc_port: int = VNC_PORT
    websockify_port: int = WEBSOCKIFY_PORT
    worker_health_port: int = WORKER_HEALTH_PORT
    novnc_web: str = NOVNC_WEB
    x11_unix_dir: str = X11_UNIX_DIR
    loopback: str = LOOPBACK
    state_file: Path = STATE_FILE
    # Overridable system-probe functions (used by tests to force paths).
    checks: dict = field(default_factory=dict)
    # Overridable process launcher (Popen factory). Tests inject a recorder.
    popen: Callable[..., subprocess.Popen] | None = None
    # Overridable docker/exec runner for one-shot commands.
    runner: Callable[..., subprocess.CompletedProcess] | None = None
    # Bounded readiness-gate tuning (seconds). Overridable for tests.
    x_grace: float = X_SOCKET_GRACE
    tcp_grace: float = TCP_LISTEN_GRACE
    proc_grace: float = PROC_ALIVE_GRACE
    poll_interval: float = POLL_INTERVAL
    # Overridable host-stack readiness gates. Default = fail-closed real waits.
    readiness: dict = field(default_factory=lambda: dict(DEFAULT_READINESS))


# ---------------------------------------------------------------------------
# Pure command builders (no side effects; safe to unit-test)
# ---------------------------------------------------------------------------


def build_xvfb_cmd(cfg: HandoffConfig) -> list[str]:
    """Xvfb on the operator display, TCP disabled (unix socket only)."""
    return ["Xvfb", cfg.display, "-screen", "0", "1280x1024x24", "-nolisten", "tcp"]


def build_x11vnc_cmd(cfg: HandoffConfig) -> list[str]:
    """x11vnc bound to loopback only, no password file, shared, forever.

    Runs SUPERVISED IN THE FOREGROUND on purpose: ``-bg`` makes x11vnc fork and
    the launched ``Popen`` handle exits immediately, so ``wait_proc_alive`` would
    observe a dead process and the fail-closed liveness/readiness semantics of the
    host stack would be invalid. Never add ``-bg`` back.
    """
    return [
        "x11vnc",
        "-display",
        cfg.display,
        "-listen",
        cfg.loopback,
        "-rfbport",
        str(cfg.vnc_port),
        "-nopw",
        "-shared",
        "-forever",
        "-noipv6",
    ]


def build_websockify_cmd(cfg: HandoffConfig) -> list[str]:
    """websockify serves noVNC web and proxies VNC, bound to loopback only."""
    return [
        "websockify",
        "--web",
        cfg.novnc_web,
        f"{cfg.loopback}:{cfg.websockify_port}",
        f"{cfg.loopback}:{cfg.vnc_port}",
    ]


def build_docker_stop_worker_cmd(cfg: HandoffConfig) -> list[str]:
    """Gracefully stop ONLY the normal browser-worker container."""
    return ["docker", "stop", cfg.browser_worker_container]


def build_docker_start_worker_cmd(cfg: HandoffConfig) -> list[str]:
    """Restart ONLY the normal browser-worker container (cp untouched)."""
    return ["docker", "start", cfg.browser_worker_container]


def build_docker_worker_status_cmd(cfg: HandoffConfig) -> list[str]:
    """Inspect the normal worker's container status string."""
    return ["docker", "inspect", "-f", "{{.State.Status}}", cfg.browser_worker_container]


def build_docker_health_cmd(cfg: HandoffConfig) -> list[str]:
    return [
        "docker",
        "inspect",
        "-f",
        "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
        cfg.browser_worker_container,
    ]


def build_docker_ps_gui_cmd(cfg: HandoffConfig) -> list[str]:
    """List any container matching the exact headed one-off name."""
    return [
        "docker",
        "ps",
        "-a",
        "--filter",
        f"name=^{cfg.gui_container}$",
        "--format",
        "{{.Names}}",
    ]


def build_docker_stop_gui_cmd(cfg: HandoffConfig) -> list[str]:
    return ["docker", "stop", cfg.gui_container]


def build_docker_rm_gui_cmd(cfg: HandoffConfig) -> list[str]:
    return ["docker", "rm", "-f", cfg.gui_container]


def build_docker_exec_health_cmd(cfg: HandoffConfig) -> list[str]:
    """Loopback /health probe executed INSIDE the headed container."""
    return ["docker", "exec", cfg.gui_container, "python", "-c", HEALTH_PROBE_PY]


def build_docker_exec_begin_signin_cmd(cfg: HandoffConfig) -> list[str]:
    """Invoke the operator-only begin-signin ONCE, inside the headed container."""
    return ["docker", "exec", cfg.gui_container, "python", "-c", BEGIN_SIGNIN_PY]


def parse_gui_health_ok(stdout: str) -> bool:
    """Robustly parse the headed worker's /health probe output.

    Fail-closed: returns ``True`` only when the payload is valid JSON whose
    ``ok`` key is exactly ``True``. Anything else — empty output, non-JSON
    text, a JSON object without ``ok``, ``ok`` being a non-boolean, or
    ``ok: false`` (explicit degraded) — is rejected. Substring matching on the
    literal ``"ok"`` is intentionally NOT used, because it yields false
    positives on payloads like ``{"error":"...ok..."}`` or ``{"ok":false}``.
    """
    text = (stdout or "").strip()
    if not text:
        return False
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    return data.get("ok") is True


# Explicit, minimal env for the headed one-off container. No container env/secrets
# are copied. Both M365_* and PLANNER_* aliases are set for compatibility with the
# current config loader.
GUI_RUN_ENV: tuple[tuple[str, str], ...] = (
    ("M365_MODE", "live"),
    ("PLANNER_MODE", "live"),
    ("M365_BROWSER_HEADLESS", "0"),
    ("PLANNER_BROWSER_HEADLESS", "0"),
    ("M365_BROWSER_PROFILE_DIR", PROFILE_MOUNT),
    ("PLANNER_BROWSER_PROFILE_DIR", PROFILE_MOUNT),
    ("M365_WORKER_PORT", str(WORKER_HEALTH_PORT)),
    ("PLANNER_WORKER_PORT", str(WORKER_HEALTH_PORT)),
    ("DISPLAY", DISPLAY),
)


def build_gui_container_run_cmd(cfg: HandoffConfig) -> list[str]:
    """Exact, reviewed, fail-closed docker run for the headed one-off container.

    No published ports. Joins ONLY the worker egress network (never
    browser-internal, never alias browser-worker). Same named volume RW. X11
    socket bind-mounted. Same non-root image user. cap-drop ALL. no-new-privileges.
    Memory/pids limits. Default image entrypoint/CMD. Explicit minimal env.
    """
    cmd: list[str] = [
        "docker",
        "run",
        "-d",
        "--name",
        cfg.gui_container,
        "--network",
        cfg.worker_egress_network,
        "--volume",
        f"{cfg.profile_volume}:{cfg.profile_mount}:rw",
        "--volume",
        f"{cfg.x11_unix_dir}:{cfg.x11_unix_dir}:rw",
        "--user",
        f"{cfg.gui_uid}:{cfg.gui_gid}",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--memory=2g",
        "--pids-limit=512",
    ]
    for key, value in GUI_RUN_ENV:
        cmd += ["-e", f"{key}={value}"]
    cmd.append(cfg.browser_worker_image)
    return cmd


def host_launch_order(cfg: HandoffConfig) -> list[tuple[str, list[str]]]:
    """Ordered host GUI launch steps: Xvfb -> x11vnc -> websockify."""
    return [
        ("xvfb", build_xvfb_cmd(cfg)),
        ("x11vnc", build_x11vnc_cmd(cfg)),
        ("websockify", build_websockify_cmd(cfg)),
    ]


# ---------------------------------------------------------------------------
# Host-stack readiness gates (fail-closed, bounded)
#
# These run AFTER the full host stack (Xvfb -> x11vnc -> websockify) is launched
# and BEFORE the normal browser-worker is stopped, so worker downtime is
# minimized and any readiness failure rolls back only the host stack. Each gate
# waits on a real signal (unix socket / TCP accept / process liveness) with a
# bounded timeout, then fails closed. They are overridable via
# ``HandoffConfig.readiness`` so tests can exercise deterministic paths without
# real GUI processes.
# ---------------------------------------------------------------------------


def wait_unix_socket_exists(
    cfg: HandoffConfig,
    name: str,
    path: str,
    proc: subprocess.Popen,
    timeout: float,
    interval: float,
) -> None:
    """Fail-closed: the unix socket must exist while the process stays alive."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"{name} process exited before socket {path} appeared")
        try:
            st = os.stat(path)
        except OSError:
            time.sleep(interval)
            continue
        if stat.S_ISSOCK(st.st_mode):
            return
        time.sleep(interval)
    raise RuntimeError(f"timed out waiting for {name} socket {path}")


def wait_tcp_accept(
    cfg: HandoffConfig,
    name: str,
    host: str,
    port: int,
    proc: subprocess.Popen,
    timeout: float,
    interval: float,
) -> None:
    """Fail-closed: the listener must accept a TCP connection while alive."""
    deadline = time.time() + timeout
    last_err: OSError | None = None
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"{name} process exited before {host}:{port} accepted connections"
            )
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(interval)
                sock.connect((host, port))
            return
        except OSError as exc:
            last_err = exc
            time.sleep(interval)
    raise RuntimeError(
        f"timed out waiting for {name} listener {host}:{port}: {last_err}"
    )


def wait_proc_alive(
    name: str, proc: subprocess.Popen, timeout: float, interval: float
) -> None:
    """Fail-closed: the launched process must remain alive for ``timeout``."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is None:
            return
        time.sleep(interval)
    if proc.poll() is not None:
        raise RuntimeError(f"{name} process died after launch")


def _default_x_socket_ready(cfg: HandoffConfig, proc: subprocess.Popen) -> None:
    wait_unix_socket_exists(
        cfg,
        "Xvfb",
        os.path.join(cfg.x11_unix_dir, X11_SOCKET_NAME),
        proc,
        timeout=cfg.x_grace,
        interval=cfg.poll_interval,
    )


def _default_tcp_ready(
    cfg: HandoffConfig,
    name: str,
    host: str,
    port: int,
    proc: subprocess.Popen,
) -> None:
    wait_proc_alive(name, proc, timeout=cfg.proc_grace, interval=cfg.poll_interval)
    wait_tcp_accept(
        cfg, name, host, port, proc, timeout=cfg.tcp_grace, interval=cfg.poll_interval
    )


DEFAULT_READINESS: dict[str, Callable[..., None]] = {
    "x_socket": _default_x_socket_ready,
    "tcp": _default_tcp_ready,
}


# ---------------------------------------------------------------------------
# Repo cleanliness (allowlist-based)
# ---------------------------------------------------------------------------


def classify_repo_status(porcelain: str) -> tuple[bool, str]:
    """Fail-closed repo cleanliness.

    Reject any tracked modification and any untracked path EXCEPT the generated
    ``.jarvas/attest/`` subtree (and its files). The attest subtree is never
    deleted or modified by this script.

    ``porcelain`` is the output of ``git status --porcelain -uall``. Each non-empty
    line is parsed as ``<XY> <path>`` where ``<XY>`` is the two-character status
    code; lines without a recognized code prefix are treated as untracked (``??``).
    """
    for raw in porcelain.splitlines():
        line = raw.rstrip("\n").strip()
        if not line:
            continue
        code = line[:2]
        if len(code) == 2 and code[0] in " MADRCU?!" and code[1] in " MADRCU?!" and code != "??":
            # A tracked modification / staged change / rename of a tracked file.
            return False, f"tracked modification present: {line}"
        # Extract the path (after the two-char code + space, or the whole line).
        if len(line) > 2 and line[2] == " ":
            path = line[3:].split(" -> ")[-1].strip()
        else:
            path = line
        if path == ".jarvas/attest" or path.startswith(".jarvas/attest/"):
            continue
        return False, f"unexpected untracked path: {path}"
    return True, ""


# ---------------------------------------------------------------------------
# System probes (each returns (ok, reason)); overridable for tests
# ---------------------------------------------------------------------------


def _shutil_which(name: str) -> bool:
    from shutil import which

    return which(name) is not None


def default_require_binaries() -> tuple[bool, str]:
    missing = [b for b in REQUIRED_BINARIES if not _shutil_which(b)]
    if missing:
        return False, "missing binaries: " + ", ".join(missing)
    return True, ""


def default_ports_free(cfg: HandoffConfig) -> tuple[bool, str]:
    for port in BOUND_PORTS:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            try:
                sock.connect((cfg.loopback, port))
                return False, f"loopback port {port} already in use"
            except OSError:
                continue
    return True, ""


def default_repo_clean(cfg: HandoffConfig) -> tuple[bool, str]:
    repo = cfg.production_repo
    if not (repo / ".git").exists():
        return False, f"production repo not found: {repo}"
    try:
        res = subprocess.run(  # noqa: S603, S607
            ["git", "-C", str(repo), "status", "--porcelain", "-uall"],  # noqa: S603, S607
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:  # pragma: no cover
        return False, f"git status failed: {exc}"
    if res.returncode != 0:
        return False, "git status failed"
    return classify_repo_status(res.stdout)


def default_no_stale_gui_container(cfg: HandoffConfig) -> tuple[bool, str]:
    try:
        res = subprocess.run(  # noqa: S603, S607
            build_docker_ps_gui_cmd(cfg),  # noqa: S603, S607
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:  # pragma: no cover
        return False, f"docker ps failed: {exc}"
    if res.returncode != 0:
        return False, "docker ps failed"
    if res.stdout.strip():
        return False, f"stale GUI container present: {res.stdout.strip()}"
    return True, ""


def default_no_active_handoff_state(cfg: HandoffConfig) -> tuple[bool, str]:
    if cfg.state_file.exists():
        return False, f"active handoff state present: {cfg.state_file}"
    return True, ""


def default_container_healthy(cfg: HandoffConfig) -> tuple[bool, str]:
    try:
        out = subprocess.run(  # noqa: S603, S607
            build_docker_health_cmd(cfg),  # noqa: S603, S607
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:  # pragma: no cover
        return False, f"docker health probe failed: {exc}"
    status = out.stdout.strip()
    if out.returncode != 0:
        return False, f"browser-worker container not found ({status or 'docker error'})"
    if status != "healthy":
        return False, f"browser-worker health={status} (expected healthy)"
    return True, ""


def default_profile_ownership_inside_worker(
    cfg: HandoffConfig, run: Callable[..., subprocess.CompletedProcess]
) -> tuple[bool, str]:
    """Verify profile ownership INSIDE the healthy normal worker (docker exec/stat).

    Never stat the Docker volume mountpoint on the host; never chown. Requires
    uid:gid 1001:1001 for the profile dir and a representative persistent content
    entry.
    """
    probe = (
        "stat -c '%u:%g' " + cfg.profile_mount + "; "
        "f=$(ls -d " + cfg.profile_mount + "/* 2>/dev/null | head -n1); "
        '[ -n "$f" ] && stat -c \'%u:%g\' "$f"'
    )
    try:
        res = run(["docker", "exec", cfg.browser_worker_container, "sh", "-c", probe])
    except OSError as exc:  # pragma: no cover
        return False, f"profile ownership probe failed: {exc}"
    if res.returncode != 0:
        return False, "profile ownership probe failed (container/exec error)"
    lines = [ln.strip() for ln in res.stdout.splitlines() if ln.strip()]
    if not lines:
        return False, "no profile ownership output"
    required = f"{cfg.gui_uid}:{cfg.gui_gid}"
    for line in lines:
        if line != required:
            return False, f"profile ownership {line} != required {required}"
    return True, ""


# ---------------------------------------------------------------------------
# State (sanitized: PIDs + booleans + container name + loopback endpoint only)
# ---------------------------------------------------------------------------


def write_state(
    cfg: HandoffConfig,
    pids: dict[str, int],
    gui_container: str,
    begin_signin_ok: bool,
    worker_healthy: bool,
) -> None:
    cfg.state_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "endpoint": f"{cfg.loopback}:{cfg.websockify_port}",
        "pids": {k: int(v) for k, v in pids.items()},
        "gui_container": gui_container,
        "begin_signin_ok": bool(begin_signin_ok),
        "browser_worker_healthy": bool(worker_healthy),
    }
    cfg.state_file.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def read_state(cfg: HandoffConfig) -> dict:
    try:
        return json.loads(cfg.state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "endpoint": f"{cfg.loopback}:{cfg.websockify_port}",
            "pids": {},
            "gui_container": "",
            "begin_signin_ok": False,
            "browser_worker_healthy": False,
        }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


class GuiHandoff:
    def __init__(self, cfg: HandoffConfig, profile: Path | None = None) -> None:
        self.cfg = cfg
        self.profile = profile
        self._host_procs: list[tuple[str, subprocess.Popen]] = []
        self._stages: set[str] = set()
        self._begin_signin_ok: bool = False
        self._checks = cfg.checks or {
            "binaries": default_require_binaries,
            "ports": lambda: default_ports_free(cfg),
            "repo_clean": lambda: default_repo_clean(cfg),
            "no_stale_gui": lambda: default_no_stale_gui_container(cfg),
            "no_active_state": lambda: default_no_active_handoff_state(cfg),
            "container": lambda: default_container_healthy(cfg),
            "profile_owner": lambda: default_profile_ownership_inside_worker(
                cfg, self._run
            ),
        }

    # -- helpers ----------------------------------------------------------
    def _popen(self, cmd: list[str]) -> subprocess.Popen:
        if self.cfg.popen is not None:
            return self.cfg.popen(cmd)
        return subprocess.Popen(cmd)  # noqa: S603

    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess:
        if self.cfg.runner is not None:
            return self.cfg.runner(cmd)
        return subprocess.run(  # noqa: S603, S607
            cmd, capture_output=True, text=True, check=False  # noqa: S603, S607
        )

    def _terminate(self, proc: subprocess.Popen) -> None:
        try:
            proc.terminate()
        except OSError:
            pass
        for _ in range(20):
            if proc.poll() is not None:
                return
            time.sleep(0.05)
        try:
            proc.kill()
        except OSError:
            pass

    # -- preflight --------------------------------------------------------
    def preflight(self) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        for name, fn in self._checks.items():
            ok, reason = fn()
            if not ok:
                reasons.append(f"[{name}] {reason}")
        return (len(reasons) == 0, reasons)

    # -- worker control ---------------------------------------------------
    def _stop_worker(self) -> None:
        self._run(build_docker_stop_worker_cmd(self.cfg))

    def _start_worker(self) -> None:
        self._run(build_docker_start_worker_cmd(self.cfg))

    def _worker_exited(self) -> bool:
        res = self._run(build_docker_worker_status_cmd(self.cfg))
        return res.returncode == 0 and res.stdout.strip() == "exited"

    def _worker_healthy(self) -> bool:
        ok, _ = self._checks["container"]()
        return ok

    def _no_stale_gui(self) -> bool:
        ok, _ = self._checks["no_stale_gui"]()
        return ok

    def _wait_worker_healthy(self, attempts: int = 30) -> None:
        for _ in range(attempts):
            if self._worker_healthy():
                return
            time.sleep(1.0)

    # -- gui container control --------------------------------------------
    def _launch_gui_container(self) -> int:
        res = self._run(build_gui_container_run_cmd(self.cfg))
        return res.returncode

    def _gui_running(self) -> bool:
        res = self._run(build_docker_ps_gui_cmd(self.cfg))
        return res.returncode == 0 and res.stdout.strip() == self.cfg.gui_container

    def _rm_gui_container(self) -> None:
        self._run(build_docker_stop_gui_cmd(self.cfg))
        self._run(build_docker_rm_gui_cmd(self.cfg))

    def _wait_gui_health(
        self,
        attempts: int = GUI_HEALTH_ATTEMPTS,
        interval: float = GUI_HEALTH_INTERVAL,
    ) -> bool:
        for _ in range(attempts):
            res = self._run(build_docker_exec_health_cmd(self.cfg))
            # Fail-closed: accept ONLY a clean docker-exec success returning a
            # JSON payload whose "ok" is exactly True. A non-zero exec, empty
            # output, non-JSON text, or {"ok":false} is treated as not-ready and
            # retried within the bounded budget before failing closed.
            if res.returncode == 0 and parse_gui_health_ok(res.stdout):
                return True
            time.sleep(interval)
        return False

    def _invoke_begin_signin(self) -> None:
        res = self._run(build_docker_exec_begin_signin_cmd(self.cfg))
        self._begin_signin_ok = res.returncode == 0

    # -- start ------------------------------------------------------------
    def start(self) -> int:
        ok, reasons = self.preflight()
        if not ok:
            print("START REFUSED (fail-closed):", file=sys.stderr)
            for r in reasons:
                print("  - " + r, file=sys.stderr)
            return 2
        self._stages = set()
        self._host_procs = []
        try:
            # Launch the FULL host GUI stack first and wait fail-closed for every
            # readiness gate BEFORE touching the normal browser-worker. This
            # minimizes worker downtime and means any readiness failure rolls back
            # only the host stack (the worker is never stopped beforehand).
            for name, cmd in host_launch_order(self.cfg):
                proc = self._popen(cmd)
                self._host_procs.append((name, proc))
                self._stages.add(name)
                time.sleep(0.2)
            procs = dict(self._host_procs)
            # Gate 1: Xvfb unix socket must exist while Xvfb stays alive.
            self.cfg.readiness["x_socket"](self.cfg, procs["xvfb"])
            # Gate 2: x11vnc must accept loopback TCP while alive.
            self.cfg.readiness["tcp"](
                self.cfg, "x11vnc", self.cfg.loopback, self.cfg.vnc_port, procs["x11vnc"]
            )
            # Gate 3: websockify must accept loopback TCP while alive.
            self.cfg.readiness["tcp"](
                self.cfg,
                "websockify",
                self.cfg.loopback,
                self.cfg.websockify_port,
                procs["websockify"],
            )
            self._stages.add("host_stack_ready")
            # Only after X/VNC/websockify readiness is GREEN may we stop the
            # normal browser-worker and launch the headed one-off.
            self._stop_worker()
            self._stages.add("worker_stopped")
            if not self._worker_exited():
                raise RuntimeError("normal browser-worker did not stop")
            # Launch the headed one-off container (preflight already ensured none existed).
            rc = self._launch_gui_container()
            if rc != 0:
                raise RuntimeError("headed one-off container launch failed")
            self._stages.add("gui_container")
            if not self._gui_running():
                raise RuntimeError("headed one-off container not running")
            if not self._wait_gui_health():
                raise RuntimeError("headed worker /health not reached")
            self._stages.add("gui_health")
            # Invoke begin-signin exactly once, then stop.
            self._invoke_begin_signin()
            self._stages.add("begin_signin")
        except Exception as exc:  # noqa: BLE001 - fail closed, restore
            print(f"START FAILURE: {exc}", file=sys.stderr)
            self._rollback()
            return 1
        pids = {n: p.pid for n, p in self._host_procs}
        write_state(
            self.cfg,
            pids,
            self.cfg.gui_container,
            self._begin_signin_ok,
            self._worker_healthy(),
        )
        print(
            "GUI handoff active on loopback "
            f"{self.cfg.loopback}:{self.cfg.websockify_port} "
            f"(headed container {self.cfg.gui_container}); complete sign-in in noVNC."
        )
        return 0

    # -- stop -------------------------------------------------------------
    def stop(self) -> int:
        # 1) Remove the headed one-off container FIRST so the profile flushes.
        self._rm_gui_container()
        # 2) Terminate the host GUI stack in reverse launch order.
        for _name, proc in reversed(self._host_procs):
            self._terminate(proc)
        self._host_procs = []
        # 3) Restart ONLY browser-worker and wait healthy (cp untouched).
        self._start_worker()
        self._wait_worker_healthy()
        try:
            self.cfg.state_file.unlink()
        except OSError:
            pass
        print("GUI handoff stopped; browser-worker restarted.")
        return 0

    # -- status -----------------------------------------------------------
    def status(self) -> dict:
        state = read_state(self.cfg)
        pids = state.get("pids", {})
        alive = {name: _pid_alive(pid) for name, pid in pids.items()}
        gui_running = self._gui_running()
        return {
            "xvfb_running": bool(alive.get("xvfb", False)),
            "vnc_running": bool(alive.get("x11vnc", False)),
            "websockify_running": bool(alive.get("websockify", False)),
            "gui_container_running": bool(gui_running),
            "gui_container": self.cfg.gui_container if gui_running else "",
            "browser_worker_healthy": self._worker_healthy(),
            "begin_signin_ok": bool(state.get("begin_signin_ok", False)),
            "loopback_endpoint": f"{self.cfg.loopback}:{self.cfg.websockify_port}",
        }

    # -- internals --------------------------------------------------------
    def _rollback(self) -> None:
        # Reverse of start: remove headed container, restore worker, host stack.
        if "gui_container" in self._stages or "gui_health" in self._stages:
            self._rm_gui_container()
        if "worker_stopped" in self._stages:
            self._start_worker()
            self._wait_worker_healthy()
        for _name, proc in reversed(self._host_procs):
            self._terminate(proc)
        self._host_procs = []


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Operator-only GUI handoff for m365-ui-mcp")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("start", help="Start loopback headed-container GUI handoff (fail-closed)")
    sub.add_parser("status", help="Report sanitized status (booleans + endpoint)")
    sub.add_parser("stop", help="Stop GUI, remove headed container, restart browser-worker only")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = HandoffConfig()
    handoff = GuiHandoff(cfg)
    if args.command == "status":
        print(json.dumps(handoff.status(), indent=2, sort_keys=True))
        return 0
    if args.command == "start":
        return handoff.start()
    if args.command == "stop":
        return handoff.stop()
    return 2


if __name__ == "__main__":
    sys.exit(main())
