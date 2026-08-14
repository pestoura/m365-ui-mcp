"""Loopback-only live sign-in observation for the browser worker.

This module implements the OPERATOR-ONLY ``/auth/bootstrap/observe`` contract.
It reuses the existing fail-closed ``auth_state_machine`` logic
(``classify_live`` / ``advance_live_auth_state``) to read the live sign-in
surface and expose ONLY a sanitized state. No URL, page text, DOM, selector,
cookie, token, UPN, tenant id or account identifier is ever logged or returned.

Fail-closed invariants:

* the visible body text is read internally through the narrow
  ``PersistentBrowser.read_visible_body_bounded`` primitive, which itself only
  fires when the browser is started + dedicated profile + approved Microsoft
  auth origin (or the fixed Planner Web surface) + exactly one auth page. The
  text is consumed here and never logged or returned;
* ambiguous number matching resolves to ``None`` (``mfa_number`` null) and the
  state machine never guesses a challenge value;
* an ambiguous ``UNKNOWN`` reading never corrupts an already-established
  ``AuthContext``: the observation holds a separate in-memory context and the
  context is preserved on ambiguous ``UNKNOWN`` (and on any other illegal move,
  so a resumed mid-flow observation never 500s or corrupts);
* if the live surface has transitioned back to the fixed Planner Web surface
  while the observation context still carries prior evidence of an in-flight
  sign-in (``AUTH_REQUIRED`` / ``MFA_REQUIRED`` / ``WAITING_FOR_MFA``), the
  endpoint reports ``AUTHENTICATED`` from that live surface transition (a
  polling-skip) rather than contract attestation; on Planner Web with no prior
  auth-state evidence (``UNKNOWN`` / ``READY``) it returns sanitized
  ``UNKNOWN`` and does NOT mark authenticated;
* the endpoint is not an MCP tool, not on the control plane, and is admitted
  only by a socket-level loopback check.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from m365_browser_worker.bootstrap_navigation import is_planner_web_surface_url
from planner_mcp.auth import AuthContext, AuthState

from .auth_state_machine import advance_live_auth_state, classify_live

# Bounded visible body length read internally for classification only.
_OBSERVATION_MAX_CHARS = 2000


@dataclass
class ObservationResult:
    """Sanitized observation outcome. No page text or identifiers."""

    state: AuthState
    mfa_number: str | None
    mfa_ambiguous: bool


def _advance_checked(context: AuthContext, target: AuthState) -> None:
    """Attempt a guarded transition; swallow only illegal-move errors.

    Used so an observation that resumes mid-flow (or sees a live state the
    internal context cannot legally reach from its current position) never
    corrupts the context or raises. Any other error is left to propagate.
    """
    try:
        context.transition(target)
    except ValueError:
        # Illegal transition: preserve the existing context. The live state is
        # still reported in the response; only the internal bookkeeping stays.
        pass


def _planner_web_surface_present(browser: Any) -> bool:
    """Return True when exactly one open page is the fixed Planner Web surface.

    Used to detect the post-sign-in surface transition. Only the closed host
    classifier is consulted; raw URLs are never returned. The browser context
    attribute name differs between production (``_context``) and test doubles
    (``context``), so both are probed.
    """
    context = getattr(browser, "_context", None) or getattr(browser, "context", None)
    if context is None:
        return False
    pages = [p for p in context.pages if str(p.url)]
    if len(pages) != 1:
        return False
    return is_planner_web_surface_url(str(pages[0].url))


async def observe_signin_state(browser: Any, context: AuthContext) -> ObservationResult:
    """Read the live sign-in surface and return a sanitized closed state.

    The flow:

    1. check the fixed Planner Web surface first (fail-closed, no URL/text read):
       if present, the live surface has transitioned back to Planner after
       sign-in. Report ``AUTHENTICATED`` (advancing the context when the move is
       legal) or sanitize ``UNKNOWN`` for unrecognized context states;
    2. only when Planner Web is not present, fail closed if the browser cannot
       be observed via the narrow primitive;
    3. read bounded visible body text internally (never logged/returned);
    4. classify via the existing safe state machine (``classify_live``) and
       advance the in-memory observation context with ``advance_live_auth_state``
       when the move is legal. Ambiguous ``UNKNOWN`` and any illegal move
       preserve the context instead of corrupting it.

    Returns only ``state``, an optional 2-digit ``mfa_number`` and
    ``mfa_ambiguous``.
    """
    # Planner Web surface takes precedence over the bounded body read. The
    # surface classifier never returns URLs/text, so no URL or page text is
    # ever consumed on this path.
    if _planner_web_surface_present(browser):
        if context.state is AuthState.AUTHENTICATED:
            return ObservationResult(
                state=AuthState.AUTHENTICATED, mfa_number=None, mfa_ambiguous=False
            )
        if context.state in (
            AuthState.AUTH_REQUIRED,
            AuthState.MFA_REQUIRED,
            AuthState.WAITING_FOR_MFA,
        ):
            # Live surface returned to Planner Web with a prior in-flight
            # sign-in: treat as AUTHENTICATED from the live surface (polling
            # skip), not contract attestation.
            _advance_checked(context, AuthState.AUTHENTICATED)
            return ObservationResult(
                state=AuthState.AUTHENTICATED, mfa_number=None, mfa_ambiguous=False
            )
        if context.state in (AuthState.UNKNOWN, AuthState.READY):
            # On Planner Web with no prior auth-state evidence: do NOT mark
            # authenticated. Return sanitized UNKNOWN without reading the
            # Microsoft-auth body text and without mutating the context.
            return ObservationResult(
                state=AuthState.UNKNOWN, mfa_number=None, mfa_ambiguous=False
            )
        # Any other state on Planner Web (e.g. already AUTHENTICATED,
        # SESSION_EXPIRED): fall through to the bounded page-text
        # classification below.

    page_text = await browser.read_visible_body_bounded(max_chars=_OBSERVATION_MAX_CHARS)

    # ``classify_live`` is the existing fail-closed classifier: a unique number
    # match yields MFA_REQUIRED + challenge, an ambiguous page yields UNKNOWN,
    # and WAITING_FOR_MFA yields the approval-wait state.
    state, challenge, ambiguous = classify_live(page_text)
    mfa_number: str | None = challenge.number if challenge is not None else None

    if state is AuthState.UNKNOWN:
        # Ambiguous / unrecognized surface: never corrupt the observation
        # context. The context is preserved and reported as UNKNOWN.
        return ObservationResult(
            state=AuthState.UNKNOWN, mfa_number=None, mfa_ambiguous=ambiguous
        )

    # Valid live auth state. Prefer the existing ``advance_live_auth_state``
    # helper for the legal-transition case; if the internal context is in a
    # position for which the move is illegal (observation resumed mid-flow),
    # preserve the context but still report the live state below.
    try:
        advance_live_auth_state(context, page_text)
    except ValueError:
        pass

    return ObservationResult(state=state, mfa_number=mfa_number, mfa_ambiguous=ambiguous)
