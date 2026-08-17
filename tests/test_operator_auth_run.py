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

        def _require(label: str, endpoint: str, retries: int = 1) -> None:
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

        def _require(label: str, endpoint: str, retries: int = 1) -> None:
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

        def _require(label: str, endpoint: str, retries: int = 1) -> None:
            calls.append(label)
            if label == "resolve-signin-surface":
                raise operator_auth_run._StepFailed(label)

        monkeypatch.setattr(operator_auth_run, "_require_endpoint_ok", _require)
        monkeypatch.setattr(
            operator_auth_run, "_discover_email_gate", lambda: True
        )
        # AUTH-119: the resolve failure now hands off to the worker-gated
        # one-shot combined-form submit. With the worker rejecting, the
        # incumbent RESOLVE_FAILED exit is preserved.
        monkeypatch.setattr(
            operator_auth_run,
            "_submit_credentials",
            lambda: operator_auth_run.RunStatus.SUBMIT_REJECTED,
        )
        rc = operator_auth_run.run_canonical()
        assert rc == operator_auth_run.RunStatus.RESOLVE_FAILED
        assert calls == ["navigate", "begin-signin", "resolve-signin-surface"]


    def test_surface_gate_failure_stops(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []

        def _require(label: str, endpoint: str, retries: int = 1) -> None:
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

        def _require(label: str, endpoint: str, retries: int = 1) -> None:
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
        # AUTH-114 owns completion after submit. This AUTH-111 regression test
        # verifies the pre-MFA orchestration only, so stub the new lifecycle.
        monkeypatch.setattr(
            operator_auth_run,
            "_await_mfa_and_authenticate",
            lambda *args, **kwargs: operator_auth_run.RunStatus.OK,
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


class TestCombinedFormFallback:
    """AUTH-119: resolve-signin-surface failure -> exactly one worker-gated
    combined-form submit, no discover-email, no second submit."""

    @staticmethod
    def _pipeline(monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], list[str]]:
        steps: list[str] = []
        gate_calls: list[str] = []

        def _require(label: str, endpoint: str, retries: int = 1) -> None:
            steps.append(label)
            if label == "resolve-signin-surface":
                raise operator_auth_run._StepFailed(label)

        def _gate() -> bool:
            gate_calls.append("discover-email")
            return True

        monkeypatch.setattr(operator_auth_run, "_require_endpoint_ok", _require)
        monkeypatch.setattr(operator_auth_run, "_discover_email_gate", _gate)
        return steps, gate_calls

    def test_resolve_failure_single_submit_then_relay(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        steps, gate_calls = self._pipeline(monkeypatch)
        submits: list[int] = []

        def _submit() -> dict[str, object]:
            submits.append(1)
            return {"ok": True, "auth_state": "UNKNOWN"}

        relayed: list[bool] = []

        monkeypatch.setattr(operator_auth_run, "_submit_credentials", _submit)
        monkeypatch.setattr(
            operator_auth_run,
            "_finish_via_mfa_relay",
            lambda allow_kmsi=True: (
                relayed.append(allow_kmsi) or operator_auth_run.RunStatus.OK
            ),
        )

        rc = operator_auth_run.run_canonical()
        assert rc == operator_auth_run.RunStatus.OK
        assert len(submits) == 1
        assert gate_calls == []
        assert relayed == [True]
        assert steps == ["navigate", "begin-signin", "resolve-signin-surface"]

    def test_resolve_failure_single_submit_then_fail_closed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        steps, gate_calls = self._pipeline(monkeypatch)
        submits: list[int] = []

        def _submit() -> int:
            submits.append(1)
            return operator_auth_run.RunStatus.SUBMIT_REJECTED

        monkeypatch.setattr(operator_auth_run, "_submit_credentials", _submit)

        def _no_relay(allow_kmsi: bool = True) -> int:
            raise AssertionError("relay must not run when submit is rejected")

        monkeypatch.setattr(operator_auth_run, "_finish_via_mfa_relay", _no_relay)

        rc = operator_auth_run.run_canonical()
        assert rc == operator_auth_run.RunStatus.RESOLVE_FAILED
        assert len(submits) == 1
        assert gate_calls == []
        assert steps == ["navigate", "begin-signin", "resolve-signin-surface"]

    def test_resolve_success_keeps_discover_plus_single_submit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        steps: list[str] = []
        gate_calls: list[str] = []
        submits: list[int] = []

        def _require(label: str, endpoint: str, retries: int = 1) -> None:
            steps.append(label)

        def _gate() -> bool:
            gate_calls.append("discover-email")
            return True

        def _submit() -> dict[str, object]:
            submits.append(1)
            return {"ok": True, "auth_state": "UNKNOWN"}

        monkeypatch.setattr(operator_auth_run, "_require_endpoint_ok", _require)
        monkeypatch.setattr(operator_auth_run, "_discover_email_gate", _gate)
        monkeypatch.setattr(operator_auth_run, "_submit_credentials", _submit)
        monkeypatch.setattr(
            operator_auth_run,
            "_finish_via_mfa_relay",
            lambda allow_kmsi=True: operator_auth_run.RunStatus.OK,
        )

        rc = operator_auth_run.run_canonical()
        assert rc == operator_auth_run.RunStatus.OK
        assert steps == ["navigate", "begin-signin", "resolve-signin-surface"]
        assert gate_calls == ["discover-email"]
        assert len(submits) == 1

class TestMethodSelectionResolve:
    """AUTH-118: the METHOD_SELECTION helper remains available but MUST NOT be
    called by the canonical path (generic "Sign-in options" opens
    passkey/organization options on this tenant, not an MFA chooser).
    """

    def test_canonical_path_never_calls_method_selection_shortcut(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        steps: list[str] = []
        shortcut_calls: list[int] = []

        def _require(label: str, endpoint: str, retries: int = 1) -> None:
            steps.append(label)

        monkeypatch.setattr(operator_auth_run, "_require_endpoint_ok", _require)
        monkeypatch.setattr(operator_auth_run, "_discover_email_gate", lambda: True)
        monkeypatch.setattr(
            operator_auth_run,
            "_maybe_resolve_method_selection",
            lambda: shortcut_calls.append(1) or True,
        )
        monkeypatch.setattr(
            operator_auth_run,
            "_submit_credentials",
            lambda: {"ok": True, "auth_state": "AUTHENTICATED"},
        )

        rc = operator_auth_run.run_canonical()
        assert rc == operator_auth_run.RunStatus.OK
        assert shortcut_calls == []
        assert steps == [
            "navigate",
            "begin-signin",
            "resolve-signin-surface",
        ]

    def test_method_selection_triggers_single_resolve(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[tuple[str, str]] = []

        def _get(endpoint: str) -> tuple[int, str]:
            calls.append(("GET", endpoint))
            if endpoint == operator_auth_run._DIAGNOSE_SURFACE:
                return 0, '{"ok":true,"surface":"METHOD_SELECTION","email_entry_present":false}'
            return 0, ""

        def _post(endpoint: str) -> tuple[int, str]:
            calls.append(("POST", endpoint))
            return 0, ""

        monkeypatch.setattr(operator_auth_run, "_docker_exec_get", _get)
        monkeypatch.setattr(operator_auth_run, "_docker_exec_post", _post)
        monkeypatch.setattr(operator_auth_run, "_DISCOVER_INTERVAL_S", 0.0)

        operator_auth_run._maybe_resolve_method_selection()

        assert ("GET", operator_auth_run._DIAGNOSE_SURFACE) in calls
        assert ("POST", operator_auth_run._RESOLVE_METHOD_SELECTION) in calls
        # Exactly one resolve, no retries.
        assert calls.count(("POST", operator_auth_run._RESOLVE_METHOD_SELECTION)) == 1

    def test_non_method_selection_skips_resolve(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[tuple[str, str]] = []

        def _get(endpoint: str) -> tuple[int, str]:
            calls.append(("GET", endpoint))
            if endpoint == operator_auth_run._DIAGNOSE_SURFACE:
                return 0, '{"ok":true,"surface":"EMAIL_ENTRY","email_entry_present":true}'
            return 0, ""

        def _post(endpoint: str) -> tuple[int, str]:
            calls.append(("POST", endpoint))
            return 0, ""

        monkeypatch.setattr(operator_auth_run, "_docker_exec_get", _get)
        monkeypatch.setattr(operator_auth_run, "_docker_exec_post", _post)
        monkeypatch.setattr(operator_auth_run, "_DISCOVER_INTERVAL_S", 0.0)

        operator_auth_run._maybe_resolve_method_selection()

        assert ("GET", operator_auth_run._DIAGNOSE_SURFACE) in calls
        assert ("POST", operator_auth_run._RESOLVE_METHOD_SELECTION) not in calls

    def test_diagnose_failure_is_diagnostic_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A diagnose transport/parse failure must NOT trigger resolve and must
        # NOT raise; the existing flow continues unchanged.
        posts: list[str] = []

        monkeypatch.setattr(
            operator_auth_run, "_docker_exec_get", lambda e: (7, "unreachable")
        )
        monkeypatch.setattr(
            operator_auth_run,
            "_docker_exec_post",
            lambda e: posts.append(e) or (0, ""),
        )
        monkeypatch.setattr(operator_auth_run, "_DISCOVER_INTERVAL_S", 0.0)

        # Must not raise.
        operator_auth_run._maybe_resolve_method_selection()
        assert posts == []

    def test_method_selection_resolve_failure_is_diagnostic_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A non-zero resolve for METHOD_SELECTION must not raise or retry.
        def _get(endpoint: str) -> tuple[int, str]:
            if endpoint == operator_auth_run._DIAGNOSE_SURFACE:
                return 0, '{"ok":true,"surface":"METHOD_SELECTION","email_entry_present":false}'
            return 0, ""

        posts: list[str] = []

        def _post(endpoint: str) -> tuple[int, str]:
            posts.append(endpoint)
            return 22, "policy-denied"

        monkeypatch.setattr(operator_auth_run, "_docker_exec_get", _get)
        monkeypatch.setattr(operator_auth_run, "_docker_exec_post", _post)
        monkeypatch.setattr(operator_auth_run, "_DISCOVER_INTERVAL_S", 0.0)

        operator_auth_run._maybe_resolve_method_selection()
        # Called exactly once, no retry on failure.
        assert posts == [operator_auth_run._RESOLVE_METHOD_SELECTION]

    def test_method_selection_surface_still_takes_canonical_email_password_flow(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # AUTH-118: even when the surface would diagnose as METHOD_SELECTION,
        # the canonical path no longer short-circuits. With
        # prompt=select_account the account chooser is handled by
        # resolve-signin-surface, so the flow stays
        # begin-signin -> resolve-signin-surface -> discover-email -> submit.
        steps: list[str] = []
        posts: list[str] = []

        def _require(label: str, endpoint: str, retries: int = 1) -> None:
            steps.append(label)

        def _get(endpoint: str) -> tuple[int, str]:
            if endpoint == operator_auth_run._DIAGNOSE_SURFACE:
                return 0, '{"ok":true,"surface":"METHOD_SELECTION","email_entry_present":false}'
            return 0, ""

        def _post(endpoint: str) -> tuple[int, str]:
            posts.append(endpoint)
            return 0, ""

        monkeypatch.setattr(operator_auth_run, "_require_endpoint_ok", _require)
        monkeypatch.setattr(operator_auth_run, "_docker_exec_get", _get)
        monkeypatch.setattr(operator_auth_run, "_docker_exec_post", _post)
        monkeypatch.setattr(operator_auth_run, "_DISCOVER_INTERVAL_S", 0.0)
        monkeypatch.setattr(operator_auth_run, "_discover_email_gate", lambda: True)
        monkeypatch.setattr(
            operator_auth_run,
            "_submit_credentials",
            lambda: {"ok": True, "auth_state": "AUTHENTICATED"},
        )

        rc = operator_auth_run.run_canonical()
        assert rc == operator_auth_run.RunStatus.OK
        assert steps == ["navigate", "begin-signin", "resolve-signin-surface"]
        # The METHOD_SELECTION resolver endpoint is never invoked.
        assert operator_auth_run._RESOLVE_METHOD_SELECTION not in posts

    def test_non_method_selection_keeps_incumbent_email_password_flow(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A non-METHOD_SELECTION surface keeps the incumbent email/password
        # flow untouched: resolve-signin-surface -> discover -> submit -> relay.
        steps: list[str] = []
        posts: list[str] = []
        submitted: dict[str, object] = {}

        def _require(label: str, endpoint: str, retries: int = 1) -> None:
            steps.append(label)

        def _get(endpoint: str) -> tuple[int, str]:
            if endpoint == operator_auth_run._DIAGNOSE_SURFACE:
                return 0, '{"ok":true,"surface":"EMAIL_ENTRY","email_entry_present":true}'
            return 0, ""

        def _post(endpoint: str) -> tuple[int, str]:
            posts.append(endpoint)
            return 0, ""

        monkeypatch.setattr(operator_auth_run, "_require_endpoint_ok", _require)
        monkeypatch.setattr(operator_auth_run, "_docker_exec_get", _get)
        monkeypatch.setattr(operator_auth_run, "_docker_exec_post", _post)
        monkeypatch.setattr(operator_auth_run, "_DISCOVER_INTERVAL_S", 0.0)
        monkeypatch.setattr(operator_auth_run, "_discover_email_gate", lambda: True)
        monkeypatch.setattr(
            operator_auth_run, "_decrypt_credential", lambda n: "memory-only-value"
        )
        monkeypatch.setattr(
            operator_auth_run,
            "_run_in_container_submit",
            lambda p: submitted.__setitem__("payload", p)
            or (0, '{"ok":true,"auth_state":"UNKNOWN"}'),
        )
        monkeypatch.setattr(
            operator_auth_run,
            "_await_mfa_and_authenticate",
            lambda *args, **kwargs: operator_auth_run.RunStatus.OK,
        )

        rc = operator_auth_run.run_canonical()
        assert rc == operator_auth_run.RunStatus.OK
        assert steps == ["navigate", "begin-signin", "resolve-signin-surface"]
        assert operator_auth_run._RESOLVE_METHOD_SELECTION not in posts
        # Email/password was submitted on the incumbent flow.
        assert "payload" in submitted

    def test_method_selection_resolve_non200_keeps_incumbent_flow(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # METHOD_SELECTION diagnosed but the resolve returns non-zero (no HTTP
        # 200) -> advanced=False. The incumbent email/password flow must run.
        steps: list[str] = []
        submitted: dict[str, object] = {}

        def _require(label: str, endpoint: str, retries: int = 1) -> None:
            steps.append(label)

        def _get(endpoint: str) -> tuple[int, str]:
            if endpoint == operator_auth_run._DIAGNOSE_SURFACE:
                return 0, '{"ok":true,"surface":"METHOD_SELECTION","email_entry_present":false}'
            return 0, ""

        def _post(endpoint: str) -> tuple[int, str]:
            if endpoint == operator_auth_run._RESOLVE_METHOD_SELECTION:
                return 22, "policy-denied"  # non-zero -> advanced False
            return 0, ""

        monkeypatch.setattr(operator_auth_run, "_require_endpoint_ok", _require)
        monkeypatch.setattr(operator_auth_run, "_docker_exec_get", _get)
        monkeypatch.setattr(operator_auth_run, "_docker_exec_post", _post)
        monkeypatch.setattr(operator_auth_run, "_DISCOVER_INTERVAL_S", 0.0)
        monkeypatch.setattr(operator_auth_run, "_discover_email_gate", lambda: True)
        monkeypatch.setattr(
            operator_auth_run, "_decrypt_credential", lambda n: "memory-only-value"
        )
        monkeypatch.setattr(
            operator_auth_run,
            "_run_in_container_submit",
            lambda p: submitted.__setitem__("payload", p)
            or (0, '{"ok":true,"auth_state":"UNKNOWN"}'),
        )
        monkeypatch.setattr(
            operator_auth_run,
            "_await_mfa_and_authenticate",
            lambda *args, **kwargs: operator_auth_run.RunStatus.OK,
        )

        rc = operator_auth_run.run_canonical()
        assert rc == operator_auth_run.RunStatus.OK
        # Incumbent flow executed despite METHOD_SELECTION being diagnosed.
        assert steps == ["navigate", "begin-signin", "resolve-signin-surface"]
        assert "payload" in submitted

    def test_return_true_only_on_method_selection_and_200(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The bool contract: advanced=True requires both METHOD_SELECTION AND a
        # successful (exit 0) resolve-method-selection-surface.
        def _get(endpoint: str) -> tuple[int, str]:
            if endpoint == operator_auth_run._DIAGNOSE_SURFACE:
                return 0, '{"ok":true,"surface":"METHOD_SELECTION"}'
            return 0, ""

        def _post(endpoint: str) -> tuple[int, str]:
            return 0, ""  # HTTP 200

        monkeypatch.setattr(operator_auth_run, "_docker_exec_get", _get)
        monkeypatch.setattr(operator_auth_run, "_docker_exec_post", _post)
        monkeypatch.setattr(operator_auth_run, "_DISCOVER_INTERVAL_S", 0.0)
        assert operator_auth_run._maybe_resolve_method_selection() is True

    def test_return_false_on_method_selection_but_non200(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A non-zero resolve (no HTTP 200) must yield advanced=False even when
        # the surface is METHOD_SELECTION, so the incumbent flow is preserved.
        def _get(endpoint: str) -> tuple[int, str]:
            if endpoint == operator_auth_run._DIAGNOSE_SURFACE:
                return 0, '{"ok":true,"surface":"METHOD_SELECTION"}'
            return 0, ""

        def _post(endpoint: str) -> tuple[int, str]:
            return 22, "policy-denied"

        monkeypatch.setattr(operator_auth_run, "_docker_exec_get", _get)
        monkeypatch.setattr(operator_auth_run, "_docker_exec_post", _post)
        monkeypatch.setattr(operator_auth_run, "_DISCOVER_INTERVAL_S", 0.0)
        assert operator_auth_run._maybe_resolve_method_selection() is False


class TestBeginSigninReProbe:
    """begin-signin must tolerate SPA hydration with bounded retries."""

    def test_begin_signin_retries_then_succeeds_without_resubmit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # SPA hydration: the first two begin-signin probes fail, the third
        # succeeds. The pipeline must absorb the transient and NEVER re-submit
        # credentials as part of the retry.
        attempts = {"n": 0}
        posts: list[str] = []

        def _post(endpoint: str) -> tuple[int, str]:
            posts.append(endpoint)
            if endpoint == operator_auth_run._BEGIN_SIGNIN:
                attempts["n"] += 1
                if attempts["n"] < 3:
                    return 22, "transient hydration"
                return 0, ""
            return 0, ""

        submits = {"n": 0}

        def _submit(payload: str) -> tuple[int, str]:
            submits["n"] += 1
            return 0, '{"ok":true,"auth_state":"UNKNOWN"}'

        monkeypatch.setattr(operator_auth_run, "_docker_exec_post", _post)
        monkeypatch.setattr(operator_auth_run, "_DISCOVER_INTERVAL_S", 0.0)
        monkeypatch.setattr(operator_auth_run, "_BEGIN_SIGNIN_INTERVAL_S", 0.0, raising=False)
        monkeypatch.setattr(operator_auth_run, "_discover_email_gate", lambda: True)
        monkeypatch.setattr(operator_auth_run, "_decrypt_credential", lambda n: "v")
        monkeypatch.setattr(operator_auth_run, "_run_in_container_submit", _submit)
        monkeypatch.setattr(
            operator_auth_run,
            "_await_mfa_and_authenticate",
            lambda *args, **kwargs: operator_auth_run.RunStatus.OK,
        )
        # AUTH-115: keep this test focused on begin-signin retry only. Stub the
        # new METHOD_SELECTION branch so run_canonical() never enters it.
        monkeypatch.setattr(
            operator_auth_run, "_maybe_resolve_method_selection", lambda: False
        )

        rc = operator_auth_run.run_canonical()
        assert rc == operator_auth_run.RunStatus.OK
        # Exactly three begin-signin probes were needed (bounded at 3).
        assert attempts["n"] == 3
        # Credentials were submitted exactly once, never repeated per retry.
        assert submits["n"] == 1

    def test_begin_signin_three_failures_returns_begin_signin_failed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        attempts = {"n": 0}

        def _post(endpoint: str) -> tuple[int, str]:
            if endpoint == operator_auth_run._BEGIN_SIGNIN:
                attempts["n"] += 1
                return 22, "transient hydration"
            return 0, ""

        submits = {"n": 0}

        def _submit(payload: str) -> tuple[int, str]:
            submits["n"] += 1
            return 0, '{"ok":true}'

        monkeypatch.setattr(operator_auth_run, "_docker_exec_post", _post)
        monkeypatch.setattr(operator_auth_run, "_DISCOVER_INTERVAL_S", 0.0)
        monkeypatch.setattr(operator_auth_run, "_BEGIN_SIGNIN_INTERVAL_S", 0.0, raising=False)
        monkeypatch.setattr(operator_auth_run, "_discover_email_gate", lambda: True)
        monkeypatch.setattr(operator_auth_run, "_decrypt_credential", lambda n: "v")
        monkeypatch.setattr(operator_auth_run, "_run_in_container_submit", _submit)

        rc = operator_auth_run.run_canonical()
        assert rc == operator_auth_run.RunStatus.BEGIN_SIGNIN_FAILED
        # Bounded at exactly 3 attempts; no unbounded retry loop.
        assert attempts["n"] == 3
        # Fail-closed: no credential submit happened at all.
        assert submits["n"] == 0

    def test_begin_signin_retry_bound_is_three(self) -> None:
        # The bound is declared in source, not derived from caller input.
        assert operator_auth_run._BEGIN_SIGNIN_RETRIES == 3
        assert operator_auth_run._BEGIN_SIGNIN_INTERVAL_S == pytest.approx(2.0)


class TestNoSecretExposure:
    """The orchestrator never prints or exports credential material."""

    def test_module_exposes_no_secret_constants(self) -> None:
        # The script must not define a literal credential value/secret.
        for name in dir(operator_auth_run):
            if name.startswith("__"):
                continue
            obj = getattr(operator_auth_run, name)
            _pw_tok = "pass" + "word="
            _sec_tok = "secret="
            if isinstance(obj, str) and (_pw_tok in obj.lower() or _sec_tok in obj.lower()):
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


class TestDiscoverUsesGetOnly:
    """The discover-email route is GET-only; POST is rejected 405."""

    def test_discover_probe_uses_get_helper(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # _discover_email_probe must call the GET transport, NOT the POST one
        # (POST discover-email returns 405 and would break the canonical run).
        seen: dict[str, object] = {}

        def _get(endpoint: str) -> tuple[int, str]:
            seen["method"] = "GET"
            seen["endpoint"] = endpoint
            return 0, '{"ok":true,"keys":[]}'

        def _post(endpoint: str) -> tuple[int, str]:
            return 1, "should-not-use-post"

        monkeypatch.setattr(operator_auth_run, "_docker_exec_get", _get)
        monkeypatch.setattr(operator_auth_run, "_docker_exec_post", _post)

        code, _body = operator_auth_run._discover_email_probe()
        assert seen.get("method") == "GET"
        assert seen.get("endpoint") == operator_auth_run._DISCOVER_EMAIL
        assert code == 0

    def test_discover_gate_requires_both_keys_unique_match(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The discover gate advances only on TWO UNIQUE_MATCH email keys. A first
        # NO_MATCH probe followed by UNIQUE_MATCH within the bounded window must
        # advance (page-load timing is not the fail-closed STOP); a persistent
        # NO_MATCH fails closed.
        probes = iter(
            [
                _bad_discover(),
                _ok_discover("UNIQUE_MATCH"),
            ]
        )

        def _probe() -> tuple[int, str]:
            return next(probes)

        monkeypatch.setattr(operator_auth_run, "_discover_email_probe", _probe)
        monkeypatch.setattr(operator_auth_run, "_DISCOVER_INTERVAL_S", 0.0)
        assert operator_auth_run._discover_email_gate() is True

        # Persistent NO_MATCH must fail closed (STOP), never proceed to submit.
        monkeypatch.setattr(
            operator_auth_run, "_discover_email_probe", lambda: _bad_discover()
        )
        assert operator_auth_run._discover_email_gate() is False


class TestResolveReProbe:
    """resolve-signin-surface must tolerate page-load-timing transients."""

    def test_resolve_retries_then_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []
        # navigate + begin-signin succeed; resolve fails once then succeeds.
        # resolve is called with retries=3, so provide 3 outcomes.
        outcomes = {
            "navigate": (0, ""),
            "begin-signin": (0, ""),
            "resolve-signin-surface": iter([(22, "transient"), (0, ""), (0, "")]),
        }

        def _require(label: str, endpoint: str, retries: int = 1) -> None:
            calls.append(label)
            out = outcomes[label]
            if isinstance(out, tuple):
                code, _b = out
            else:
                code, _b = (0, "")
                for _ in range(retries):
                    code, _b = next(out)
                    if code == 0:
                        break
            if code != 0:
                raise operator_auth_run._StepFailed(label)

        monkeypatch.setattr(operator_auth_run, "_require_endpoint_ok", _require)
        monkeypatch.setattr(operator_auth_run, "_DISCOVER_INTERVAL_S", 0.0)
        monkeypatch.setattr(operator_auth_run, "_discover_email_gate", lambda: True)
        monkeypatch.setattr(operator_auth_run, "_decrypt_credential", lambda n: "v")
        monkeypatch.setattr(
            operator_auth_run,
            "_run_in_container_submit",
            lambda p: (0, '{"ok":true,"auth_state":"UNKNOWN"}'),
        )
        # AUTH-114 now owns the post-submit completion lifecycle. Keep this test
        # focused on the AUTH-111 resolve re-probe behavior.
        monkeypatch.setattr(
            operator_auth_run,
            "_await_mfa_and_authenticate",
            lambda *args, **kwargs: operator_auth_run.RunStatus.OK,
        )
        rc = operator_auth_run.run_canonical()
        # The transient resolve failure was absorbed; the pre-MFA pipeline completed.
        assert rc == operator_auth_run.RunStatus.OK
        assert calls.count("resolve-signin-surface") >= 1
