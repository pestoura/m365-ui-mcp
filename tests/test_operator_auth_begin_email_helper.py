"""Tests for the OPERATOR-ONLY AUTH-106 email-stage helper.

Coverage:

* the helper takes no arguments (fixed store/route/container);
* it decrypts ONLY the username/email credential and never the password one;
* the decrypted value is passed to the delivery step via STDIN only, never in
  argv, never in the environment, and never written to a file;
* the body sent to the worker is the closed ``{email}`` contract;
* the in-container client source refuses anything but that closed contract;
* decrypt failure, worker rejection, worker unreachability and a malformed
  response all fail closed with sanitized, value-free messages;
* success reports only ``ok=true`` plus the worker's closed ``auth_state``, and
  the credential value is never printed.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

_HELPER = (
    Path(__file__).resolve().parents[1] / "scripts" / "operator_auth_begin_email.py"
)

_FAKE_EMAIL = "operator@contoso.example"


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location("operator_auth_begin_email", _HELPER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def helper() -> Any:
    return _load_module()


class _Completed:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_rejects_any_argument(helper: Any, capsys: pytest.CaptureFixture[str]) -> None:
    assert helper.main(["--email", _FAKE_EMAIL]) == helper.EmailStageStatus.USAGE
    err = capsys.readouterr().err
    assert "takes no arguments" in err
    assert _FAKE_EMAIL not in err


def test_password_credential_is_never_referenced(helper: Any) -> None:
    source = _HELPER.read_text(encoding="utf-8")
    # The helper must not name the password credential file at all.
    assert "m365-ui-mcp.password.cred" not in source
    assert helper._USERNAME_CRED == "m365-ui-mcp.username.cred"


def test_decrypts_only_username_credential(helper: Any, monkeypatch: Any) -> None:
    decrypted: list[str] = []

    def fake_run(cmd: list[str], **kwargs: Any) -> _Completed:
        decrypted.append(cmd[-1])
        return _Completed(stdout=_FAKE_EMAIL + "\n")

    monkeypatch.setattr(helper.subprocess, "run", fake_run)
    monkeypatch.setattr(Path, "is_file", lambda self: True)

    assert helper._decrypt_credential(helper._USERNAME_CRED) == _FAKE_EMAIL
    assert len(decrypted) == 1
    assert decrypted[0].endswith("m365-ui-mcp.username.cred")


def test_value_goes_over_stdin_not_argv_or_env(helper: Any, monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_run(cmd: list[str], **kwargs: Any) -> _Completed:
        captured["cmd"] = cmd
        captured["input"] = kwargs.get("input")
        captured["env"] = kwargs.get("env")
        return _Completed(stdout=json.dumps({"ok": True, "auth_state": "UNKNOWN"}))

    monkeypatch.setattr(helper.subprocess, "run", fake_run)

    result = helper._submit_email_stage(_FAKE_EMAIL)
    assert result == {"ok": True, "auth_state": "UNKNOWN"}

    # The value travels ONLY through stdin.
    assert json.loads(captured["input"]) == {"email": _FAKE_EMAIL}
    assert all(_FAKE_EMAIL not in part for part in captured["cmd"])
    # No custom environment is constructed to carry the value.
    assert captured["env"] is None
    # stdin must be wired for the exec.
    assert "-i" in captured["cmd"]


def test_in_container_client_enforces_closed_contract(helper: Any) -> None:
    client = helper._IN_CONTAINER_CLIENT
    assert 'set(parsed) != {"email"}' in client
    assert helper._WORKER_ENDPOINT in client
    # The client must not reference a password field at all.
    assert "passwd" not in client.lower()


def test_decrypt_failure_fails_closed(
    helper: Any, monkeypatch: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(cred_name: str) -> str:
        raise RuntimeError("systemd-creds decrypt failed for cred (rc=1)")

    monkeypatch.setattr(helper, "_decrypt_credential", boom)
    assert helper.main([]) == helper.EmailStageStatus.DECRYPT_FAILED
    captured = capsys.readouterr()
    assert "decrypt failed" in captured.err
    assert _FAKE_EMAIL not in captured.err + captured.out


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("WORKER_REJECTED", 4),
        ("WORKER_UNREACHABLE", 5),
        ("BAD_RESPONSE", 6),
    ],
)
def test_delivery_failures_fail_closed_sanitized(
    helper: Any,
    monkeypatch: Any,
    capsys: pytest.CaptureFixture[str],
    reason: str,
    expected: int,
) -> None:
    monkeypatch.setattr(helper, "_decrypt_credential", lambda name: _FAKE_EMAIL)

    def boom(email: str) -> dict[str, object]:
        raise RuntimeError(reason)

    monkeypatch.setattr(helper, "_submit_email_stage", boom)

    assert helper.main([]) == expected
    captured = capsys.readouterr()
    assert _FAKE_EMAIL not in captured.err + captured.out


def test_success_reports_only_sanitized_state(
    helper: Any, monkeypatch: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(helper, "_decrypt_credential", lambda name: _FAKE_EMAIL)
    monkeypatch.setattr(
        helper,
        "_submit_email_stage",
        lambda email: {"ok": True, "auth_state": "UNKNOWN"},
    )

    assert helper.main([]) == helper.EmailStageStatus.OK
    captured = capsys.readouterr()
    assert captured.out.strip() == "ok=true auth_state=UNKNOWN"
    assert _FAKE_EMAIL not in captured.out + captured.err


def test_unexpected_shape_is_bad_response(
    helper: Any, monkeypatch: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(helper, "_decrypt_credential", lambda name: _FAKE_EMAIL)
    monkeypatch.setattr(helper, "_submit_email_stage", lambda email: {"ok": False})

    assert helper.main([]) == helper.EmailStageStatus.BAD_RESPONSE
    assert _FAKE_EMAIL not in capsys.readouterr().err


def test_fixed_targets_are_not_configurable(helper: Any) -> None:
    source = _HELPER.read_text(encoding="utf-8")
    # No environment-driven override of store, route or container.
    assert "os.getenv" not in source
    assert "os.environ" not in source
    assert helper._WORKER_CONTAINER == "planner-mcp-browser-worker-1"
    assert helper._WORKER_ENDPOINT.startswith("http://127.0.0.1:8090/")
    assert subprocess is not None
