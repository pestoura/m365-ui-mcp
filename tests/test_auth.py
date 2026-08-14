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


def test_detect_number_matching_type_the_number() -> None:
    # Alternate authentic phrasing the live surface uses.
    text = "To sign in, type the number 73 shown on your phone. Approve sign in request"
    assert detect_mfa_number(text) == "73"
    state, meta = classify_page(text)
    assert state is AuthState.MFA_REQUIRED
    assert meta["mfa_number"] == "73"


def test_detect_fails_closed_on_unbound_authenticator_token() -> None:
    # "authenticator" is present, but the only 2-digit token (2024) is a YEAR
    # / request id, NOT the number-match. Phrase-bound extraction must not emit
    # it; ambiguity is not invented from a generic numeric value.
    text = "Microsoft Authenticator request received at 14:23 on 2024-08-14. Please wait."
    assert detect_mfa_number(text) is None
    state, meta = classify_page(text)
    # No phrase-bound number-match phrase => not MFA_REQUIRED.
    assert state is not AuthState.MFA_REQUIRED


def test_detect_fails_closed_on_ambiguous_two_numbers() -> None:
    # Two distinct phrase-bound candidates => ambiguous => None (never guess).
    text = (
        "Enter the number 73 to sign in. If that does not work, enter the number 84 "
        "shown on your phone. Approve sign in request"
    )
    assert detect_mfa_number(text) is None


def test_detect_fails_closed_when_number_not_bound_to_phrase() -> None:
    # A bare 2-digit code with no number-matching phrase nearby must not match.
    text = "Your session code is 19. Approve sign in request in Microsoft Authenticator."
    assert detect_mfa_number(text) is None


def test_classify_page_mfa_only_on_unique_phrase_bound_code() -> None:
    # Exactly one phrase-bound code => MFA_REQUIRED with that number.
    text = "Open your authenticator and enter the number 73 to sign in."
    state, meta = classify_page(text)
    assert state is AuthState.MFA_REQUIRED
    assert meta["mfa_number"] == "73"
    # Two phrase-bound codes => not a confident MFA_REQUIRED (ambiguous surface).
    ambiguous = (
        "Enter the number 42 and enter the number 17 shown in your "
        "Microsoft Authenticator app."
    )
    state2, _ = classify_page(ambiguous)
    assert state2 is not AuthState.MFA_REQUIRED


def test_resolve_mfa_number_unique_matches_phrase_bound_only() -> None:
    from planner_browser_worker.auth_flow import resolve_mfa_number_unique

    assert resolve_mfa_number_unique(
        "Open your authenticator and enter the number 73 to sign in."
    ) == "73"
    # Ambiguous surface (two candidates) resolves closed.
    assert resolve_mfa_number_unique(
        "Enter the number 73. Also enter the number 84 shown on your phone."
    ) is None
    # Generic numeric context with no phrase must not resolve.
    assert resolve_mfa_number_unique(
        "Microsoft Authenticator 2024 session 15 pending approval"
    ) is None
