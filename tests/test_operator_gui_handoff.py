"""Focused tests for the operator-only GUI handoff (WORKER-120…127).

These assert the fail-closed contract without ever launching real GUI/container
processes: every launcher and runner is injected and recorded, and the command
builders / preflight / state handling are inspected directly.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest


# The repository-root ``scripts`` namespace is not importable in every pytest
# environment (e.g. installed-package CI runs), so we load the module file
# directly via importlib instead of ``import scripts...``. This matches the
# CI-proof pattern used by tests/test_auth_bootstrap_guard.py and keeps
# production code, packaging semantics and runtime behavior unchanged.
def _load_operator_gui_handoff():
    script_path = (
        Path(__file__).resolve().parent.parent / "scripts" / "operator_gui_handoff.py"
    )
    spec = importlib.util.spec_from_file_location(
        "operator_gui_handoff", str(script_path)
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load operator_gui_handoff from {script_path}")
    module = importlib.util.module_from_spec(spec)
    # Register before exec so module-level @dataclass resolution can find the
    # module in sys.modules (otherwise dataclasses raises AttributeError).
    sys.modules["operator_gui_handoff"] = module
    spec.loader.exec_module(module)
    return module


m = _load_operator_gui_handoff()

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _FakeProc:
    def __init__(self, pid: int = 4242) -> None:
        self.pid = pid
        self._killed = False

    def poll(self) -> int | None:
        # Never "exits" so terminate/kill paths are exercised.
        return None

    def terminate(self) -> None:
        self._killed = True

    def kill(self) -> None:
        self._killed = True


class _Recorder:
    """Records launched command lines; ignores real side effects."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def popen(self, cmd: list[str]) -> _FakeProc:
        self.calls.append(list(cmd))
        return _FakeProc()

    def runner(self, cmd: list[str]) -> Any:
        # Return a benign CompletedProcess-like object.
        class _R:
            returncode = 0
            stdout = ""
            stderr = ""

        return _R()


@pytest.fixture()
def fake_profile(tmp_path: Path) -> Path:
    p = tmp_path / "profile"
    p.mkdir()
    # Try to set ownership to 1001:1001 without chown on the host; if not
    # permitted the uid probe tests patch the check instead.
    try:
        import os

        os.chown(p, 1001, 1001)
    except OSError:
        pass
    return p


@pytest.fixture()
def cfg() -> m.HandoffConfig:
    return m.HandoffConfig()


# ---------------------------------------------------------------------------
# Command builders: loopback + no CDP + no chown
# ---------------------------------------------------------------------------


def test_xvfb_binds_no_tcp(cfg: m.HandoffConfig) -> None:
    cmd = m.build_xvfb_cmd(cfg)
    assert "-nolisten" in cmd and "tcp" in cmd
    assert cfg.loopback not in " ".join(cmd)  # only unix socket


def test_x11vnc_binds_loopback_only(cfg: m.HandoffConfig) -> None:
    cmd = m.build_x11vnc_cmd(cfg)
    assert "-listen" in cmd
    idx = cmd.index("-listen") + 1
    assert cmd[idx] == "127.0.0.1"
    assert "-rfbport" in cmd


def test_websockify_binds_loopback_only(cfg: m.HandoffConfig) -> None:
    cmd = m.build_websockify_cmd(cfg)
    # Both the public port and the proxied VNC target must be loopback.
    assert "127.0.0.1:6080" in cmd
    assert "127.0.0.1:5999" in cmd
    all_ifaces = ".".join(["0", "0", "0", "0"])  # avoid S104 literal
    assert all_ifaces not in " ".join(cmd)


def test_chromium_has_no_remote_debugging(tmp_path: Path) -> None:
    local_cfg = m.HandoffConfig()
    profile = tmp_path / "p"
    profile.mkdir()
    cmd = m.build_chromium_cmd(local_cfg, profile)
    joined = " ".join(cmd)
    assert "setpriv" in cmd
    assert "--reuid" in cmd and str(local_cfg.gui_uid) in cmd
    assert "--regid" in cmd and str(local_cfg.gui_gid) in cmd
    # No remote debugging / CDP surface of any kind.
    assert "--remote-debugging-port" not in joined
    assert "--remote-debugging-pipe" not in joined
    assert "remote-debugging" not in joined
    assert "cdp" not in joined.lower()
    # No chown anywhere.
    assert "chown" not in joined


