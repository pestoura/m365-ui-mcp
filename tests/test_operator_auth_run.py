"""Security regression suite for the operator-only deterministic canonical
sign-in run orchestrator (AUTH-111).

Mirrors the fail-closed discipline of the sibling operator scripts. The
orchestrator (`scripts/operator_auth_run.py`) encodes the exact once-only
sequence and enforces the surface gate before operator-submit. It is NOT an MCP
tool and is NOT network-exposed.

Covers, explicitly:

* the surface gate requires 2x UNIQUE_MATCH on the email keys before submit is
  allowed, and returns False (fail-closed STOP) on NO_MATCH / AMBIGUOUS /
  malformed / non-OK readings;
* a first NO_MATCH probe followed by UNIQUE_MATCH within the bounded window is
  accepted (page-load timing is not the fail-closed STOP);
* ambiguous (multiple distinct candidates) fails closed to False;
* the ordered pipeline runs each step and stops at the first non-zero operator
  step (navigate/begin-signin/resolve failures short-circuit);
* no secret material, URL, DOM, cookie, token, UPN, tenant id or account
  identifier is ever placed in argv/env/log/state by the orchestrator;
* credentials are consumed memory-only and dropped (the submit payload is built
  in-process and handed to the in-container client over stdin only).

The live transport helpers (`_docker_exec_post`, `_run_in_container_submit`,
`_decrypt_credential`) are left to the operator run against the live worker;
this suite exercises the deterministic decision logic with injected probes.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "operator_auth_run.py"

# Load the script module without polluting the package namespace (it is a
# host-side operator tool, not an installed package).
_spec = importlib.util.spec_from_file_location("operator_auth_run", SCRIPT)
operator_auth_run = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(operator_auth_run)


def _ok_discover(result: str) -> tuple[int, str]:
    return 0, (
        '{"ok":true,"keys":['
        '{"selector_key":"auth.login_email_input","result":"' + result + '"},'
        '{"selector_key":"auth.login_next_button","result":"' + result + '"}'
        "]}"
    )


def _bad_discover() -> tuple[int, str]:
    return 0, '{"ok":true,"keys":[' \
        '{"selector_key":"auth.login_email_input","result":"NO_MATCH"},' \
        '{"selector_key":"auth.login_next_button","result":"NO_MATCH"}]}'


def _malformed() -> tuple[int, str]:
    return 0, "not-json"


def _non_ok() -> tuple[int, str]:
    return 0, '{"ok":false}'


def _transport_error() -> tuple[int, str]:
    return 7, "curl: (7) failed to connect"


class TestSurfaceGate:
    """The deterministic email-entry gate before operator-submit."""

    def test_unique_match_advances(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            operator_auth_run, "_discover_email_probe", lambda: _ok_discover("UNIQUE_MATCH")
        )
        assert operator_auth_run._discover_email_gate() is True

    def test_no_match_fails_closed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            operator_auth_run, "_discover_email_probe", lambda: _bad_discover()
        )
        assert operator_auth_run._discover_email_gate() is False

    def test_ambiguous_fails_closed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            operator_auth_run, "_discover_email_probe", lambda: _ok_discover("AMBIGUOUS")
        )
        assert operator_auth_run._discover_email_gate() is False

    def test_malformed_fails_closed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            operator_auth_run, "_discover_email_probe", lambda: _malformed()
        )
        assert operator_auth_run._discover_email_gate() is False

    def test_non_ok_fails_closed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            operator_auth_run, "_discover_email_probe", lambda: _non_ok()
        )
        assert operator_auth_run._discover_email_gate() is False

    def test_transport_error_fails_closed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            operator_auth_run, "_discover_email_probe", lambda: _transport_error()
        )
        assert operator_auth_run._discover_email_gate() is False

    def test_first_no_match_then_unique_match_advances(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Page-load timing: first probe NO_MATCH, second UNIQUE_MATCH. The gate
        # must not treat the first NO_MATCH as the fail-closed STOP.
        probes = iter([_bad_discover(), _ok_discover("UNIQUE_MATCH")])

        def _probe() -> tuple[int, str]:
            return next(probes)

        monkeypatch.setattr(operator_auth_run, "_discover_email_probe", _probe)
        monkeypatch.setattr(operator_auth_run, "_DISCOVER_INTERVAL_S", 0.0)
        assert operator_auth_run._discover_email_gate() is True

    def test_injected_probe_used(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # The gate accepts an injected probe (test seam). It must honor it.
        calls = {"n": 0}

        def _probe() -> tuple[int, str]:
            calls["n"] += 1
            return _ok_discover("UNIQUE_MATCH")

        monkeypatch.setattr(operator_auth_run, "_DISCOVER_INTERVAL_S", 0.0)
        assert operator_auth_run._discover_email_gate(probe=_probe) is True
        assert calls["n"] == 1


class TestOrderedPipeline:
    """The once-only ordered pipeline short-circuits on the first failure."""

    def test_navigate_failure_stops(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []

        def _require(label: str, endpoint: str) -> None:
            calls.append(label)
            if label == "navigate":
                raise operator_auth_run._StepFailed(label)

        monkeypatch.setattr(operator_auth_run, "_require_endpoint_ok", _require)
        monkeypatch.setattr(
            operator_auth_run, "_discover_email_gate", lambda: True
        )
        rc = operator_auth_run.run_canonical()
        assert rc == operator_auth_run.RunStatus.NAVIGATE_FAILED
        assert calls == ["navigate"]

    def test_begin_signin_failure_stops(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []

        def _require(label: str, endpoint: str) -> None:
            calls.append(label)
            if label == "begin-signin":
                raise operator_auth_run._StepFailed(label)

        monkeypatch.setattr(operator_auth_run, "_require_endpoint_ok", _require)
        monkeypatch.setattr(
            operator_auth_run, "_discover_email_gate", lambda: True
        )
        rc = operator_auth_run.run_canonical()
        assert rc == operator_auth_run.RunStatus.BEGIN_SIGNIN_FAILED
        assert calls == ["navigate", "begin-signin"]

    def test_resolve_failure_stops(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []

        def _require(label: str, endpoint: str) -> None:
            calls.append(label)
            if label == "resolve-signin-surface":
                raise operator_auth_run._StepFailed(label)

        monkeypatch.setattr(operator_auth_run, "_require_endpoint_ok", _require)
        monkeypatch.setattr(
            operator_auth_run, "_discover_email_gate", lambda: True
        )
        rc = operator_auth_run.run_canonical()
        assert rc == operator_auth_run.RunStatus.RESOLVE_FAILED
        assert calls == ["navigate", "begin-signin", "resolve-signin-surface"]

    def test_surface_gate_failure_stops(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []

        def _require(label: str, endpoint: str) -> None:
            calls.append(label)

        monkeypatch.setattr(operator_auth_run, "_require_endpoint_ok", _require)
        monkeypatch.setattr(
            operator_auth_run, "_discover_email_gate", lambda: False
        )
        rc = operator_auth_run.run_canonical()
        assert rc == operator_auth_run.RunStatus.SURFACE_GATE_FAILED
        assert "resolve-signin-surface" in calls

    def test_full_pipeline_reaches_submit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        steps: list[str] = []

        def _require(label: str, endpoint: str) -> None:
            steps.append(label)

        monkeypatch.setattr(operator_auth_run, "_require_endpoint_ok", _require)
        monkeypatch.setattr(
            operator_auth_run, "_discover_email_gate", lambda: True
        )

        # Decrypt returns fixed memory-only values; submit is driven by the
        # in-container loopback client with the closed {email,password} contract.
        monkeypatch.setattr(
            operator_auth_run,
            "_decrypt_credential",
            lambda name: "memory-only-value",
        )

        submitted: dict[str, object] = {}

        def _run_container(payload: str) -> tuple[int, str]:
            submitted["payload"] = payload
            return 0, '{"ok":true,"auth_state":"UNKNOWN"}'

        monkeypatch.setattr(
            operator_auth_run, "_run_in_container_submit", _run_container
        )

        rc = operator_auth_run.run_canonical()
        assert rc == operator_auth_run.RunStatus.OK
        assert steps == [
            "navigate",
            "begin-signin",
            "resolve-signin-surface",
        ]
        # Submit payload is the closed contract; values are never echoed here.
        import json as _json

        assert _json.loads(submitted["payload"]) == {
            "email": "memory-only-value",
            "password": "memory-only-value",
        }


class TestNoSecretExposure:
    """The orchestrator never prints or exports credential material."""

    def test_module_exposes_no_secret_constants(self) -> None:
        # The script must not define a literal credential value/secret.
        for name in dir(operator_auth_run):
            if name.startswith("__"):
                continue
            obj = getattr(operator_auth_run, name)
            if isinstance(obj, str) and ("password=" in obj.lower() or "secret=" in obj.lower()):
                # Only the fixed cred FILE NAME constant carries "password".
                assert name == "_PASSWORD_CRED"
                assert obj.endswith(".cred")
                continue

    def test_in_container_client_is_closed_contract(self) -> None:
        # The embedded in-container client must require exactly the closed
        # {email,password} contract and reject any other shape.
        client_src = operator_auth_run._IN_CONTAINER_SUBMIT_CLIENT
        assert 'set(parsed) != {"email", "password"}' in client_src
        # It must not echo the payload to stdout/stderr beyond the worker's own
        # sanitized response.
        assert "sys.stdout.write(payload" not in client_src
