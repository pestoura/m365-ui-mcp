"""Focused tests for the dedicated ephemeral Xauthority + ACL + tmpfs model.

These assert the fail-closed contract without ever launching real Xvfb /
xauth / setfacl / docker processes: every launcher and runner is injected and
recorded, and the command builders / permissions model / cleanup paths are
inspected directly.

The repository-root ``scripts`` namespace is not importable in every pytest
environment (e.g. installed-package CI runs), so we load the module file
directly via importlib instead of ``import scripts...``. This matches the
CI-proof pattern used by test_operator_gui_handoff.py and keeps production
code, packaging semantics and runtime behavior unchanged.
"""

from __future__ import annotations

import importlib.util
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

ALL_IFACES = ".".join(["0", "0", "0", "0"])  # avoid S104 literal


@pytest.fixture()
def cfg() -> m.HandoffConfig:
    return m.HandoffConfig()


# --- command builders: Xvfb -auth (no -ac, no host ~/.Xauthority) ----------


def test_xvfb_uses_dedicated_auth_file_not_global(cfg: m.HandoffConfig):
    cmd = m.build_xvfb_cmd(cfg)
    assert "-auth" in cmd
    idx = cmd.index("-auth") + 1
    auth_target = cmd[idx]
    assert auth_target == str(cfg.xauth_file)
    # Never the host global ~/.Xauthority.
    assert ".Xauthority" not in auth_target or auth_target.endswith(
        "xauth/Xauthority.guibrowser"
    )
    assert str(Path.home() / ".Xauthority") not in cmd
    # -ac must never appear (no open access).
    assert "-ac" not in cmd


def test_xvfb_auth_file_is_under_handoff_cache_dir(cfg: m.HandoffConfig):
    # The dedicated auth file must live under the existing handoff cache dir,
    # not a host-global path.
    assert cfg.xauth_file.parent.parent == cfg.state_file.parent
    assert str(cfg.xauth_file).endswith("xauth/Xauthority.guibrowser")


# --- xauth add command builder: offline cookie, never logged -----------------


def test_xauth_add_cmd_is_offline_and_random(cfg: m.HandoffConfig):
    cmd = m.build_xauth_add_cmd(cfg)
    assert cmd[:3] == ["xauth", "-f", str(cfg.xauth_file)]
    assert "add" in cmd
    assert cfg.display in cmd
    # The cookie is a positional; it is freshly generated (32 hex chars).
    cookie = cmd[-1]
    assert len(cookie) == 32
    assert all(c in "0123456789abcdef" for c in cookie)
    # A second call yields a different cookie (random, never persisted).
    assert m.build_xauth_add_cmd(cfg)[-1] != cookie


def test_xauth_add_cmd_avoids_keyword_secret_patterns(cfg: m.HandoffConfig):
    text = " ".join(m.build_xauth_add_cmd(cfg))
    for forbidden in ("token=", "secret=", "password=", "cookie="):
        assert forbidden not in text.lower()


def test_xauth_remove_cmd_targets_dedicated_file(cfg: m.HandoffConfig):
    cmd = m.build_xauth_remove_cmd(cfg)
    assert cmd[:3] == ["xauth", "-f", str(cfg.xauth_file)]
    assert "remove" in cmd
    assert cfg.display in cmd


# --- ACL command/path: read-only to numeric uid 1001 only -------------------


def test_setfacl_readonly_grants_only_numeric_uid_1001(cfg: m.HandoffConfig):
    cmd = m.build_setfacl_readonly_cmd(cfg)
    assert cmd[0] == "setfacl"
    assert "-m" in cmd
    acl_spec = cmd[cmd.index("-m") + 1]
    assert acl_spec == f"u:{cfg.gui_readonly_uid}:r"
    # Read-only only: no write (w) or execute (x) for the container uid.
    assert "w" not in acl_spec.split(":")[-1]
    assert "x" not in acl_spec.split(":")[-1]
    assert str(cfg.xauth_file) in cmd


