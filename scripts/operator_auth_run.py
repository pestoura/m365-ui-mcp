#!/usr/bin/env python3
"""Deterministic operator-only Microsoft sign-in orchestrator.

Canonical flow:

    navigate -> begin-signin -> resolve-signin-surface
        -> require EMAIL_ENTRY / discover-email UNIQUE_MATCH
        -> operator-submit -> observe MFA -> Hermes/Telegram
        -> human Microsoft Authenticator approval -> AUTHENTICATED

The worker remains headless-only. This host-side conductor never approves MFA,
never exposes browser content, and never gives Telegram credentials to the M365
component. A uniquely resolved two-digit Microsoft number is the only value
relayed to Hermes. Every ambiguous or unsupported condition fails closed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

_CREDSTORE_DIR = Path(os.path.expanduser("~")) / ".local" / "lib" / "credstore.encrypted"
_SYSTEMD_CREDS = "/usr/bin/systemd-creds"
_DOCKER = "/usr/bin/docker"
_ENV = "/usr/bin/env"

_USERNAME_CRED = "m365-ui-mcp.username.cred"
_PASSWORD_CRED = "m365-ui-mcp.password.cred"  # noqa: S105 - credential file name only
_WORKER_CONTAINER = "m365-ui-mcp-browser-worker-1"

_NAVIGATE = "http://127.0.0.1:8090/auth/bootstrap/navigate"
_BEGIN_SIGNIN = "http://127.0.0.1:8090/auth/bootstrap/begin-signin"
_RESOLVE_SURFACE = "http://127.0.0.1:8090/auth/bootstrap/resolve-signin-surface"
_OPERATOR_SUBMIT = "http://127.0.0.1:8090/auth/bootstrap/operator-submit"
_DISCOVER_EMAIL = "http://127.0.0.1:8090/auth/bootstrap/discover-email"
_OBSERVE = "http://127.0.0.1:8090/auth/bootstrap/observe"

_DISCOVER_PROBES = 6
_DISCOVER_INTERVAL_S = 3.0
_MFA_MAX_POLLS = 120
_MFA_POLL_INTERVAL_S = 2.0

_IN_CONTAINER_SUBMIT_CLIENT = (
    'ENDPOINT = "' + _OPERATOR_SUBMIT + '"\n'
    """
import json, sys, urllib.error, urllib.request

payload = sys.stdin.buffer.read()
try:
    parsed = json.loads(payload)
except Exception:
    sys.stderr.write("ERROR: in-container client received a malformed body\\n")
    raise SystemExit(6)
if not isinstance(parsed, dict) or set(parsed) != {"email", "password"}:
    sys.stderr.write("ERROR: in-container client requires the closed {email,password} contract\\n")
    raise SystemExit(6)

