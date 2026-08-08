"""Auth state machine and MFA metadata tests."""

from __future__ import annotations

import pytest

from planner_browser_worker.auth_flow import classify_page, detect_mfa_number
from planner_mcp.auth import AuthContext, AuthState, MfaChallenge, can_transition


def test_all_states_present() -> None:
    assert {s.value for s in AuthState} == {
        "UNKNOWN", "READY", "AUTH_REQUIRED", "MFA_REQUIRED", "WAITING_FOR_MFA",
        "AUTHENTICATED", "SESSION_EXPIRED", "AUTH_FAILED",
    }


def test_legal_and_illegal_transitions() -> None:
    ctx = AuthContext()
    ctx.transition(AuthState.AUTH_REQUIRED)
    ctx.transition(AuthState.MFA_REQUIRED)
    ctx.transition(AuthState.WAITING_FOR_MFA)
    ctx.transition(AuthState.AUTHENTICATED)
    assert ctx.state is AuthState.AUTHENTICATED
    assert not can_transition(AuthState.AUTHENTICATED, AuthState.MFA_REQUIRED)
    with pytest.raises(ValueError):
        ctx.transition(AuthState.MFA_REQUIRED)


def test_mfa_challenge_is_two_digits_and_sanitized() -> None:
    challenge = MfaChallenge(
        number="42", operation_id="op-1", service="microsoft-entra-id",
        description="Sign in", expires_at="2030-01-01T00:00:00+00:00",
    )
    payload = challenge.to_dict()
    assert payload["mfa_number"] == "42"
    assert payload["approval_channel"] == "microsoft_authenticator"
    assert payload["approve_in_telegram"] == "false"
    assert "password" not in payload
    with pytest.raises(ValueError):
        MfaChallenge("7", "op", "svc", "d", "2030-01-01T00:00:00+00:00")


def test_detect_number_matching() -> None:
    text = "Open your Microsoft Authenticator app and enter the number 73 to sign in."
    assert detect_mfa_number(text) == "73"
    state, meta = classify_page(text)
    assert state is AuthState.MFA_REQUIRED
    assert meta["mfa_number"] == "73"