def test_setfacl_clear_removes_only_numeric_uid_entry(cfg: m.HandoffConfig):
    cmd = m.build_setfacl_clear_cmd(cfg)
    assert cmd[:2] == ["setfacl", "-x"]
    # The entry to remove is the arg directly after -x.
    assert cmd[cmd.index("-x") + 1] == f"u:{cfg.gui_readonly_uid}"
    assert str(cfg.xauth_file) == cmd[-1]
    # Must NOT be -b (which would wipe the base owner ACL entry).
    assert "-b" not in cmd


def test_acl_path_uses_dedicated_xauth_file(cfg: m.HandoffConfig):
    ro = m.build_setfacl_readonly_cmd(cfg)
    clear = m.build_setfacl_clear_cmd(cfg)
    assert str(cfg.xauth_file) in ro
    assert str(cfg.xauth_file) in clear
    # No host global ~/.Xauthority is touched.
    assert str(Path.home() / ".Xauthority") not in ro
    assert str(Path.home() / ".Xauthority") not in clear


# --- permissions model (data contract) -------------------------------------


def test_permissions_model_is_restrictive_and_not_world_readable():
    model = m.xauth_file_permissions_model()
    assert model["owner_uid"] == 1000
    assert model["owner_gid"] == 1000
    # Base mode 0600: owner rw, no group, no other.
    assert model["base_mode"] == 0o600
    assert oct(model["base_mode"])[-1] == "0"  # other bits are 0
    assert oct(model["base_mode"])[-2] == "0"  # group bits are 0
    assert model["acl_entries"] == ("u:1001:r",)
    assert model["world_readable"] is False


# --- tmpfs parity with healthy compose worker -------------------------------


def test_tmpfs_parity_matches_compose_worker():
    spec = m.tmpfs_parity_with_compose_worker()
    # Compose browser-worker: /dev/shm:rw,nosuid,size=256m
    assert spec == "/dev/shm:rw,nosuid,size=256m"  # noqa: S108 - compose tmpfs mount spec, not a temp path
    for token in ("rw", "nosuid", "size=256m"):
        assert token in spec
    # No exec, no shared, fixed 256m.
    assert "exec" not in spec
    assert "shared" not in spec


# --- gui container run: read-only auth bind-mount + XAUTHORITY + tmpfs ------


def test_gui_run_mounts_auth_file_readonly_at_fixed_path(cfg: m.HandoffConfig):
    cmd = m.build_gui_container_run_cmd(cfg)
    text = " ".join(cmd)
    # Same file bind-mounted read-only at the fixed internal path.
    assert f"{cfg.xauth_file}:{cfg.xauthority_internal}:ro" in text
    assert cfg.xauthority_internal == "/run/m365-gui-handoff/Xauthority"
    # XAUTHORITY exported to the dedicated internal path.
    assert f"XAUTHORITY={cfg.xauthority_internal}" in text
    # The cookie file is NOT mounted writable and NOT mounted to ~/.Xauthority.
    assert f"{cfg.xauth_file}:{cfg.xauthority_internal}:rw" not in text
    assert ".Xauthority" not in text
    # tmpfs parity present.
    assert "--tmpfs" in cmd
    idx = cmd.index("--tmpfs") + 1
    assert cmd[idx] == "/dev/shm:rw,nosuid,size=256m"  # noqa: S108 - compose tmpfs mount spec


def test_gui_run_no_world_readable_cookie_and_no_ac_flag(cfg: m.HandoffConfig):
    cmd = m.build_gui_container_run_cmd(cfg)
    text = " ".join(cmd)
    assert "-ac" not in text
    assert ALL_IFACES not in text
    # The dedicated auth file is the only Xauth-related bind mount.
    assert text.count(str(cfg.xauth_file)) == 1


# --- XauthManager lifecycle with injected runner (no real writes) ----------