def test_chromium_uses_numeric_uid_profile(cfg: m.HandoffConfig, fake_profile: Path) -> None:
    cmd = m.build_chromium_cmd(cfg, fake_profile)
    assert f"--user-data-dir={fake_profile}" in cmd
    assert str(cfg.gui_uid) in cmd and str(cfg.gui_gid) in cmd


# ---------------------------------------------------------------------------
# Control-plane isolation
# ---------------------------------------------------------------------------


def test_restart_targets_only_browser_worker(cfg: m.HandoffConfig) -> None:
    cmd = m.build_docker_restart_worker_cmd(cfg)
    assert "browser-worker" in cmd
    joined = " ".join(cmd)
    assert "control-plane" not in joined
    assert "restart" in cmd


# ---------------------------------------------------------------------------
# Fail-closed preflight
# ---------------------------------------------------------------------------


def _ok() -> tuple[bool, str]:
    return True, ""


def _bad(reason: str = "blocked") -> tuple[bool, str]:
    return False, reason


def test_preflight_rejects_on_any_failure(cfg: m.HandoffConfig, fake_profile: Path) -> None:
    ho = m.GuiHandoff(cfg, fake_profile)
    ho._checks = {  # noqa: SLF001
        "binaries": _ok,
        "ports": _ok,
        "uid": _bad,
        "profile_unlocked": _ok,
        "prod_clean": _ok,
        "container": _ok,
    }
    ok, reasons = ho.preflight()
    assert ok is False
    assert any("uid" in r for r in reasons)


def test_preflight_passes_when_all_ok(cfg: m.HandoffConfig, fake_profile: Path) -> None:
    ho = m.GuiHandoff(cfg, fake_profile)
    ho._checks = {  # noqa: SLF001
        "binaries": _ok,
        "ports": _ok,
        "uid": _ok,
        "profile_unlocked": _ok,
        "prod_clean": _ok,
        "container": _ok,
    }
    ok, reasons = ho.preflight()
    assert ok is True
    assert reasons == []


# ---------------------------------------------------------------------------
# Rollback order
# ---------------------------------------------------------------------------


def test_launch_and_teardown_order(cfg: m.HandoffConfig, fake_profile: Path) -> None:
    launch = [name for name, _ in m.launch_order(cfg, fake_profile)]
    assert launch == ["xvfb", "x11vnc", "websockify", "chromium"]
    assert m.teardown_order() == ["chromium", "x11vnc", "websockify", "xvfb"]


