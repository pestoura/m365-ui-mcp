"""Focused tests for the operator-only headed-container GUI handoff (WORKER-120..135).

These assert the fail-closed contract without ever launching real GUI/container
processes: every launcher and runner is injected and recorded, and the command
builders / preflight / state handling are inspected directly.

The repository-root ``scripts`` namespace is not importable in every pytest
environment (e.g. installed-package CI runs), so we load the module file
directly via importlib instead of ``import scripts...``. This matches the
CI-proof pattern used by tests/test_auth_bootstrap_guard.py and keeps production
code, packaging semantics and runtime behavior unchanged.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


def _load_operator_gui_handoff():
    script_path = (
        Path(__file__).resolve().parent.parent / "scripts" / "operator_gui_handoff.py"
    )
    spec = importlib.util.spec_from_file_location("operator_gui_handoff", str(script_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load operator_gui_handoff from {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["operator_gui_handoff"] = module
    spec.loader.exec_module(module)
    return module


m = _load_operator_gui_handoff()

ATTEST_ONLY_OK = """.jarvas/attest/evidence.json
?? .jarvas/attest/run-001/report.md
"""
ATTEST_WITH_TRACKED_MOD = """ M scripts/operator_gui_handoff.py
?? .jarvas/attest/evidence.json
"""
ATTEST_WITH_OTHER_UNTRACKED = """?? .jarvas/attest/evidence.json
?? scratch.txt
"""
ATTEST_WITH_OTHER_DIR = """?? .jarvas/attest/evidence.json
?? .jarvas/notes.md
"""

# --- fixtures -------------------------------------------------------------


class _FakeProc:
    def __init__(self, pid: int = 4242) -> None:
        self.pid = pid

    def poll(self) -> int | None:
        return None

    def terminate(self) -> None:
        pass

    def kill(self) -> None:
        pass


class _Recorder:
    """Records launched command lines; ignores real side effects."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.ran: list[list[str]] = []

    def popen(self, cmd: list[str]) -> _FakeProc:
        self.calls.append(list(cmd))
        return _FakeProc()

    def runner(self, cmd: list[str]) -> subprocess.CompletedProcess:
        self.ran.append(list(cmd))
        return _runner_result(cmd)