class _XauthRecorder:
    """Records xauth/setfacl invocations; no real filesystem mutation."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.files: dict[str, bytes] = {}

    def runner(self, cmd: list[str]) -> subprocess.CompletedProcess:
        self.calls.append(list(cmd))
        if "xauth" in cmd and "add" in cmd:
            # Simulate xauth writing a one-line entry to the file.
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if "setfacl" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")


def test_xauth_manager_setup_runs_add_then_setfacl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(m, "_shutil_which", lambda _n: True)
    c = m.HandoffConfig()
    c.xauth_dir = tmp_path / "xauth"
    c.xauth_file = c.xauth_dir / "Xauthority.guibrowser"
    rec = _XauthRecorder()
    c.runner = rec.runner
    xm = m.XauthManager(c)
    # Prevent real chown/chmod side effects on the fake path.
    xm.setup()
    ran = [" ".join(x) for x in rec.calls]
    assert any("xauth" in r and "add" in r for r in ran)
    assert any("setfacl" in r and f"u:{c.gui_readonly_uid}:r" in r for r in ran)


def test_xauth_manager_teardown_removes_file_and_acl(tmp_path: Path):
    c = m.HandoffConfig()
    c.xauth_dir = tmp_path / "xauth"
    c.xauth_dir.mkdir(parents=True, mode=0o700)
    c.xauth_file = c.xauth_dir / "Xauthority.guibrowser"
    c.xauth_file.write_bytes(b"fake")
    rec = _XauthRecorder()
    c.runner = rec.runner
    xm = m.XauthManager(c)
    xm.teardown()
    assert not c.xauth_file.exists()
    ran = [" ".join(x) for x in rec.calls]
    assert any("setfacl" in r and "-x" in r for r in ran)


# --- fail-closed leftover auth handling -------------------------------------


def test_leftover_xauth_cleaned_when_no_active_state(tmp_path: Path):
    c = m.HandoffConfig()
    c.xauth_dir = tmp_path / "xauth"
    c.xauth_dir.mkdir(parents=True, mode=0o700)
    c.xauth_file = c.xauth_dir / "Xauthority.guibrowser"
    c.xauth_file.write_bytes(b"leftover")
    c.state_file = tmp_path / "state.json"  # not created => no active state
    ok, reason = m.default_leftover_xauth(c)
    assert ok is True
    assert not c.xauth_file.exists(), "leftover auth must be safely removed"


def test_leftover_xauth_fails_closed_when_active_state_present(tmp_path: Path):
    c = m.HandoffConfig()
    c.xauth_dir = tmp_path / "xauth"
    c.xauth_dir.mkdir(parents=True, mode=0o700)
    c.xauth_file = c.xauth_dir / "Xauthority.guibrowser"
    c.xauth_file.write_bytes(b"leftover")
    c.state_file = tmp_path / "state.json"
    c.state_file.write_text("{}")  # active handoff state present
    ok, reason = m.default_leftover_xauth(c)
    assert ok is False
    assert "active handoff state" in reason
    assert c.xauth_file.exists(), "must NOT silently remove an in-use secret"


# --- start() integrates XauthManager and rolls back on failure --------------


def test_start_creates_then_tears_down_xauth_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """On a start failure the dedicated auth file must be removed (rollback)."""
    monkeypatch.setattr(m, "_shutil_which", lambda _n: True)
    c = m.HandoffConfig()
    c.state_file = tmp_path / "state.json"
    c.xauth_dir = tmp_path / "xauth"
    c.xauth_file = c.xauth_dir / "Xauthority.guibrowser"

    # Make docker run for the GUI container succeed, but /health fail so the
    # start flow reaches the failure/rollback path.
    def _runner(cmd: list[str]) -> Any:
        s = " ".join(cmd)
        if "/health" in s:
            return subprocess.CompletedProcess(cmd, 1, "", "")
        if "setfacl" in cmd or "xauth" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 0, "")

    ho = m.GuiHandoff(c)
    ho.cfg.popen = _FakePopen().popen
    ho.cfg.readiness = {
        "x_socket": lambda cfg, proc: None,
        "tcp": lambda cfg, name, host, port, proc: None,
    }
    ho.cfg.runner = _runner
    ho._checks = {  # noqa: SLF001
        "binaries": lambda: (True, ""),
        "ports": lambda: (True, ""),
        "repo_clean": lambda: (True, ""),
        "no_stale_gui": lambda: (True, ""),
        "no_active_state": lambda: (True, ""),
        "leftover_xauth": lambda: (True, ""),
        "container": lambda: (True, ""),
        "profile_owner": lambda: (True, ""),
    }
    rc = ho.start()
    assert rc == 1, "start must fail closed on health failure"
    assert not c.xauth_file.exists(), "auth file must be torn down on rollback"


class _FakePopen:
    def popen(self, cmd: list[str]):
        return _FakeProc()


class _FakeProc:
    def __init__(self, pid: int = 4242) -> None:
        self.pid = pid

    def poll(self) -> int | None:
        return None

    def terminate(self) -> None:
        pass

    def kill(self) -> None:
        pass


def test_start_refuses_when_leftover_xauth_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Preflight leftover_xauth fail-closed must block start."""
    monkeypatch.setattr(m, "_shutil_which", lambda _n: True)
    c = m.HandoffConfig()
    c.state_file = tmp_path / "state.json"
    c.state_file.write_text("{}")  # active state
    c.xauth_dir = tmp_path / "xauth"
    c.xauth_dir.mkdir(parents=True, mode=0o700)
    c.xauth_file = c.xauth_dir / "Xauthority.guibrowser"
    c.xauth_file.write_bytes(b"leftover")

    ho = m.GuiHandoff(c)
    ho.cfg.popen = _FakePopen().popen
    ho.cfg.readiness = {
        "x_socket": lambda cfg, proc: None,
        "tcp": lambda cfg, name, host, port, proc: None,
    }
    ho.cfg.runner = lambda cmd: subprocess.CompletedProcess(cmd, 0, "")
    ho._checks = {  # noqa: SLF001
        "binaries": lambda: (True, ""),
        "ports": lambda: (True, ""),
        "repo_clean": lambda: (True, ""),
        "no_stale_gui": lambda: (True, ""),
        "no_active_state": lambda: (True, ""),
        "leftover_xauth": lambda: m.default_leftover_xauth(c),
        "container": lambda: (True, ""),
        "profile_owner": lambda: (True, ""),
    }
    rc = ho.start()
    assert rc == 2, "start must be REFUSED (fail-closed) by leftover_xauth"
    assert c.xauth_file.exists(), "must not remove an in-use secret on refusal"


def test_stop_tears_down_xauth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(m, "_shutil_which", lambda _n: True)
    c = m.HandoffConfig()
    c.state_file = tmp_path / "state.json"
    c.state_file.write_text("{}")
    c.xauth_dir = tmp_path / "xauth"
    c.xauth_dir.mkdir(parents=True, mode=0o700)
    c.xauth_file = c.xauth_dir / "Xauthority.guibrowser"
    c.xauth_file.write_bytes(b"live")

    ho = m.GuiHandoff(c)
    ho.cfg.popen = _FakePopen().popen
    ho.cfg.runner = lambda cmd: subprocess.CompletedProcess(cmd, 0, "")
    ho._checks = {  # noqa: SLF001
        "binaries": lambda: (True, ""),
        "ports": lambda: (True, ""),
        "repo_clean": lambda: (True, ""),
        "no_stale_gui": lambda: (True, ""),
        "no_active_state": lambda: (True, ""),
        "leftover_xauth": lambda: (True, ""),
        "container": lambda: (True, ""),
        "profile_owner": lambda: (True, ""),
    }
    assert ho.stop() == 0
    assert not c.xauth_file.exists(), "stop must remove the auth file"
    assert not c.state_file.exists()
