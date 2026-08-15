"""Post-submit MFA relay lifecycle for the canonical operator auth runner.

AUTH-114 contract: after credentials are submitted, the operator runner polls the
loopback-only sanitized observation endpoint, relays a uniquely resolved Microsoft
Authenticator number to the already-configured Hermes Telegram home channel, and
waits for the human approval to complete. It never automates MFA approval.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "operator_auth_run.py"
_spec = importlib.util.spec_from_file_location("operator_auth_run_mfa", SCRIPT)
operator_auth_run = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(operator_auth_run)


def _reading(
    state: str,
    *,
    number: str | None = None,
    ambiguous: bool = False,
) -> tuple[int, str]:
    import json

    return 0, json.dumps(
        {
            "state": state,
            "mfa_number": number,
            "mfa_ambiguous": ambiguous,
        }
    )


class TestMfaRelayLifecycle:
    def test_unique_number_notified_once_then_authenticated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        probes = iter(
            [
                _reading("UNKNOWN"),
                _reading("MFA_REQUIRED", number="42"),
                _reading("WAITING_FOR_MFA"),
                _reading("MFA_REQUIRED", number="42"),
                _reading("AUTHENTICATED"),
            ]
        )
        notified: list[str] = []
        monkeypatch.setattr(operator_auth_run, "_MFA_POLL_INTERVAL_S", 0.0)

        rc = operator_auth_run._await_mfa_and_authenticate(
            probe=lambda: next(probes),
            notify=lambda number: notified.append(number) or True,
        )

        assert rc == operator_auth_run.RunStatus.OK
        assert notified == ["42"]

    def test_new_unique_challenge_is_relayed_but_duplicate_is_deduplicated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        probes = iter(
            [
                _reading("MFA_REQUIRED", number="42"),
                _reading("MFA_REQUIRED", number="42"),
                _reading("MFA_REQUIRED", number="17"),
                _reading("AUTHENTICATED"),
            ]
        )
        notified: list[str] = []
        monkeypatch.setattr(operator_auth_run, "_MFA_POLL_INTERVAL_S", 0.0)

        rc = operator_auth_run._await_mfa_and_authenticate(
            probe=lambda: next(probes),
            notify=lambda number: notified.append(number) or True,
        )

        assert rc == operator_auth_run.RunStatus.OK
        assert notified == ["42", "17"]

    @pytest.mark.parametrize(
        ("reading", "expected"),
        [
            (_reading("UNKNOWN", number=None, ambiguous=True), "MFA_AMBIGUOUS"),
            (_reading("MFA_REQUIRED", number=None), "MFA_AMBIGUOUS"),
            (_reading("MFA_REQUIRED", number="4"), "MFA_AMBIGUOUS"),
            (_reading("MFA_REQUIRED", number="424"), "MFA_AMBIGUOUS"),
            (_reading("MFA_REQUIRED", number="aa"), "MFA_AMBIGUOUS"),
        ],
    )
    def test_ambiguous_or_invalid_challenge_fails_closed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        reading: tuple[int, str],
        expected: str,
    ) -> None:
        notified: list[str] = []
        monkeypatch.setattr(operator_auth_run, "_MFA_POLL_INTERVAL_S", 0.0)
        rc = operator_auth_run._await_mfa_and_authenticate(
            probe=lambda: reading,
            notify=lambda number: notified.append(number) or True,
        )
        assert rc == getattr(operator_auth_run.RunStatus, expected)
        assert notified == []

    def test_malformed_observation_fails_closed(self) -> None:
        rc = operator_auth_run._await_mfa_and_authenticate(
            probe=lambda: (0, "not-json"),
            notify=lambda _number: True,
        )
        assert rc == operator_auth_run.RunStatus.OBSERVE_FAILED

    def test_transport_failure_fails_closed(self) -> None:
        rc = operator_auth_run._await_mfa_and_authenticate(
            probe=lambda: (7, "curl failed"),
            notify=lambda _number: True,
        )
        assert rc == operator_auth_run.RunStatus.OBSERVE_FAILED

    def test_notification_failure_stops_before_authentication(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(operator_auth_run, "_MFA_POLL_INTERVAL_S", 0.0)
        rc = operator_auth_run._await_mfa_and_authenticate(
            probe=lambda: _reading("MFA_REQUIRED", number="42"),
            notify=lambda _number: False,
        )
        assert rc == operator_auth_run.RunStatus.MFA_NOTIFY_FAILED

    def test_waiting_without_number_never_fabricates_one(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        probes = iter(
            [
                _reading("WAITING_FOR_MFA"),
                _reading("WAITING_FOR_MFA"),
                _reading("AUTHENTICATED"),
            ]
        )
        notified: list[str] = []
        monkeypatch.setattr(operator_auth_run, "_MFA_POLL_INTERVAL_S", 0.0)
        rc = operator_auth_run._await_mfa_and_authenticate(
            probe=lambda: next(probes),
            notify=lambda number: notified.append(number) or True,
        )
        assert rc == operator_auth_run.RunStatus.OK
        assert notified == []

    def test_persistent_unknown_times_out(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(operator_auth_run, "_MFA_MAX_POLLS", 3)
        monkeypatch.setattr(operator_auth_run, "_MFA_POLL_INTERVAL_S", 0.0)
        rc = operator_auth_run._await_mfa_and_authenticate(
            probe=lambda: _reading("UNKNOWN"),
            notify=lambda _number: True,
        )
        assert rc == operator_auth_run.RunStatus.MFA_TIMEOUT

    def test_unsupported_post_submit_state_is_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(operator_auth_run, "_MFA_POLL_INTERVAL_S", 0.0)
        rc = operator_auth_run._await_mfa_and_authenticate(
            probe=lambda: _reading("SESSION_EXPIRED"),
            notify=lambda _number: True,
        )
        assert rc == operator_auth_run.RunStatus.MFA_BLOCKED


class TestHermesTelegramTransport:
    def test_mfa_number_travels_only_over_stdin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: dict[str, object] = {}

        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""

        def _run(argv, **kwargs):
            seen["argv"] = list(argv)
            seen["input"] = kwargs.get("input")
            seen["shell"] = kwargs.get("shell", False)
            return _Result()

        monkeypatch.setattr(operator_auth_run.subprocess, "run", _run)
        assert operator_auth_run._notify_mfa_via_hermes("42") is True

        argv = seen["argv"]
        assert argv == [
            "/usr/bin/env",
            "hermes",
            "send",
            "--to",
            "telegram",
            "--quiet",
            "--file",
            "-",
        ]
        assert "42" not in " ".join(argv)
        assert "42" in str(seen["input"])
        assert seen["shell"] is False

    def test_notification_contains_no_identity_or_credential_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: dict[str, object] = {}

        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""

        def _run(_argv, **kwargs):
            seen["input"] = kwargs.get("input")
            return _Result()

        monkeypatch.setattr(operator_auth_run.subprocess, "run", _run)
        assert operator_auth_run._notify_mfa_via_hermes("42") is True
        message = str(seen["input"]).lower()
        for forbidden in (
            "password",
            "username",
            "email=",
            "cookie",
            "token",
            "tenant",
            "upn",
        ):
            assert forbidden not in message


class TestCanonicalPipelineMfaCompletion:
    def test_unknown_submit_state_continues_to_mfa_lifecycle(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(operator_auth_run, "_require_endpoint_ok", lambda *a, **k: None)
        monkeypatch.setattr(operator_auth_run, "_discover_email_gate", lambda: True)
        monkeypatch.setattr(operator_auth_run, "_decrypt_credential", lambda _name: "v")
        monkeypatch.setattr(
            operator_auth_run,
            "_run_in_container_submit",
            lambda _payload: (0, '{"ok":true,"auth_state":"UNKNOWN"}'),
        )
        calls: list[str] = []
        monkeypatch.setattr(
            operator_auth_run,
            "_await_mfa_and_authenticate",
            lambda: calls.append("mfa") or operator_auth_run.RunStatus.OK,
        )

        assert operator_auth_run.run_canonical() == operator_auth_run.RunStatus.OK
        assert calls == ["mfa"]

    def test_already_authenticated_submit_skips_notification_lifecycle(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(operator_auth_run, "_require_endpoint_ok", lambda *a, **k: None)
        monkeypatch.setattr(operator_auth_run, "_discover_email_gate", lambda: True)
        monkeypatch.setattr(operator_auth_run, "_decrypt_credential", lambda _name: "v")
        monkeypatch.setattr(
            operator_auth_run,
            "_run_in_container_submit",
            lambda _payload: (0, '{"ok":true,"auth_state":"AUTHENTICATED"}'),
        )
        monkeypatch.setattr(
            operator_auth_run,
            "_await_mfa_and_authenticate",
            lambda: pytest.fail("MFA lifecycle must not run for an authenticated session"),
        )

        assert operator_auth_run.run_canonical() == operator_auth_run.RunStatus.OK
