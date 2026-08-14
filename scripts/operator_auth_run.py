#!/usr/bin/env python3
"""OPERATOR-ONLY deterministic canonical Microsoft sign-in run orchestrator.

Drives the FIXED, fail-closed operator-only bootstrap sequence against the
already-running browser-worker, deterministically, with NO human browser
interaction. It is NOT an MCP tool and is NOT exposed over any network surface.

The sequence is exactly:

    navigate -> begin-signin -> resolve-signin-surface
        -> require surface EMAIL_ENTRY / discover-email UNIQUE_MATCH
        -> operator-submit

Every step is an OPERATOR-ONLY, socket-loopback-admitted worker route. This
script is the host-side conductor only: it never decrypts credentials of its
own, never types anything, and never selects an identity. It:

1. Runs each step ONCE in the exact order above. Re-running navigate/begin-signin
   would open a second auth page and 503 the discover/submit guards, so the
   sequence is a single ordered pipeline (a fresh run starts from a
   browser-worker restart, an operator action outside this script).
2. Enforces the surface gate after resolve-signin-surface: the email-entry
   surface MUST be present (deterministic) before operator-submit is allowed.
   The gate probes discover-email a bounded number of times with a short sleep
   (page-load timing can yield NO_MATCH on the first immediate probe; that is
   NOT the fail-closed STOP). Only TWO UNIQUE_MATCH results advance.
3. Refuses operator-submit on any other surface (account chooser still showing,
   device enrolment / CA / unsupported method, ambiguous, unknown): it never
   guesses, never clicks an identity, never proceeds.
4. Uses the VERIFIED in-container loopback transport for operator-submit (host
   `urllib` to the published 127.0.0.1:8090 port arrives via the Docker bridge
   gateway and is rejected 404 by socket-peer admission; the credentials are
   decrypted on the host and handed to an in-container client over docker exec
   **stdin**, which POSTs from the container's own loopback). This mirrors
   scripts/operator_auth_begin_email.py and the verified AUTH-101 plumbing.
5. Reports ONLY sanitized, value-free status. No URL, DOM, cookie, token, UPN,
   tenant id, account identifier, or credential value is ever printed.

Hard invariants (never weaken):

* Fixed container name, fixed endpoints, fixed credential file names. Nothing is
  configurable via argv or environment, so no caller can redirect the
  destination or the credential decryption.
* The two decrypted credential values are memory-only: consumed exactly once by
  the in-container loopback client over stdin, never placed in argv/env/state,
  never logged, never echoed.
* The resolver step (AUTH-109) is the ONLY surface-mutating operator action this
  orchestrator adds; it clicks ONLY the fixed "use another account" control and
  never selects a cached identity.
* No real authentication is asserted: the human still completes MFA in Microsoft
  Authenticator. This script returns only a sanitized success/state code.

This run never reads the real credential store or performs a real login unless
invoked by the operator against the live worker.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

# FIXED local encrypted-store path. NOT configurable via env/argv.
_CREDSTORE_DIR = Path(os.path.expanduser("~")) / ".local" / "lib" / "credstore.encrypted"
_SYSTEMD_CREDS = "/usr/bin/systemd-creds"  # absolute path avoids bare-binary lint
_DOCKER = "/usr/bin/docker"  # absolute path avoids bare-binary lint

# The two provisioned credential file names. Values stay memory-only.
_USERNAME_CRED = "m365-ui-mcp.username.cred"
_PASSWORD_CRED = "m365-ui-mcp.password.cred"  # noqa: S105 - cred file name, not a secret

# Fixed worker container (loopback 127.0.0.1:8090 inside the container).
_WORKER_CONTAINER = "m365-ui-mcp-browser-worker-1"

# Fixed loopback worker endpoints (operator-only, socket-loopback admission).
_NAVIGATE = "http://127.0.0.1:8090/auth/bootstrap/navigate"
_BEGIN_SIGNIN = "http://127.0.0.1:8090/auth/bootstrap/begin-signin"
_RESOLVE_SURFACE = "http://127.0.0.1:8090/auth/bootstrap/resolve-signin-surface"
_OPERATOR_SUBMIT = "http://127.0.0.1:8090/auth/bootstrap/operator-submit"
_DISCOVER_EMAIL = "http://127.0.0.1:8090/auth/bootstrap/discover-email"

# Bounded discover-email re-probe (page-load timing guard, not a retry loop).
_DISCOVER_PROBES = 6
_DISCOVER_INTERVAL_S = 3.0

# In-container client for operator-submit. Reads ONE JSON object from stdin and
# POSTs it unchanged to the fixed loopback endpoint. The credentials never
# appear in argv or the environment.
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
    """Sanitized exit-code contract. Values are NEVER carried in messages."""

    OK = 0
    USAGE = 2
    NAVIGATE_FAILED = 10
    BEGIN_SIGNIN_FAILED = 11
    RESOLVE_FAILED = 12
    SURFACE_GATE_FAILED = 13
    DECRYPT_FAILED = 3
    SUBMIT_REJECTED = 4
    SUBMIT_UNREACHABLE = 5
    BAD_RESPONSE = 6


class _StepFailed(Exception):
    """Internal fail-closed signal carrying only a sanitized step label."""


def _docker_exec_post(endpoint: str) -> tuple[int, str]:
    """POST an empty body to a loopback endpoint from inside the container.

    Returns (exit_code, sanitized_status_line). Used for the zero-body operator
    routes (navigate / begin-signin / resolve-signin-surface). A non-loopback
    caller (host curl) is rejected 404 by socket-peer admission; docker exec
    runs inside the container's own loopback namespace, which is admitted.
    """
    proc = subprocess.run(  # noqa: S603 - fixed binary, fixed container, no shell
        [
            _DOCKER,
            "exec",
            _WORKER_CONTAINER,
            "curl",
            "-sS",
            "-o",
            "-",
            "-w",
            "\\n",
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


def _require_endpoint_ok(label: str, endpoint: str) -> None:
    """Run a zero-body operator route once; fail closed on nonzero exit."""
    code, _body = _docker_exec_post(endpoint)
    if code != 0:
        # Sanitized: no body, no URL, no selector. The endpoint constant is a
        # fixed local route, not user input.
        sys.stderr.write(
            f"ERROR: operator step '{label}' failed (exit={code}); "
            "browser-worker rejected or unreachable.\n"
        )
        raise _StepFailed(label)


def _discover_email_probe() -> tuple[int, str]:
    """Probe discover-email once from inside the container (default probe)."""
    return _docker_exec_post(_DISCOVER_EMAIL)


def _discover_email_gate(
    probe: Callable[[], tuple[int, str]] | None = None,
) -> bool:
    """Probe discover-email a bounded number of times; require 2x UNIQUE_MATCH.

    Returns True when both email keys report UNIQUE_MATCH (the deterministic
    email-entry surface is present). Returns False on any NO_MATCH / AMBIGUOUS /
    non-OK reading after the bounded probe window — the caller then fails
    closed (STOP, never proceeds to submit). The probe is injectable for
    tests; the default probes the live worker via the container loopback. The
    probe is resolved at call time (not bound as a default argument) so an
    operator may monkeypatch the module-level probe and have it honored.
    """
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
            isinstance(k, dict) and k.get("result") == "UNIQUE_MATCH" for k in keys
        ):
            return True
        # Page-load timing can yield NO_MATCH on the first immediate probe; this
        # is NOT the fail-closed STOP. Sleep once and re-probe within the bound.
        time.sleep(_DISCOVER_INTERVAL_S)
    return False


def _decrypt_credential(cred_name: str) -> str:
    """Decrypt one provisioned systemd-creds file to memory only."""
    cred_path = _CREDSTORE_DIR / cred_name
    if not cred_path.is_file():
        raise RuntimeError(f"encrypted credential not found: {cred_name}")
    proc = subprocess.run(  # noqa: S603 - fixed binary + fixed path, no shell
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
    """Hand the JSON payload to the in-container loopback submit client.

    The two memory-only fields travel in the payload over docker exec **stdin**;
    they never appear in argv or the environment of either process.
    """
    proc = subprocess.run(  # noqa: S603 - fixed binary, fixed container, no shell
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
    """Decrypt-free submit of the two memory-only fields via in-container client."""
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


def run_canonical() -> int:
    """Execute the deterministic canonical operator sign-in pipeline."""
    # 1) navigate (fixed Planner Web target)
    try:
        _require_endpoint_ok("navigate", _NAVIGATE)
    except _StepFailed:
        return RunStatus.NAVIGATE_FAILED

    # 2) begin-signin (single auth page on approved origin)
    try:
        _require_endpoint_ok("begin-signin", _BEGIN_SIGNIN)
    except _StepFailed:
        return RunStatus.BEGIN_SIGNIN_FAILED

    # 3) resolve-signin-surface (AUTH-109: force EMAIL_ENTRY, fixed action only)
    try:
        _require_endpoint_ok("resolve-signin-surface", _RESOLVE_SURFACE)
    except _StepFailed:
        return RunStatus.RESOLVE_FAILED

    # 4) deterministic surface gate: email-entry MUST be present (2x UNIQUE_MATCH)
    if not _discover_email_gate():
        sys.stderr.write(
            "ERROR: email-entry surface not deterministically present after "
            "resolve-signin-surface; refusing operator-submit (fail-closed).\n"
        )
        return RunStatus.SURFACE_GATE_FAILED

    # 5) operator-submit (encrypted-store, memory-only, in-container loopback)
    try:
        username = _decrypt_credential(_USERNAME_CRED)
        password = _decrypt_credential(_PASSWORD_CRED)
    except RuntimeError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return RunStatus.DECRYPT_FAILED

    try:
        result = _submit_loopback(username, password)
    except RuntimeError as exc:
        reason = str(exc)
        if reason == "SUBMIT_REJECTED":
            sys.stderr.write(
                "ERROR: worker rejected sign-in submit; no credential value is exposed.\n"
            )
            return RunStatus.SUBMIT_REJECTED
        if reason == "SUBMIT_UNREACHABLE":
            sys.stderr.write(
                "ERROR: worker loopback endpoint unreachable; is the browser-worker running?\n"
            )
            return RunStatus.SUBMIT_UNREACHABLE
        sys.stderr.write("ERROR: worker returned an unexpected response shape.\n")
        return RunStatus.BAD_RESPONSE
    finally:
        del username, password

    if not isinstance(result, dict) or result.get("ok") is not True:
        sys.stderr.write("ERROR: worker returned an unexpected response shape.\n")
        return RunStatus.BAD_RESPONSE

    auth_state = result.get("auth_state", "UNKNOWN")
    sys.stdout.write(f"ok=true auth_state={auth_state}\n")
    return RunStatus.OK


def main(argv: list[str]) -> int:
    if argv:
        sys.stderr.write(
            "ERROR: operator_auth_run takes no arguments (fixed local store and routes).\n"
        )
        return RunStatus.USAGE
    return run_canonical()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