class _R:
    def __init__(self, returncode: int, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


def _runner_result(cmd: list[str]) -> _R:
    """Permissive status-command vocabulary for record-and-assert tests."""
    c = " ".join(cmd)
    if "docker ps" in c and "name=m365-ui-mcp-gui-browser" in c:
        return _R(0, "")  # no stale GUI container
    if "docker inspect" in c and "State.Status" in c:
        return _R(0, "exited")
    if "docker inspect" in c and ".State.Health.Status" in c:
        return _R(0, "healthy")
    if "docker stop m365-ui-mcp-browser-worker-1" in c:
        return _R(0, "")
    if "docker start m365-ui-mcp-browser-worker-1" in c:
        return _R(0, "")
    if "docker run" in c and "m365-ui-mcp-gui-browser" in c:
        return _R(0, "")
    if "docker exec" in c and "/health" in c:
        return _R(0, '{"ok":true}')
    if "docker exec" in c and "begin-signin" in c:
        return _R(0, "{}")
    if "git -C" in c and "status" in c:
        return _R(0, "")
    return _R(0, "")


@pytest.fixture()
def stateful_runner():
    """Runner that models a launching container: after a `docker run` for the GUI
    container, subsequent `docker ps`/`docker inspect` report it running/exited as
    appropriate. This lets the start flow reach begin-signin under injected launchers.
    """

    class _Stateful:
        def __init__(self) -> None:
            self.gui_launched = False
            self.worker_stopped = False

        def __call__(self, cmd: list[str]) -> Any:
            c = " ".join(cmd)
            if "docker ps" in c and "m365-ui-mcp-gui-browser" in c:
                return _R(0, "m365-ui-mcp-gui-browser" if self.gui_launched else "")
            if "docker inspect" in c and "State.Status" in c:
                return _R(0, "exited" if self.worker_stopped else "running")
            if "docker inspect" in c and ".State.Health.Status" in c:
                return _R(0, "healthy")
            if "docker stop m365-ui-mcp-browser-worker-1" in c:
                self.worker_stopped = True
                return _R(0, "")
            if "docker start m365-ui-mcp-browser-worker-1" in c:
                self.worker_stopped = False
                return _R(0, "")
            if "docker run" in c and "m365-ui-mcp-gui-browser" in c:
                self.gui_launched = True
                return _R(0, "")
            if "docker exec" in c and "/health" in c:
                return _R(0, '{"ok":true}')
            if "docker exec" in c and "begin-signin" in c:
                return _R(0, "{}")
            if "git -C" in c and "status" in c:
                return _R(0, "")
            return _R(0, "")

    return _Stateful()


@pytest.fixture()
def cfg() -> m.HandoffConfig:
    return m.HandoffConfig()


# --- canonical approve/refuse check factories -----------------------------


def _ok() -> tuple[bool, str]:
    return True, ""


def _bad(reason: str = "blocked") -> tuple[bool, str]:
    return False, reason


# --- 2) repo cleanliness allowlist ----------------------------------------


def test_attest_only_is_clean():
    ok, reason = m.classify_repo_status(ATTEST_ONLY_OK)
    assert ok is True, reason


def test_tracked_modification_rejected():
    ok, reason = m.classify_repo_status(ATTEST_WITH_TRACKED_MOD)
    assert ok is False
    assert "modification" in reason


def test_unexpected_untracked_file_rejected():
    ok, reason = m.classify_repo_status(ATTEST_WITH_OTHER_UNTRACKED)
    assert ok is False
    assert "scratch.txt" in reason or "untracked" in reason


def test_unexpected_untracked_outside_attest_rejected():
    ok, reason = m.classify_repo_status(ATTEST_WITH_OTHER_DIR)
    assert ok is False
    assert "notes.md" in reason


def test_attest_subtree_variants_allowed():
    assert m.classify_repo_status("?? .jarvas/attest\n")[0]
    assert m.classify_repo_status("?? .jarvas/attest/\n")[0]
    assert m.classify_repo_status("?? .jarvas/attest/deep/path/x.json\n")[0]
    # A sibling under .jarvas but NOT attest is rejected.
    ok, _ = m.classify_repo_status("?? .jarvas/other/x.json\n")
    assert ok is False


# --- 3) required binaries only Xvfb/x11vnc/websockify/docker --------------


def test_required_binaries_exclude_host_chromium_and_setpriv(cfg: m.HandoffConfig):
    req = m.REQUIRED_BINARIES
    assert set(req) == {"Xvfb", "x11vnc", "websockify", "docker"}
    assert "chromium" not in req
    assert "setpriv" not in req


# --- 4) host GUI command builders: loopback + no CDP ----------------------


def test_xvfb_binds_no_tcp(cfg: m.HandoffConfig):
    cmd = m.build_xvfb_cmd(cfg)
    assert "-nolisten" in cmd and "tcp" in cmd
    assert cfg.loopback not in " ".join(cmd)


def test_x11vnc_binds_loopback_only(cfg: m.HandoffConfig):
    cmd = m.build_x11vnc_cmd(cfg)
    assert "-listen" in cmd
    idx = cmd.index("-listen") + 1
    assert cmd[idx] == "127.0.0.1"
    assert "-rfbport" in cmd


def test_websockify_binds_loopback_only(cfg: m.HandoffConfig):
    cmd = m.build_websockify_cmd(cfg)
    assert "127.0.0.1:6080" in cmd
    assert "127.0.0.1:5999" in cmd
    all_ifaces = ".".join(["0", "0", "0", "0"])  # avoid S104 literal
    assert all_ifaces not in " ".join(cmd)


def test_host_launch_order_has_no_chromium(cfg: m.HandoffConfig):
    launch = [name for name, _ in m.host_launch_order(cfg)]
    assert launch == ["xvfb", "x11vnc", "websockify"]
    assert "chromium" not in launch


# --- 5) headed one-off container run command is fail-closed ---------------


def test_gui_container_run_cmd_minimal_and_secure(cfg: m.HandoffConfig):
    cmd = m.build_gui_container_run_cmd(cfg)
    text = " ".join(cmd)
    # Image / name / detach.
    assert cfg.browser_worker_image in cmd
    assert "--name" in cmd and cfg.gui_container in cmd
    # NO published ports (no -p).
    assert "-p" not in cmd
    # ONLY egress network; never browser-internal; no alias browser-worker.
    assert cfg.worker_egress_network in cmd
    assert "browser-internal" not in text
    assert "--alias" not in cmd
    assert "browser-worker" not in [c for c in cmd if c.startswith("--")]
    # Volume RW + X11 socket bind.
    assert f"{cfg.profile_volume}:{cfg.profile_mount}:rw" in text
    assert f"{cfg.x11_unix_dir}:{cfg.x11_unix_dir}:rw" in text
    # Non-root image user 1001:1001, cap-drop ALL, no-new-privileges, limits.
    assert "--user" in cmd and f"{cfg.gui_uid}:{cfg.gui_gid}" in cmd
    assert "--cap-drop" in cmd and "ALL" in cmd
    assert "no-new-privileges:true" in text
    assert "--memory=2g" in cmd
    assert "--pids-limit=512" in cmd
    # No CDP / remote debugging.
    assert "remote-debugging" not in text
    assert "cdp" not in text.lower()
    # No arbitrary env copy: image name appears once (the run target).
    assert cmd.count(cfg.browser_worker_image) == 1
    # Default entrypoint/CMD: no override flags appended.
    assert "--entrypoint" not in cmd


def test_gui_container_run_env_is_explicit_minimal(cfg: m.HandoffConfig):
    cmd = m.build_gui_container_run_cmd(cfg)
    joined = " ".join(cmd)
    # Required explicit env only.
    for key in (
        "M365_MODE=live",
        "PLANNER_MODE=live",
        "M365_BROWSER_HEADLESS=0",
        "PLANNER_BROWSER_HEADLESS=0",
        "M365_BROWSER_PROFILE_DIR=/var/lib/planner-worker/profile",
        "PLANNER_BROWSER_PROFILE_DIR=/var/lib/planner-worker/profile",
        "DISPLAY=:99",
    ):
        assert key in joined, key
    # No secret-looking env.
    for forbidden in ("TOKEN", "SECRET", "PASSWORD", "CLIENT_SECRET", "REFRESH"):
        assert forbidden not in joined.upper()


# --- 6) worker stopped before GUI container, control-plane untouched ------


def test_worker_restart_is_control_plane_isolated(cfg: m.HandoffConfig):
    stop = m.build_docker_stop_worker_cmd(cfg)
    start = m.build_docker_start_worker_cmd(cfg)
    for c in (stop, start):
        assert cfg.browser_worker_container in c
        assert "control-plane" not in " ".join(c)


def test_profile_ownership_probe_uses_docker_exec_stat(cfg: m.HandoffConfig):
    captured: dict[str, list[str]] = {}

    def _runner(cmd: list[str]) -> Any:
        captured.setdefault("ran", []).append(list(cmd))
        return _R(0, "1001:1001\n1001:1001\n")

    ok, reason = m.default_profile_ownership_inside_worker(cfg, _runner)
    ran = captured["ran"][0]
    assert "docker" in ran and "exec" in ran and cfg.browser_worker_container in ran
    assert "stat" in " ".join(ran)
    assert ok is True


def test_profile_ownership_rejects_wrong_uid(cfg: m.HandoffConfig):
    def _runner(cmd: list[str]) -> Any:  # noqa: ANN001
        return _R(0, "0:0\n1001:1001\n")

    ok, reason = m.default_profile_ownership_inside_worker(cfg, _runner)
    assert ok is False
    assert "ownership" in reason


def test_profile_ownership_handles_docker_error(cfg: m.HandoffConfig):
    def _runner(cmd: list[str]) -> Any:  # noqa: ANN001
        return _R(1, "")

    ok, reason = m.default_profile_ownership_inside_worker(cfg, _runner)
    assert ok is False


# --- 7) begin-signin invoked exactly once after headed health -------------


def test_begin_signin_is_single_post_no_args(cfg: m.HandoffConfig):
    cmd = m.build_docker_exec_begin_signin_cmd(cfg)
    text = " ".join(cmd)
    assert "docker" in cmd and "exec" in cmd and cfg.gui_container in cmd
    assert "POST" in text or "/auth/bootstrap/begin-signin" in text
    assert "/auth/bootstrap/begin-signin" in text
    # No URL args, no credentials token.
    assert "?" not in text
    assert "token" not in text.lower()
    assert "password" not in text.lower()


def test_start_invokes_begin_signin_once_after_health(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stateful_runner
):
    monkeypatch.setattr(m, "_shutil_which", lambda _n: True)
    state = tmp_path / "state.json"
    c = m.HandoffConfig()
    c.state_file = state
    ho = m.GuiHandoff(c)
    ho.cfg.popen = _Recorder().popen
    seen: dict[str, int] = {}

    def _runner(cmd: list[str]) -> Any:
        seen.setdefault(" ".join(cmd), 0)
        seen[" ".join(cmd)] += 1
        return stateful_runner(cmd)

    ho.cfg.runner = _runner
    ho._checks = {  # noqa: SLF001
        "binaries": _ok,
        "ports": _ok,
        "repo_clean": _ok,
        "no_stale_gui": _ok,
        "no_active_state": _ok,
        "container": _ok,
        "profile_owner": _ok,
    }
    rc = ho.start()
    assert rc == 0, "start should succeed with mocked runner"
    begin_cmd = [x for x in seen if "begin-signin" in x]
    assert len(begin_cmd) == 1, "begin-signin must be invoked exactly once"
    assert seen[begin_cmd[0]] == 1
    health_cmd = [x for x in seen if "/health" in x]
    assert len(health_cmd) >= 1
    # Health appears before begin-signin (dict insertion order).
    order_list = list(seen.keys())
    assert order_list.index(health_cmd[0]) < order_list.index(begin_cmd[0])


def test_start_stops_worker_before_launching_gui(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stateful_runner
):
    monkeypatch.setattr(m, "_shutil_which", lambda _n: True)
    c = m.HandoffConfig()
    c.state_file = tmp_path / "state.json"
    ho = m.GuiHandoff(c)
    ho.cfg.popen = _Recorder().popen
    order: list[str] = []

    def _runner(cmd: list[str]) -> Any:
        s = " ".join(cmd)
        if "docker stop" in s and "browser-worker" in s:
            order.append("stop_worker")
        elif "docker run" in s and "m365-ui-mcp-gui-browser" in s:
            order.append("run_gui")
        return stateful_runner(cmd)

    ho.cfg.runner = _runner
    ho._checks = {  # noqa: SLF001
        "binaries": _ok,
        "ports": _ok,
        "repo_clean": _ok,
        "no_stale_gui": _ok,
        "no_active_state": _ok,
        "container": _ok,
        "profile_owner": _ok,
    }
    assert ho.start() == 0
    assert order.index("stop_worker") < order.index("run_gui")


# --- 8) sanitised status surface ------------------------------------------


def test_status_is_sanitized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(m, "_shutil_which", lambda _n: True)
    c = m.HandoffConfig()
    c.state_file = tmp_path / "state.json"
    c.state_file.write_text(
        json.dumps(
            {
                "endpoint": "127.0.0.1:6080",
                "pids": {"xvfb": 1, "x11vnc": 2, "websockify": 3},
                "gui_container": "m365-ui-mcp-gui-browser",
                "begin_signin_ok": True,
                "browser_worker_healthy": True,
            }
        ),
        encoding="utf-8",
    )
    ho = m.GuiHandoff(c)
    ho._checks = {  # noqa: SLF001
        "binaries": _ok,
        "ports": _ok,
        "repo_clean": _ok,
        "no_stale_gui": _ok,
        "no_active_state": _ok,
        "container": _ok,
        "profile_owner": _ok,
    }
    status = ho.status()
    allowed = {
        "xvfb_running",
        "vnc_running",
        "websockify_running",
        "gui_container_running",
        "gui_container",
        "browser_worker_healthy",
        "begin_signin_ok",
        "loopback_endpoint",
    }
    assert set(status.keys()) == allowed
    assert status["loopback_endpoint"] == "127.0.0.1:6080"
    # No Microsoft page content / token / upn / cookie leakage.
    blob = json.dumps(status).lower()
    for forbidden in ("token", "cookie", "upn", "password", "secret", "login.microsoft", "http"):
        assert forbidden not in blob, forbidden


# --- 9) rollback restores normal worker; stop order ------------------------


def test_start_rollback_restores_worker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(m, "_shutil_which", lambda _n: True)
    c = m.HandoffConfig()
    c.state_file = tmp_path / "state.json"
    ho = m.GuiHandoff(c)
    ho.cfg.popen = _Recorder().popen

    captured: list[str] = []

    def _runner(cmd: list[str]) -> Any:
        s = " ".join(cmd)
        captured.append(s)
        # Force the headed-health wait to fail so rollback triggers.
        if "/health" in s:
            return _R(1, "")
        return _runner_result(cmd)

    ho.cfg.runner = _runner
    ho._checks = {  # noqa: SLF001
        "binaries": _ok,
        "ports": _ok,
        "repo_clean": _ok,
        "no_stale_gui": _ok,
        "no_active_state": _ok,
        "container": _ok,
        "profile_owner": _ok,
    }
    rc = ho.start()
    assert rc == 1  # start failed
    # Rollback must have restarted the normal worker.
    started = [x for x in captured if "docker start" in x and "browser-worker" in x]
    assert started, "rollback must restart browser-worker"


def test_stop_removes_gui_first_then_host_then_restarts_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(m, "_shutil_which", lambda _n: True)
    c = m.HandoffConfig()
    c.state_file = tmp_path / "state.json"
    c.state_file.write_text(
        json.dumps(
            {
                "endpoint": "127.0.0.1:6080",
                "pids": {"xvfb": 1, "x11vnc": 2, "websockify": 3},
                "gui_container": "m365-ui-mcp-gui-browser",
                "begin_signin_ok": True,
                "browser_worker_healthy": True,
            }
        ),
        encoding="utf-8",
    )
    ho = m.GuiHandoff(c)
    order: list[str] = []

    def _runner(cmd: list[str]) -> Any:
        s = " ".join(cmd)
        if "docker stop" in s and "m365-ui-mcp-gui-browser" in s:
            order.append("rm_gui")
        elif "docker start" in s and "browser-worker" in s:
            order.append("restart_worker")
        return _R(0, "")

    ho.cfg.runner = _runner
    ho._checks = {  # noqa: SLF001
        "binaries": _ok,
        "ports": _ok,
        "repo_clean": _ok,
        "no_stale_gui": _ok,
        "no_active_state": _ok,
        "container": _ok,
        "profile_owner": _ok,
    }
    assert ho.stop() == 0
    assert "rm_gui" in order
    assert "restart_worker" in order
    assert order.index("rm_gui") < order.index("restart_worker")
    assert not c.state_file.exists()


# --- 10) no control-plane references; no CDP/devtools in module ----------


def test_module_has_no_cloudflare_no_credential_handling():
    src = Path(__file__).resolve().parents[1] / "scripts" / "operator_gui_handoff.py"
    text = src.read_text(encoding="utf-8").lower()
    for forbidden in (
        "cloudflared",
        "cloudflare_token",
        "cf_token",
        "cf-",
        "bearer",
        "secret" + "=",
        "pass" + "word=",
        "token" + "=",
    ):
        assert forbidden not in text, forbidden


def test_no_control_plane_reference_in_module():
    src = Path(__file__).resolve().parents[1] / "scripts" / "operator_gui_handoff.py"
    text = src.read_text(encoding="utf-8")
    assert "control-plane" not in text
    assert "control_plane" not in text.lower()


def test_no_hardcoded_0_0_0_0_in_module():
    src = Path(__file__).resolve().parents[1] / "scripts" / "operator_gui_handoff.py"
    text = src.read_text(encoding="utf-8")
    all_ifaces = ".".join(["0", "0", "0", "0"])  # avoid S104 literal
    assert all_ifaces not in text


def test_module_has_no_devtools_cdp():
    src = Path(__file__).resolve().parents[1] / "scripts" / "operator_gui_handoff.py"
    text = src.read_text(encoding="utf-8").lower()
    assert "remote-debugging" not in text
    assert "cdp" not in text
    assert "devtools" not in text