request = urllib.request.Request(
    ENDPOINT,
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(request, timeout=60) as response:
        sys.stdout.write(response.read().decode("utf-8"))
except urllib.error.HTTPError as exc:
    sys.stderr.write("ERROR: worker rejected sign-in submit (http={})\\n".format(exc.code))
    raise SystemExit(4) from None
except urllib.error.URLError as exc:
    sys.stderr.write("ERROR: worker loopback unreachable ({})\\n".format(exc.reason))
    raise SystemExit(5) from None
"""
)


class RunStatus:
    """Sanitized process exit codes."""

    OK = 0
    USAGE = 2
    DECRYPT_FAILED = 3
    SUBMIT_REJECTED = 4
    SUBMIT_UNREACHABLE = 5
    BAD_RESPONSE = 6
    NAVIGATE_FAILED = 10
    BEGIN_SIGNIN_FAILED = 11
    RESOLVE_FAILED = 12
    SURFACE_GATE_FAILED = 13
    OBSERVE_FAILED = 14
    MFA_AMBIGUOUS = 15
    MFA_NOTIFY_FAILED = 16
    MFA_TIMEOUT = 17
    MFA_BLOCKED = 18


class _StepFailed(Exception):
    """Internal fail-closed signal containing only a fixed step label."""


def _docker_exec_post(endpoint: str) -> tuple[int, str]:
    """POST an empty body to one fixed loopback worker route."""
    proc = subprocess.run(  # noqa: S603 - fixed binary/container, no shell
        [
            _DOCKER,
            "exec",
            _WORKER_CONTAINER,
            "curl",
            "-sS",
            "-o",
            "-",
            "-w",
            "\n",
            "-X",
            "POST",
            "-H",
            "Content-Length: 0",
            "--fail-with-body",
            endpoint,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout or proc.stderr).strip()


def _docker_exec_get(endpoint: str) -> tuple[int, str]:
    """GET one fixed loopback worker route."""
    proc = subprocess.run(  # noqa: S603 - fixed binary/container, no shell
        [
            _DOCKER,
            "exec",
            _WORKER_CONTAINER,
            "curl",
            "-sS",
            "-o",
            "-",
            "-w",
            "\n",
            "-X",
            "GET",
            "--fail-with-body",
            endpoint,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout or proc.stderr).strip()


def _require_endpoint_ok(label: str, endpoint: str, retries: int = 1) -> None:
    """Require one operator step to succeed within its bounded re-probe count."""
    code = 1
    for attempt in range(retries):
        code, _body = _docker_exec_post(endpoint)
        if code == 0:
            return
        if attempt + 1 < retries:
            time.sleep(_DISCOVER_INTERVAL_S)
    sys.stderr.write(
        f"ERROR: operator step '{label}' failed (exit={code}); "
        "browser-worker rejected or unreachable.\n"
    )
    raise _StepFailed(label)


def _discover_email_probe() -> tuple[int, str]:
    return _docker_exec_get(_DISCOVER_EMAIL)


def _discover_email_gate(
    probe: Callable[[], tuple[int, str]] | None = None,
) -> bool:
    """Require both fixed email-entry selector keys to be UNIQUE_MATCH."""
    if probe is None:
        probe = _discover_email_probe
    for _ in range(_DISCOVER_PROBES):
        code, body = probe()
        if code != 0:
            return False
        try:
            data = json.loads(body)
        except Exception:
            return False
        if not isinstance(data, dict) or data.get("ok") is not True:
            return False
        keys = data.get("keys") or []
        if len(keys) == 2 and all(
            isinstance(item, dict) and item.get("result") == "UNIQUE_MATCH"
            for item in keys
        ):
            return True
        time.sleep(_DISCOVER_INTERVAL_S)
    return False


def _decrypt_credential(cred_name: str) -> str:
    """Decrypt one fixed systemd credential to memory only."""
    cred_path = _CREDSTORE_DIR / cred_name
    if not cred_path.is_file():
        raise RuntimeError(f"encrypted credential not found: {cred_name}")
    proc = subprocess.run(  # noqa: S603 - fixed binary/path, no shell
        [_SYSTEMD_CREDS, "decrypt", "--user", str(cred_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"systemd-creds decrypt failed for {cred_name} "
            f"(rc={proc.returncode}); see operator logs"
        )
    value = proc.stdout.rstrip("\n")
    if not value:
        raise RuntimeError(f"decrypted credential is empty: {cred_name}")
    return value


def _run_in_container_submit(payload: str) -> tuple[int, str]:
    """Pass the closed credential JSON to the worker via docker-exec stdin."""
    proc = subprocess.run(  # noqa: S603 - fixed binary/container, no shell
        [
            _DOCKER,
            "exec",
            "-i",
            _WORKER_CONTAINER,
            "python3",
            "-c",
            _IN_CONTAINER_SUBMIT_CLIENT,
        ],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout or proc.stderr).strip()


def _submit_loopback(email: str, password: str) -> dict[str, object]:
    """Submit memory-only credentials and parse the sanitized response."""
    payload = json.dumps({"email": email, "password": password})
    code, body = _run_in_container_submit(payload)
    if code == RunStatus.SUBMIT_REJECTED:
        raise RuntimeError("SUBMIT_REJECTED")
    if code == RunStatus.SUBMIT_UNREACHABLE:
        raise RuntimeError("SUBMIT_UNREACHABLE")
    if code != 0:
        raise RuntimeError("BAD_RESPONSE")
    try:
        parsed = json.loads(body)
    except Exception:
        raise RuntimeError("BAD_RESPONSE") from None
    if not isinstance(parsed, dict):
        raise RuntimeError("BAD_RESPONSE")
    return parsed


def _observe_probe() -> tuple[int, str]:
    """Read one sanitized post-submit auth observation."""
    return _docker_exec_get(_OBSERVE)


def _notify_mfa_via_hermes(number: str) -> bool:
    """Send one sanitized MFA number to Hermes' configured Telegram home."""
    message = (
        "M365 — Aprova o início de sessão no Microsoft Authenticator "
        f"com o número: {number}\n"
    )
    try:
        proc = subprocess.run(  # noqa: S603 - fixed Hermes action, no shell
            [
                _ENV,
                "hermes",
                "send",
                "--to",
                "telegram",
                "--quiet",
                "--file",
                "-",
            ],
            input=message,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return proc.returncode == 0


def _await_mfa_and_authenticate(
    probe: Callable[[], tuple[int, str]] | None = None,
    notify: Callable[[str], bool] | None = None,
) -> int:
    """Relay unique challenges and wait for human approval to authenticate."""
    if probe is None:
        probe = _observe_probe
    if notify is None:
        notify = _notify_mfa_via_hermes

    notified_numbers: set[str] = set()
    for poll_index in range(_MFA_MAX_POLLS):
        code, body = probe()
        if code != 0:
            return RunStatus.OBSERVE_FAILED
        try:
            data = json.loads(body)
        except Exception:
            return RunStatus.OBSERVE_FAILED
        if not isinstance(data, dict):
            return RunStatus.OBSERVE_FAILED

        state = data.get("state")
        number = data.get("mfa_number")
        ambiguous = data.get("mfa_ambiguous")
        if not isinstance(state, str) or not isinstance(ambiguous, bool):
            return RunStatus.OBSERVE_FAILED
        if number is not None and not isinstance(number, str):
            return RunStatus.OBSERVE_FAILED
        if ambiguous:
            return RunStatus.MFA_AMBIGUOUS
        if state == "AUTHENTICATED":
            return RunStatus.OK

        if state == "MFA_REQUIRED":
            valid_number = (
                isinstance(number, str)
                and len(number) == 2
                and number.isascii()
                and number.isdigit()
            )
            if not valid_number:
                return RunStatus.MFA_AMBIGUOUS
            if number not in notified_numbers:
                if not notify(number):
                    return RunStatus.MFA_NOTIFY_FAILED
                notified_numbers.add(number)
        elif state not in {"UNKNOWN", "WAITING_FOR_MFA"}:
            return RunStatus.MFA_BLOCKED

        if poll_index + 1 < _MFA_MAX_POLLS:
            time.sleep(_MFA_POLL_INTERVAL_S)

    return RunStatus.MFA_TIMEOUT


def _submit_credentials() -> dict[str, object] | int:
    """Decrypt, submit, and immediately drop both credential values."""
    try:
        username = _decrypt_credential(_USERNAME_CRED)
        password = _decrypt_credential(_PASSWORD_CRED)
    except RuntimeError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return RunStatus.DECRYPT_FAILED

    try:
        return _submit_loopback(username, password)
    except RuntimeError as exc:
        reason = str(exc)
        if reason == "SUBMIT_REJECTED":
            sys.stderr.write(
                "ERROR: worker rejected sign-in submit; "
                "no credential value is exposed.\n"
            )
            return RunStatus.SUBMIT_REJECTED
        if reason == "SUBMIT_UNREACHABLE":
            sys.stderr.write(
                "ERROR: worker loopback endpoint unreachable; "
                "is the browser-worker running?\n"
            )
            return RunStatus.SUBMIT_UNREACHABLE
        sys.stderr.write("ERROR: worker returned an unexpected response shape.\n")
        return RunStatus.BAD_RESPONSE
    finally:
        del username, password


def run_canonical() -> int:
    """Execute the complete deterministic sign-in and human-MFA pipeline."""
    try:
        _require_endpoint_ok("navigate", _NAVIGATE)
    except _StepFailed:
        return RunStatus.NAVIGATE_FAILED

    try:
        _require_endpoint_ok("begin-signin", _BEGIN_SIGNIN)
    except _StepFailed:
        return RunStatus.BEGIN_SIGNIN_FAILED

    try:
        _require_endpoint_ok("resolve-signin-surface", _RESOLVE_SURFACE, retries=3)
    except _StepFailed:
        return RunStatus.RESOLVE_FAILED

    if not _discover_email_gate():
        sys.stderr.write(
            "ERROR: email-entry surface not deterministically present after "
            "resolve-signin-surface; refusing operator-submit (fail-closed).\n"
        )
        return RunStatus.SURFACE_GATE_FAILED

    result = _submit_credentials()
    if isinstance(result, int):
        return result
    if result.get("ok") is not True:
        sys.stderr.write("ERROR: worker returned an unexpected response shape.\n")
        return RunStatus.BAD_RESPONSE

    auth_state = result.get("auth_state", "UNKNOWN")
    if not isinstance(auth_state, str):
        return RunStatus.BAD_RESPONSE
    if auth_state == "AUTHENTICATED":
        sys.stdout.write("ok=true auth_state=AUTHENTICATED\n")
        return RunStatus.OK

    final_status = _await_mfa_and_authenticate()
    if final_status == RunStatus.OK:
        sys.stdout.write("ok=true auth_state=AUTHENTICATED\n")
        return RunStatus.OK
    if final_status == RunStatus.OBSERVE_FAILED:
        sys.stderr.write(
            "ERROR: sanitized MFA observation failed; authentication stopped.\n"
        )
    elif final_status == RunStatus.MFA_AMBIGUOUS:
        sys.stderr.write(
            "ERROR: MFA challenge was ambiguous or invalid; nothing was relayed.\n"
        )
    elif final_status == RunStatus.MFA_NOTIFY_FAILED:
        sys.stderr.write(
            "ERROR: Hermes Telegram MFA notification failed; "
            "authentication stopped.\n"
        )
    elif final_status == RunStatus.MFA_TIMEOUT:
        sys.stderr.write(
            "ERROR: MFA approval window expired before authentication completed.\n"
        )
    else:
        sys.stderr.write(
            "ERROR: unsupported post-submit authentication state; "
            "stopped fail-closed.\n"
        )
    return final_status


def main(argv: list[str]) -> int:
    if argv:
        sys.stderr.write(
            "ERROR: operator_auth_run takes no arguments "
            "(fixed local store and routes).\n"
        )
        return RunStatus.USAGE
    return run_canonical()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
