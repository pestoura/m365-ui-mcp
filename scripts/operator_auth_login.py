#!/usr/bin/env python3
"""OPERATOR-ONLY encrypted-store Microsoft sign-in submit helper.

This is the local counterpart to the worker's
``POST /auth/bootstrap/operator-submit`` route (AUTH-101). It is NOT an MCP
tool, is NOT exposed over any network surface, and performs NO interactive login
on its own. It only:

1. Decrypts two already-provisioned encrypted *systemd user* credentials from the
   fixed local store under ``~/.local/lib/credstore.encrypted`` using
   ``systemd-creds decrypt --user``.
2. Keeps both decrypted values MEMORY-ONLY. They are never written to disk, never
   placed in argv, never exported to the environment, never logged, and never
   stored in worker/control-plane state.
3. Forwards them through a local loopback (``127.0.0.1:8090``) stdin/IPC path to
   the narrowly-scoped operator-only browser-worker route, which applies them to
   the already-open Microsoft authentication page and types nothing else.

Hard invariants (enforced here and in the worker):

* No generic DOM primitive, no arbitrary URL and no Graph surface is reachable.
  The destination is the fixed loopback worker endpoint; the only fields sent are
  ``email`` and ``password`` from the two provisioned creds.
* The plaintext values are consumed once (one in-memory POST) and then dropped.
  They are never echoed to stdout, stderr, logs or the terminal. Status/error
  output is sanitized and value-free.
* No real authentication is asserted by this script: the human still completes
  MFA in Microsoft Authenticator. This helper returns only a sanitized status
  code and the worker's sanitized ``{ok, auth_state}`` response.

This run never reads the real credential store or performs a real login.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

# FIXED local encrypted-store path. Intentionally NOT configurable via env/argv
# so no caller can redirect credential decryption to an attacker-controlled file.
_CREDSTORE_DIR = Path(os.path.expanduser("~")) / ".local" / "lib" / "credstore.encrypted"
_SYSTEMD_CREDS = "/usr/bin/systemd-creds"  # absolute path avoids bare-binary lint

# The two provisioned credential file names. Order is fixed; values stay memory-only.
_USERNAME_CRED = "m365-ui-mcp.username.cred"
_PASSWORD_CRED = "m365-ui-mcp.password.cred"  # noqa: S105 - cred file name, not a secret

# Fixed loopback worker endpoint (operator-only, socket-loopback admission).
_WORKER_ENDPOINT = "http://127.0.0.1:8090/auth/bootstrap/operator-submit"


class LoginStatus:
    """Sanitized exit-code contract. Values are NEVER carried in messages."""

    OK = 0
    USAGE = 2
    DECRYPT_FAILED = 3
    WORKER_REJECTED = 4
    WORKER_UNREACHABLE = 5
    BAD_RESPONSE = 6


def _decrypt_credential(cred_name: str) -> str:
    """Decrypt one provisioned systemd-creds file to memory only.

    Returns the plaintext value. Raises ``RuntimeError`` with a sanitized message
    (no value) if decryption fails or the store is unavailable.
    """
    cred_path = _CREDSTORE_DIR / cred_name
    if not cred_path.is_file():
        raise RuntimeError(f"encrypted credential not found: {cred_name}")
    # Decrypt straight to stdout (no OUTPUT file) so the plaintext never lands on
    # disk. ``--user`` selects the per-user systemd credential context.
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


def _submit_loopback(email: str, password: str) -> dict[str, object]:
    """POST the two memory-only fields to the loopback operator-submit route.

    The body is built in memory and sent over loopback only. The values are not
    placed in argv, env or any query string.
    """
    payload = json.dumps({"email": email, "password": password}).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310 - fixed loopback-only endpoint
        _WORKER_ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - loopback only
        body = response.read().decode("utf-8")
    return json.loads(body)


def main(argv: list[str]) -> int:
    if argv:
        # The caller may not supply the credential names or any target: the store
        # path, cred names and endpoint are all fixed by design.
        sys.stderr.write(
            "ERROR: operator_auth_login takes no arguments (fixed local store and route).\n"
        )
        return LoginStatus.USAGE

    try:
        username = _decrypt_credential(_USERNAME_CRED)
        password = _decrypt_credential(_PASSWORD_CRED)
    except RuntimeError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return LoginStatus.DECRYPT_FAILED

    # At this point both values are in memory. They are used exactly once below
    # and then become unreachable (no retention, no persistence, no print).
    try:
        result = _submit_loopback(username, password)
    except urllib.error.HTTPError as exc:
        sys.stderr.write(
            f"ERROR: worker rejected sign-in submit (http={exc.code}); "
            "no credential value is exposed.\n"
        )
        return LoginStatus.WORKER_REJECTED
    except urllib.error.URLError as exc:
        sys.stderr.write(
            f"ERROR: worker loopback endpoint unreachable ({exc.reason}); "
            "is the browser-worker running and on loopback 8090?\n"
        )
        return LoginStatus.WORKER_UNREACHABLE
    finally:
        # Drop the in-memory copies deterministically. Names are cleared so no
        # reference survives in this frame.
        del username, password

    if not isinstance(result, dict) or result.get("ok") is not True:
        sys.stderr.write("ERROR: worker returned an unexpected response shape.\n")
        return LoginStatus.BAD_RESPONSE

    # Sanitized success: only the worker's closed state value is reported.
    auth_state = result.get("auth_state", "UNKNOWN")
    sys.stdout.write(f"ok=true auth_state={auth_state}\n")
    return LoginStatus.OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
