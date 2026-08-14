"""Live authentication state machine wiring for the browser worker.

Bridges the existing live ``auth_flow`` probes (``classify_page`` /
``detect_mfa_number``) and ``planner_mcp.auth.MfaChallenge`` into the real
``AuthState`` lifecycle so that ``MFA_REQUIRED`` / ``WAITING_FOR_MFA`` become
*resolved* live states rather than static constants.

Fail-closed contract:

* The number-matching value is accepted ONLY when it is **uniquely** resolvable
  from the page text (``resolve_mfa_number_unique``). An ambiguous or empty
  number resolves to ``None`` and the state machine fails closed to
  ``UNKNOWN``; it never guesses a challenge value.
* No email/MFA locator is guessed here. This module operates on page text that
  the worker already classified; locator values remain evidence-gated under
  ``common.auth`` and are not invented.
* Transitions go through ``AuthContext.transition``, which raises on an illegal
  move, so an attacker cannot push the state machine into a privileged state by
  supplying crafted text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from planner_mcp.auth import AuthContext, AuthState, MfaChallenge

from .auth_flow import build_challenge, classify_page, resolve_mfa_number_unique


@dataclass(frozen=True)
class LiveAuthReading:
    """Outcome of one live page classification against the state machine."""

    state: AuthState
    # Sanitized metadata only. For MFA_REQUIRED this carries the built
    # MfaChallenge.to_dict(); for WAITING_FOR_MFA it is empty; otherwise empty.
    metadata: dict[str, Any]
    # The resolved challenge, or None when the page is not a number match.
    challenge: MfaChallenge | None
    # True when the state was advanced on the context (a legal transition).
    advanced: bool
    # True when the number match could not be uniquely read (fail-closed).
    mfa_ambiguous: bool


def classify_live(page_text: str) -> tuple[AuthState, MfaChallenge | None, bool]:
    """Classify live page text into a state plus a sanitized challenge.

    Returns ``(state, challenge, mfa_ambiguous)``. ``challenge`` is non-None only
    for ``MFA_REQUIRED`` with a uniquely resolved number. ``mfa_ambiguous`` is
    True when the page looks like a number-matching prompt but the number could
    not be read unambiguously (fail closed).
    """
    state, meta = classify_page(page_text)
    if state is AuthState.MFA_REQUIRED:
        number = resolve_mfa_number_unique(page_text)
        if number is None:
            # Looks like MFA but the number is not uniquely resolvable: do not
            # synthesize a challenge. Surface AUTH_REQUIRED-style ambiguity as a
            # fail-closed UNKNOWN so no guessed value propagates.
            return AuthState.UNKNOWN, None, True
        challenge = build_challenge(number, operation_id="auth-live")
        return state, challenge, False
    if state is AuthState.WAITING_FOR_MFA:
        # Approval-waiting: no number to read; challenge stays None.
        return state, None, False
    return state, None, False


def advance_live_auth_state(context: AuthContext, page_text: str) -> LiveAuthReading:
    """Advance ``context`` from a live page reading, fail closed.

    Performs the guarded transition and returns the reading. Illegal transitions
    let ``AuthContext.transition`` raise so the caller sees a hard error rather
    than a silently corrupted state.
    """
    state, challenge, ambiguous = classify_live(page_text)
    if state is AuthState.UNKNOWN:
        # UNKNOWN is never a legal transition target, so any UNKNOWN reading
        # (including the ambiguous case) must fail closed: preserve the existing
        # context and never call context.transition.
        return LiveAuthReading(
            state=AuthState.UNKNOWN,
            metadata={},
            challenge=None,
            advanced=False,
            mfa_ambiguous=ambiguous,
        )
    metadata: dict[str, Any] = {}
    advanced = False
    if challenge is not None:
        metadata = challenge.to_dict()
    elif state is AuthState.WAITING_FOR_MFA:
        metadata = {}
    if state == context.state:
        # Idempotent re-classification: do not re-transition to the same state.
        return LiveAuthReading(
            state=state, metadata=metadata, challenge=challenge,
            advanced=False, mfa_ambiguous=ambiguous,
        )
    context.transition(state)
    advanced = True
    return LiveAuthReading(
        state=state, metadata=metadata, challenge=challenge,
        advanced=advanced, mfa_ambiguous=ambiguous,
    )


def waiting_for_mfa(context: AuthContext) -> bool:
    """True when the context is in a resolved live MFA wait state."""
    return context.state in (AuthState.MFA_REQUIRED, AuthState.WAITING_FOR_MFA)
