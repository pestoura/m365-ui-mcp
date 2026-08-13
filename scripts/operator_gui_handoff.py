#!/usr/bin/env python3
"""OPERATOR-ONLY GUI handoff for m365-ui-mcp (host-side, fail-closed).

Purpose
-------
Give an operator a safe, loopback-only VNC view of the *already running*
worker profile, without ever touching the control plane, the production
containers' lifecycle, Cloudflare, credentials, cookies, browser data, or M365.

This script launches a SEPARATE host-side GUI stack (Xvfb -> x11vnc ->
websockify/noVNC) and a SEPARATE host Chromium pointed at the named Docker
volume profile, running as the numeric uid/gid the volume already uses
(1001:1001). It never chowns the profile, never exposes anything beyond
127.0.0.1, never emits tokens, and never stops or starts the control plane.

Hard invariants (fail closed):
  * start refuses unless the production checkout is clean and the expected
    browser-worker container exists and is healthy;
  * start refuses if any required binary is missing, any loopback port is
    already in use, the profile is held by another live Chromium, or the
    profile ownership is not 1001:1001 (UID mismatch);
  * stop touches ONLY browser-worker (never control-plane);
  * every network bind is 127.0.0.1; no remote-debugging/CDP flags;
  * state stored outside the profile contains only sanitized PIDs/booleans;
  * any failure during start rolls the GUI stack back in reverse order and
    restores browser-worker to healthy.

The script performs NO network, container, or GUI mutation at import time and
NO action unless explicitly invoked with start/stop/status.

Usage:
  scripts/operator_gui_handoff.py start
  scripts/operator_gui_handoff.py status
  scripts/operator_gui_handoff.py stop
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
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
PROFILE_VOLUME = "m365-ui-mcp_browser-profile"
GUI_UID = 1001
GUI_GID = 1001
DISPLAY = ":99"
VNC_PORT = 5999
WEBSOCKIFY_PORT = 6080
NOVNC_WEB = "/usr/share/novnc"
LOOPBACK = "127.0.0.1"
PRODUCTION_REPO = Path.home() / "services" / "m365-ui-mcp"
STATE_DIR = Path.home() / ".cache" / "m365-gui-handoff"
STATE_FILE = STATE_DIR / "state.json"

REQUIRED_BINARIES = ("Xvfb", "x11vnc", "websockify", "chromium", "setpriv", "docker")

# Loopback ports that must be free before start.
BOUND_PORTS = (VNC_PORT, WEBSOCKIFY_PORT)


@dataclass
class HandoffConfig:
    """Reviewed operational configuration. All values are fixed or derived."""

    production_repo: Path = PRODUCTION_REPO
    compose_project: str = COMPOSE_PROJECT
    browser_worker_container: str = BROWSER_WORKER_CONTAINER
    profile_volume: str = PROFILE_VOLUME
    gui_uid: int = GUI_UID
    gui_gid: int = GUI_GID
    display: str = DISPLAY
    vnc_port: int = VNC_PORT
    websockify_port: int = WEBSOCKIFY_PORT
    novnc_web: str = NOVNC_WEB
    loopback: str = LOOPBACK
    state_file: Path = STATE_FILE
    # Overridable system-probe functions (used by tests to force paths).
    checks: dict = field(default_factory=dict)
    # Overridable process launcher (Popen factory). Tests inject a recorder.
    popen: Callable[..., subprocess.Popen] | None = None
    # Overridable docker/exec runner for one-shot commands.
    runner: Callable[..., subprocess.CompletedProcess] | None = None


# ---------------------------------------------------------------------------
# Pure command builders (no side effects; safe to unit-test)
# ---------------------------------------------------------------------------


def build_xvfb_cmd(cfg: HandoffConfig) -> list[str]:
    """Xvfb on the operator display, TCP disabled (unix socket only)."""
    return ["Xvfb", cfg.display, "-screen", "0", "1280x1024x24", "-nolisten", "tcp"]


def build_x11vnc_cmd(cfg: HandoffConfig) -> list[str]:
    """x11vnc bound to loopback only, no password file, shared, forever."""
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
        "-bg",
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


def build_chromium_cmd(cfg: HandoffConfig, profile: Path) -> list[str]:
    """Host Chromium as numeric uid/gid 1001:1001, NO remote-debugging/CDP.

    The profile is launched read-write by uid 1001 (its owner); we never chown.
    """
    return [
        "setpriv",
        "--reuid",
        str(cfg.gui_uid),
        "--regid",
        str(cfg.gui_gid),
        "--clear-groups",
        "chromium",
        "--display",
        cfg.display,
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-features=Translate,OptimizationHints,MediaRouter",
        "--disable-extensions",
    ]


def build_docker_restart_worker_cmd(cfg: HandoffConfig) -> list[str]:
    """Restart ONLY browser-worker. control-plane is never referenced."""
    return [
        "docker",
        "compose",
        "-p",
        cfg.compose_project,
        "restart",
        "browser-worker",
    ]


def build_docker_health_cmd(cfg: HandoffConfig) -> list[str]:
    return [
        "docker",
        "inspect",
        "-f",
        "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
        cfg.browser_worker_container,
    ]


def launch_order(cfg: HandoffConfig, profile: Path) -> list[tuple[str, list[str]]]:
    """Ordered GUI launch steps: Xvfb -> x11vnc -> websockify -> Chromium."""
    return [
        ("xvfb", build_xvfb_cmd(cfg)),
        ("x11vnc", build_x11vnc_cmd(cfg)),
        ("websockify", build_websockify_cmd(cfg)),
        ("chromium", build_chromium_cmd(cfg, profile)),
    ]


def teardown_order() -> list[str]:
    """Reverse of launch: Chromium -> x11vnc -> websockify -> Xvfb."""
    return ["chromium", "x11vnc", "websockify", "xvfb"]


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


def default_uid_match(profile: Path, cfg: HandoffConfig) -> tuple[bool, str]:
    try:
        st = profile.stat()
    except OSError as exc:  # pragma: no cover - filesystem error path
        return False, f"cannot stat profile {profile}: {exc}"
    if st.st_uid != cfg.gui_uid or st.st_gid != cfg.gui_gid:
        return (
            False,
            f"profile ownership {st.st_uid}:{st.st_gid} != "
            f"required {cfg.gui_uid}:{cfg.gui_gid}",
        )
    return True, ""


def default_profile_unlocked(profile: Path) -> tuple[bool, str]:
    """Reject if another live Chromium already holds this profile."""
    try:
        out = subprocess.run(
            ["pgrep", "-af", "chromium"],  # noqa: S603, S607
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:  # pragma: no cover - pgrep missing
        return True, ""
    target = str(profile)
    for line in out.stdout.splitlines():
        if target in line and "operator_gui_handoff" not in line:
            return False, f"profile already held by live chromium: {line.strip()}"
    return True, ""


def default_prod_repo_clean(cfg: HandoffConfig) -> tuple[bool, str]:
    repo = cfg.production_repo
    if not (repo / ".git").exists():
        return False, f"production repo not found: {repo}"
    head = subprocess.run(  # noqa: S603, S607
        ["git", "-C", str(repo), "status", "--porcelain"],  # noqa: S603, S607
        capture_output=True,
        text=True,
        check=False,
    )
    if head.stdout.strip():
        return False, "production repo has uncommitted changes"
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


# ---------------------------------------------------------------------------
# State (sanitized: PIDs + booleans only, never profile/credential data)
# ---------------------------------------------------------------------------


def write_state(cfg: HandoffConfig, pids: dict[str, int], healthy: dict) -> None:
    cfg.state_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "endpoint": f"{cfg.loopback}:{cfg.websockify_port}",
        "pids": {k: int(v) for k, v in pids.items()},
        "healthy": {k: bool(v) for k, v in healthy.items()},
    }
    cfg.state_file.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def read_state(cfg: HandoffConfig) -> dict:
    try:
        return json.loads(cfg.state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"endpoint": f"{cfg.loopback}:{cfg.websockify_port}", "pids": {}, "healthy": {}}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


class GuiHandoff:
    def __init__(self, cfg: HandoffConfig, profile: Path) -> None:
        self.cfg = cfg
        self.profile = profile
        self._procs: list[tuple[str, subprocess.Popen]] = []
        self._checks = cfg.checks or {
            "binaries": default_require_binaries,
            "ports": lambda: default_ports_free(cfg),
            "uid": lambda: default_uid_match(profile, cfg),
            "profile_unlocked": lambda: default_profile_unlocked(profile),
            "prod_clean": lambda: default_prod_repo_clean(cfg),
            "container": lambda: default_container_healthy(cfg),
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

    # -- start ------------------------------------------------------------
    def start(self) -> int:
        ok, reasons = self.preflight()
        if not ok:
            print("START REFUSED (fail-closed):", file=sys.stderr)
            for r in reasons:
                print("  - " + r, file=sys.stderr)
            return 2
        launched: list[tuple[str, subprocess.Popen]] = []
        try:
            for name, cmd in launch_order(self.cfg, self.profile):
                proc = self._popen(cmd)
                launched.append((name, proc))
                time.sleep(0.2)
            pids = {n: p.pid for n, p in launched}
            write_state(
                self.cfg,
                pids,
                {"browser_worker": self._worker_healthy()},
            )
            print(f"GUI handoff active on loopback {self.cfg.loopback}:{self.cfg.websockify_port}")
            return 0
        except Exception as exc:  # noqa: BLE001 - fail closed, restore
            print(f"START FAILURE: {exc}", file=sys.stderr)
            self._rollback(launched)
            self._restore_worker()
            return 1

    # -- stop -------------------------------------------------------------
    def stop(self) -> int:
        # Terminate GUI stack in reverse launch order using recorded PIDs
        # (works across process invocations; start/stop run separately).
        state = read_state(self.cfg)
        pids = state.get("pids", {})
        for name in reversed(teardown_order()):
            pid = pids.get(name)
            if pid and _pid_alive(pid):
                try:
                    os.kill(int(pid), signal.SIGTERM)
                except OSError:
                    pass
                for _ in range(20):
                    if not _pid_alive(pid):
                        break
                    time.sleep(0.05)
        # Safety net: kill any surviving host chromium holding this profile.
        self._kill_profile_chromium()
        # Restart ONLY browser-worker and wait healthy (control-plane untouched).
        res = self._run(build_docker_restart_worker_cmd(self.cfg))
        if res.returncode != 0:
            print("WARN: browser-worker restart returned non-zero", file=sys.stderr)
        self._wait_worker_healthy()
        try:
            self.cfg.state_file.unlink()
        except OSError:
            pass
        print("GUI handoff stopped; browser-worker restarted.")
        return 0

    def _kill_profile_chromium(self) -> None:
        try:
            out = subprocess.run(  # noqa: S603, S607
                ["pgrep", "-af", "chromium"],  # noqa: S603, S607
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:  # pragma: no cover
            return
        target = str(self.profile)
        for line in out.stdout.splitlines():
            if target in line and "operator_gui_handoff" not in line:
                try:
                    pid = int(line.split()[0])
                    os.kill(pid, signal.SIGTERM)
                except (ValueError, OSError):
                    pass

    # -- status -----------------------------------------------------------
    def status(self) -> dict:
        state = read_state(self.cfg)
        pids = state.get("pids", {})
        alive = {name: (_pid_alive(pid)) for name, pid in pids.items()}
        # A sanitized status surface: only booleans + loopback endpoint.
        return {
            "xvfb_running": bool(alive.get("xvfb", False)),
            "vnc_running": bool(alive.get("x11vnc", False)),
            "websockify_running": bool(alive.get("websockify", False)),
            "chromium_running": bool(alive.get("chromium", False)),
            "browser_worker_healthy": self._worker_healthy(),
            "profile_locked_by_other": (not self._checks["profile_unlocked"]()[0]),
            "loopback_endpoint": f"{self.cfg.loopback}:{self.cfg.websockify_port}",
        }

    # -- internals --------------------------------------------------------
    def _rollback(self, launched: list[tuple[str, subprocess.Popen]]) -> None:
        # Reverse launch order: chromium -> x11vnc -> websockify -> xvfb.
        for name in reversed([n for n, _ in launch_order(self.cfg, self.profile)]):
            for n, proc in list(launched):
                if n == name:
                    self._terminate(proc)
                    launched.remove((n, proc))

    def _worker_healthy(self) -> bool:
        ok, _ = self._checks["container"]()
        return ok

    def _restore_worker(self) -> None:
        self._run(build_docker_restart_worker_cmd(self.cfg))
        self._wait_worker_healthy()

    def _wait_worker_healthy(self, attempts: int = 30) -> None:
        for _ in range(attempts):
            if self._worker_healthy():
                return
            time.sleep(1.0)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def resolve_profile(cfg: HandoffConfig) -> Path:
    """Resolve the named Docker volume profile host path."""
    res = subprocess.run(  # noqa: S603, S607
        ["docker", "volume", "inspect", "-f", "{{.Mountpoint}}", cfg.profile_volume],  # noqa: S603, S607
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode == 0 and res.stdout.strip():
        return Path(res.stdout.strip())
    # Fallback for environments without the volume (tests inject profile).
    return cfg.production_repo / "browser-profile"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Operator-only GUI handoff for m365-ui-mcp")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("start", help="Start loopback GUI handoff (fail-closed)")
    sub.add_parser("status", help="Report sanitized status (booleans + endpoint)")
    sub.add_parser("stop", help="Stop GUI, restart browser-worker only")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = HandoffConfig()
    if args.command == "status":
        handoff = GuiHandoff(cfg, resolve_profile(cfg))
        print(json.dumps(handoff.status(), indent=2, sort_keys=True))
        return 0
    if args.command == "start":
        handoff = GuiHandoff(cfg, resolve_profile(cfg))
        return handoff.start()
    if args.command == "stop":
        handoff = GuiHandoff(cfg, resolve_profile(cfg))
        return handoff.stop()
    return 2


if __name__ == "__main__":
    sys.exit(main())
