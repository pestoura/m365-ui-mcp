#!/usr/bin/env python3
"""OPERATOR-ONLY encrypted-store email-stage helper for AUTH-106.

Local counterpart to the worker's ``POST /auth/bootstrap/begin-email`` route. It
is NOT an MCP tool, is NOT exposed over any network surface, and performs NO
interactive login. Credential semantics mirror ``operator_auth_login.py``.

It only:

1. Decrypts the ONE already-provisioned encrypted *systemd user* credential
   holding the operator's professional email address, from the fixed local store
   under ``~/.local/lib/credstore.encrypted`` using ``systemd-creds decrypt
   --user``. The password credential is NEVER read by this helper.
2. Keeps the decrypted value MEMORY-ONLY. It is never written to disk, never
   placed in argv, never exported to the environment, never logged, never echoed
   and never stored in worker/control-plane state.
3. Forwards it as the closed ``{"email": ...}`` body to the worker's
   loopback-only operator route.

Why a delivery helper is needed at all: the ``/auth/bootstrap/*`` routes admit
ONLY a SOCKET-level loopback peer, while ``systemd-creds`` is available only on
the host. A host-side ``curl`` to the published ``127.0.0.1:8090`` port arrives
from the Docker bridge gateway and is correctly rejected with ``404``. This
helper therefore decrypts on the host and hands the value to an in-container
loopback client over ``docker exec`` **stdin** (never argv, never env, never a
file). The in-container step reads one JSON object from stdin and POSTs it to
``127.0.0.1:8090`` from inside the container's own loopback namespace.

Hard invariants:

* Fixed store path, fixed credential name, fixed route, fixed container name.
  Nothing is configurable via argv or environment, so no caller can redirect
  credential decryption or the destination.
* The plaintext is consumed exactly once and then dropped. Status/error output is
  sanitized and value-free.
* ONLY the email is sent. No password is decrypted, referenced or transmitted.
* No authentication is asserted: the route only advances the live page to the
  password step. The human still completes MFA in Microsoft Authenticator.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# FIXED local encrypted-store path. Intentionally NOT configurable via env/argv.
_CREDSTORE_DIR = Path(os.path.expanduser("~")) / ".local" / "lib" / "credstore.encrypted"
_SYSTEMD_CREDS = "/usr/bin/systemd-creds"  # absolute path avoids bare-binary lint
_DOCKER = "/usr/bin/docker"  # absolute path avoids bare-binary lint

# The ONE provisioned credential this helper may read. The password credential is
# deliberately absent: the email stage must never carry a password.
_USERNAME_CRED = "m365-ui-mcp.username.cred"

# Fixed in-container loopback worker endpoint (operator-only admission).
_WORKER_ENDPOINT = "http://127.0.0.1:8090/auth/bootstrap/begin-email"
_WORKER_CONTAINER = "planner-mcp-browser-worker-1"

# In-container client. Reads ONE JSON object from stdin and POSTs it unchanged.
# The value never appears in argv or the environment of this program. The endpoint
# is appended from the module constant rather than interpolated, so the template
# needs no escaping and stays a fixed literal.
_IN_CONTAINER_CLIENT = (
    'ENDPOINT = "' + _WORKER_ENDPOINT + '"\n'
    """
import json, sys, urllib.error, urllib.request

payload = sys.stdin.buffer.read()
try:
    parsed = json.loads(payload)
except Exception:
    sys.stderr.write("ERROR: in-container client received a malformed body\\n")
    raise SystemExit(6)
if not isinstance(parsed, dict) or set(parsed) != {"email"}:
    sys.stderr.write("ERROR: in-container client requires the closed {email} contract\\n")
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
    sys.stderr.write("ERROR: worker rejected email stage (http={})\\n".format(exc.code))
    raise SystemExit(4) from None
except urllib.error.URLError as exc:
    sys.stderr.write("ERROR: worker loopback unreachable ({})\\n".format(exc.reason))
    raise SystemExit(5) from None
"""
)


class EmailStageStatus:
    """Sanitized exit-code contract. Values are NEVER carried in messages."""

    OK = 0
    USAGE = 2
    DECRYPT_FAILED = 3
    WORKER_REJECTED = 4
    WORKER_UNREACHABLE = 5
    BAD_RESPONSE = 6


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


def _submit_email_stage(email: str) -> dict[str, object]:
    """Hand the memory-only email to the in-container loopback client via stdin."""
    payload = json.dumps({"email": email})
    proc = subprocess.run(  # noqa: S603 - fixed binary, fixed container, no shell
        [
            _DOCKER,
            "exec",
            "-i",
            _WORKER_CONTAINER,
            "python3",
            "-c",
            _IN_CONTAINER_CLIENT,
        ],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == EmailStageStatus.WORKER_REJECTED:
        raise RuntimeError("WORKER_REJECTED")
    if proc.returncode == EmailStageStatus.WORKER_UNREACHABLE:
        raise RuntimeError("WORKER_UNREACHABLE")
    if proc.returncode != 0:
        raise RuntimeError("BAD_RESPONSE")
    try:
        parsed = json.loads(proc.stdout)
    except Exception:
        raise RuntimeError("BAD_RESPONSE") from None
    if not isinstance(parsed, dict):
        raise RuntimeError("BAD_RESPONSE")
    return parsed


def main(argv: list[str]) -> int:
    if argv:
        sys.stderr.write(
            "ERROR: operator_auth_begin_email takes no arguments "
            "(fixed local store and route).\n"
        )
        return EmailStageStatus.USAGE

    try:
        email = _decrypt_credential(_USERNAME_CRED)
    except RuntimeError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return EmailStageStatus.DECRYPT_FAILED

    # The value is in memory here. It is used exactly once below and then dropped.
    try:
        result = _submit_email_stage(email)
    except RuntimeError as exc:
        reason = str(exc)
        if reason == "WORKER_REJECTED":
            sys.stderr.write(
                "ERROR: worker rejected the email stage; no value is exposed.\n"
            )
            return EmailStageStatus.WORKER_REJECTED
        if reason == "WORKER_UNREACHABLE":
            sys.stderr.write(
                "ERROR: worker loopback endpoint unreachable; is the "
                "browser-worker running?\n"
            )
            return EmailStageStatus.WORKER_UNREACHABLE
        sys.stderr.write("ERROR: worker returned an unexpected response shape.\n")
        return EmailStageStatus.BAD_RESPONSE
    finally:
        del email

    if result.get("ok") is not True:
        sys.stderr.write("ERROR: worker returned an unexpected response shape.\n")
        return EmailStageStatus.BAD_RESPONSE

    auth_state = result.get("auth_state", "UNKNOWN")
    sys.stdout.write(f"ok=true auth_state={auth_state}\n")
    return EmailStageStatus.OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