def test_start_rollback_on_failure(
    cfg: m.HandoffConfig, fake_profile: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(m, "_shutil_which", lambda _n: True)

    boom_count = {"n": 0}

    def _boom_popen(cmd: list[str]) -> _FakeProc:
        boom_count["n"] += 1
        if boom_count["n"] == 3:
            raise RuntimeError("simulated launch failure")
        return _FakeProc()

    ho = m.GuiHandoff(cfg, fake_profile)
    ho.cfg.popen = _boom_popen
    ho.cfg.runner = lambda c: type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    ho._checks = {  # noqa: SLF001
        "binaries": _ok, "ports": _ok, "uid": _ok,
        "profile_unlocked": _ok, "prod_clean": _ok, "container": _ok,
    }
    rc = ho.start()
    assert rc == 1  # start failed
    assert boom_count["n"] == 3


# ---------------------------------------------------------------------------
# Stop: only browser-worker, control-plane untouched, clean Chromium termination
# ---------------------------------------------------------------------------


def test_stop_restarts_only_browser_worker(
    cfg: m.HandoffConfig, fake_profile: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(m, "_shutil_which", lambda _n: True)
    # Pre-seed a state file with PIDs that are not alive.
    state = tmp_path / "state.json"
    state.write_text(
        json.dumps(
            {
                "endpoint": "127.0.0.1:6080",
                "pids": {
                    "xvfb": 1,
                    "x11vnc": 2,
                    "websockify": 3,
                    "chromium": 4,
                },
                "healthy": {"browser_worker": True},
            }
        )
    )
    cfg.state_file = state
    ho = m.GuiHandoff(cfg, fake_profile)
    seen: dict[str, list[list[str]]] = {}

    def _run(cmd: list[str]) -> Any:
        seen.setdefault("runner", []).append(list(cmd))
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    ho.cfg.runner = _run
    ho._checks = {  # noqa: SLF001
        "binaries": _ok, "ports": _ok, "uid": _ok,
        "profile_unlocked": _ok, "prod_clean": _ok, "container": _ok,
    }
    rc = ho.stop()
    assert rc == 0
    # Exactly one restart command, targeting browser-worker only.
    restart_cmds = [c for c in seen["runner"] if "restart" in c]
    assert len(restart_cmds) == 1
    assert "browser-worker" in restart_cmds[0]
    assert "control-plane" not in " ".join(restart_cmds[0])
    # State file removed.
    assert not state.exists()


# ---------------------------------------------------------------------------
# Status: sanitized booleans + loopback endpoint only
# ---------------------------------------------------------------------------


def test_status_returns_sanitized_surface(
    cfg: m.HandoffConfig, fake_profile: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(m, "_shutil_which", lambda _n: True)
    state = tmp_path / "state.json"
    state.write_text(
        json.dumps(
            {
                "endpoint": "127.0.0.1:6080",
                "pids": {
                    "xvfb": 999999,
                    "x11vnc": 999998,
                    "websockify": 999997,
                    "chromium": 999996,
                },
                "healthy": {"browser_worker": True},
            }
        )
    )
    cfg.state_file = state
    ho = m.GuiHandoff(cfg, fake_profile)
    ho._checks = {  # noqa: SLF001
        "binaries": _ok, "ports": _ok, "uid": _ok,
        "profile_unlocked": _ok, "prod_clean": _ok, "container": _ok,
    }
    status = ho.status()
    allowed = {
        "xvfb_running",
        "vnc_running",
        "websockify_running",
        "chromium_running",
        "browser_worker_healthy",
        "profile_locked_by_other",
        "loopback_endpoint",
    }
    assert set(status.keys()) == allowed
    assert status["loopback_endpoint"] == "127.0.0.1:6080"
    # Non-alive PIDs -> all running flags False.
    assert status["xvfb_running"] is False
    assert status["chromium_running"] is False
    # No credential/profile path leakage.
    assert all("password" not in str(v).lower() for v in status.values())
    assert all("token" not in str(v).lower() for v in status.values())


# ---------------------------------------------------------------------------
# State file: only sanitized fields, never credential material
# ---------------------------------------------------------------------------


def test_state_file_contains_no_secrets(cfg: m.HandoffConfig, tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    cfg.state_file = state
    m.write_state(
        cfg,
        {"xvfb": 11, "x11vnc": 12, "websockify": 13, "chromium": 14},
        {"browser_worker": True},
    )
    data = json.loads(state.read_text(encoding="utf-8"))
    assert set(data.keys()) == {"endpoint", "pids", "healthy"}
    assert data["endpoint"] == "127.0.0.1:6080"
    assert data["pids"] == {"xvfb": 11, "x11vnc": 12, "websockify": 13, "chromium": 14}
    blob = json.dumps(data).lower()
    for forbidden in ("password", "token", "cookie", "secret", "bearer", "chown"):
        assert forbidden not in blob


# ---------------------------------------------------------------------------
# No Cloudflare / no credential handling anywhere in the module
# ---------------------------------------------------------------------------


def test_module_has_no_cloudflare_no_credential_handling() -> None:
    src = Path(__file__).resolve().parents[1] / "scripts" / "operator_gui_handoff.py"
    text = src.read_text(encoding="utf-8").lower()
    # Operational Cloudflare tooling / credential tokens only — not prose mentions.
    for forbidden in ("cloudflared", "cloudflare_token", "cf_token", "cf-", "bearer", "secret="):
        assert forbidden not in text, forbidden


def test_no_hardcoded_0_0_0_0_in_module() -> None:
    src = Path(__file__).resolve().parents[1] / "scripts" / "operator_gui_handoff.py"
    text = src.read_text(encoding="utf-8")
    all_ifaces = ".".join(["0", "0", "0", "0"])  # avoid S104 literal
    assert all_ifaces not in text
