"""Auth and MFA detection helpers for the worker."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from planner_mcp.auth import AuthState, MfaChallenge

# Explicit Authenticator number-matching phrase, immediately preceding a 2-digit
# code (proximity bound, no newline crossing, so a stray year / request id /
# countdown / timestamp on the page can NEVER be mis-extracted). The phrase is
# the fixed semantic context that binds the extracted value: no number is
# emitted unless it is clearly presented as the "number to enter / approve" in
# the Microsoft Authenticator number-matching prompt. This is the determinism
# guarantee required for the post-password MFA surface: extraction is anchored
# to meaning, not to the mere presence of a 2-digit token near the word
# "authenticator".
_NUMBER_MATCH_PHRASE = re.compile(
    r"(?:enter the number|number matching|type the number|the number shown|"
    r"number shown on your|open your authenticator[^0-9]{0,80}?)"
    r"[^0-9]{0,80}?(\d{2})\b",
    re.IGNORECASE | re.DOTALL,
)


def _number_match_candidates(page_text: str) -> list[str]:
    """Return every 2-digit code bound to an explicit number-matching phrase.

    Only values presented as the Authenticator number-match are eligible; a
    date, countdown, request id or other generic numeric text on the page is
    never a candidate. The candidate set is empty unless the page carries the
    fixed number-matching semantic context.
    """
    return [m.group(1) for m in _NUMBER_MATCH_PHRASE.finditer(page_text)]


def detect_mfa_number(page_text: str) -> str | None:
    """Extract the phrase-bound Authenticator number-match value, fail closed.

    Returns the value ONLY when exactly one phrase-bound candidate exists. Zero
    candidates (no number-matching prompt) or more than one (ambiguous surface)
    resolves to ``None`` so callers never guess or synthesize a challenge value.
    """
    candidates = _number_match_candidates(page_text)
    if len(candidates) == 1:
        return candidates[0]
    return None


def resolve_mfa_number_unique(page_text: str) -> str | None:
    """Fail-closed MFA number resolver for the LIVE state machine.

    Returns the number ONLY when exactly one phrase-bound number-match candidate
    is present (see :func:`_number_match_candidates`). If the page contains zero
    candidates, or more than one distinct candidate (ambiguous), it returns
    ``None`` so the caller fails closed instead of guessing a challenge value.
    Extraction is anchored to the fixed number-matching semantic context, so a
    generic 2-digit value elsewhere on the page can never create ambiguity.
    """
    candidates = {m for m in _number_match_candidates(page_text)}
    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def build_challenge(
    number: str, *, operation_id: str, description: str = "Sign in to Microsoft Planner",
    ttl_seconds: int = 120,
) -> MfaChallenge:
    """Build sanitized MFA metadata. Approval only happens in Authenticator."""
    expires = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
    return MfaChallenge(
        number=number,
        operation_id=operation_id,
        service="microsoft-entra-id",
        description=description,
        expires_at=expires.isoformat(),
    )


def classify_page(page_text: str) -> tuple[AuthState, dict[str, Any]]:
    """Classify an auth page into a state plus sanitized metadata.

    The number-match surface is recognized ONLY when exactly one phrase-bound
    Authenticator code is present (see :func:`_number_match_candidates`). Zero
    candidates ⇒ no number-match prompt; more than one ⇒ ambiguous (handled as
    a fail-closed UNKNOWN by :func:`classify_live`, never guessed here).
    """
    lowered = page_text.lower()
    candidates = _number_match_candidates(page_text)
    if len(candidates) == 1:
        challenge = build_challenge(candidates[0], operation_id="auth-live")
        return AuthState.MFA_REQUIRED, challenge.to_dict()
    if "approve sign in request" in lowered or "waiting for approval" in lowered:
        return AuthState.WAITING_FOR_MFA, {}
    if "sign in" in lowered or "enter password" in lowered:
        return AuthState.AUTH_REQUIRED, {}
    if "your session has expired" in lowered:
        return AuthState.SESSION_EXPIRED, {}
    return AuthState.UNKNOWN, {}
